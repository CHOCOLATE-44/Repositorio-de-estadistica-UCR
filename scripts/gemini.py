"""Cliente mínimo para la API de Gemini (Google AI Studio).

La clave se obtiene gratis en https://aistudio.google.com/apikey con una cuenta
de Google, sin tarjeta de crédito. Se guarda como secreto del repositorio
`GEMINI_API_KEY`. Si no existe, los scripts funcionan con reglas simples.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://generativelanguage.googleapis.com/v1beta"
URL = BASE + "/models/{modelo}:generateContent"
_alternativos: dict[str, str] = {}  # modelo pedido → modelo que lo reemplaza en esta ejecución
_sin_cuota: set[str] = set()          # modelos con la cuota diaria agotada (cada modelo tiene la suya)
_saturado = False  # si Google no respondió o no hay cuota en ningún modelo, no insistimos en esta ejecución


def disponible() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY")) and not _saturado


def es_cuota_agotada(codigo: int, cuerpo: str) -> bool:
    """429 por cuota (diaria o por minuto) agotada, a diferencia de una saturación pasajera."""
    return codigo == 429 and any(x in cuerpo for x in ("quota", "RESOURCE_EXHAUSTED", "rate-limit"))


def elegir_modelo_flash(clave: str, excluir: set[str] = frozenset(), permitir_lite: bool = False,
                        preferir_lite: bool = False) -> str | None:
    """Busca el modelo «flash» estable más nuevo que admita generateContent.
    Se usa si el modelo configurado fue retirado (404), está saturado (503) o sin cuota (429)."""
    req = urllib.request.Request(f"{BASE}/models?pageSize=200")
    req.add_header("x-goog-api-key", clave)
    with urllib.request.urlopen(req, timeout=60) as r:
        modelos = json.loads(r.read()).get("models", [])
    patron = r"gemini-(\d+(?:\.\d+)?)-flash" + ("(?:-lite)?" if permitir_lite or preferir_lite else "")
    candidatos = []
    for m in modelos:
        nombre = m.get("name", "").removeprefix("models/")
        if nombre in excluir or "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if not re.fullmatch(patron, nombre):
            continue  # descarta preview, image, tts, live, etc.
        es_lite = nombre.endswith("-lite")
        # Preferimos el tipo pedido (lite o completo) y, dentro de él, la versión más nueva.
        candidatos.append((es_lite == preferir_lite, float(nombre.split("-")[1]), nombre))
    return max(candidatos)[2] if candidatos else None


def _cambiar_modelo(clave: str, pedido: str, actual: str, motivo: str) -> str | None:
    lite = "lite" in pedido
    try:
        nuevo = elegir_modelo_flash(clave, excluir={actual, *_sin_cuota}, permitir_lite=True, preferir_lite=lite)
    except Exception as e:
        print(f"Aviso: no se pudo listar modelos de Gemini: {e}")
        return None
    if nuevo:
        print(f"Aviso: {actual} {motivo}; se usa {nuevo}.")
        _alternativos[pedido] = nuevo
    return nuevo


def preguntar_json(prompt: str, modelo: str, imagenes: list[Path] = (), intentos: int = 6) -> dict:
    """Envía el prompt (y opcionalmente imágenes JPEG) y devuelve la respuesta
    como JSON. Reintenta con espera creciente si Google está saturado y, si el
    modelo sigue sin responder, cambia a otro modelo flash. Lanza RuntimeError
    si no hay clave o la API falla."""
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError("Falta GEMINI_API_KEY")

    partes: list[dict] = [{"text": prompt}]
    for img in imagenes:
        partes.append({"inline_data": {"mime_type": "image/jpeg",
                                       "data": base64.b64encode(Path(img).read_bytes()).decode()}})
    cuerpo = json.dumps({
        "contents": [{"role": "user", "parts": partes}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()

    pedido = modelo
    modelo = _alternativos.get(pedido, pedido)
    global _saturado
    cambiado = False
    ultimo_error = None
    for intento in range(intentos):
        if modelo in _sin_cuota:
            break
        req = urllib.request.Request(URL.format(modelo=modelo), data=cuerpo, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-goog-api-key", clave)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                datos = json.loads(r.read())
            texto = datos["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texto)
        except urllib.error.HTTPError as e:
            detalle = e.read()[:400].decode("utf-8", "replace")
            ultimo_error = f"{modelo} → HTTP {e.code}: {detalle[:300]}"
            if es_cuota_agotada(e.code, detalle):
                # Reintentar no sirve: la cuota vuelve al día siguiente. Probamos otro modelo una vez.
                _sin_cuota.add(modelo)
                nuevo = None if cambiado else _cambiar_modelo(clave, pedido, modelo, "no tiene cuota disponible")
                if nuevo:
                    modelo, cambiado = nuevo, True
                    continue
                _saturado = True
                raise RuntimeError(f"Cuota gratuita de Gemini agotada por hoy ({modelo}); se usan las reglas simples.")
            if e.code == 404 and not cambiado:
                nuevo = _cambiar_modelo(clave, pedido, modelo, "no está disponible (actualiza config.json)")
                if nuevo:
                    modelo, cambiado = nuevo, True
                    continue
            if e.code not in (429, 500, 502, 503, 504):
                break
            # Saturado: a mitad de los intentos probamos con otro modelo flash.
            if intento == intentos // 2 - 1 and not cambiado:
                nuevo = _cambiar_modelo(clave, pedido, modelo, f"está saturado (HTTP {e.code})")
                if nuevo:
                    modelo, cambiado = nuevo, True
                    continue  # el modelo nuevo se prueba de inmediato
        except (KeyError, IndexError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as e:
            ultimo_error = f"{modelo} → {e!r}"
        if intento < intentos - 1:
            time.sleep(min(5 * 2 ** intento, 60))  # 5, 10, 20, 40, 60 s
    # Tras agotar los reintentos por saturación, los demás archivos de esta ejecución
    # se validan solo con la heurística (evita que un PR con muchos PDF tarde horas).
    if ultimo_error and any(f"HTTP {c}" in ultimo_error for c in (429, 500, 502, 503, 504)):
        _saturado = True
    raise RuntimeError(f"Gemini no respondió correctamente: {ultimo_error}")

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
_modelo_alternativo: str | None = None  # se recuerda durante la ejecución


def disponible() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def elegir_modelo_flash(clave: str) -> str | None:
    """Si el modelo configurado fue retirado, busca el «flash» estable más nuevo
    que admita generateContent. Así el proyecto sigue funcionando sin tocar nada."""
    req = urllib.request.Request(f"{BASE}/models?pageSize=200")
    req.add_header("x-goog-api-key", clave)
    with urllib.request.urlopen(req, timeout=60) as r:
        modelos = json.loads(r.read()).get("models", [])
    candidatos = []
    for m in modelos:
        nombre = m.get("name", "").removeprefix("models/")
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if not re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash", nombre):
            continue  # descarta lite, preview, image, tts, live, etc.
        candidatos.append((float(nombre.split("-")[1]), nombre))
    return max(candidatos)[1] if candidatos else None


def preguntar_json(prompt: str, modelo: str, imagenes: list[Path] = (), intentos: int = 3) -> dict:
    """Envía el prompt (y opcionalmente imágenes JPEG) y devuelve la respuesta
    como JSON. Lanza RuntimeError si no hay clave o la API falla."""
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

    global _modelo_alternativo
    modelo = _modelo_alternativo or modelo
    ultimo_error = None
    for intento in range(intentos):
        req = urllib.request.Request(URL.format(modelo=modelo), data=cuerpo, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-goog-api-key", clave)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                datos = json.loads(r.read())
            texto = datos["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texto)
        except urllib.error.HTTPError as e:
            ultimo_error = f"HTTP {e.code}: {e.read()[:300]!r}"
            if e.code == 404 and not _modelo_alternativo:
                nuevo = elegir_modelo_flash(clave)
                if nuevo and nuevo != modelo:
                    print(f"Aviso: el modelo {modelo} no está disponible; se usa {nuevo}. "
                          "Actualiza config.json → validacion.gemini_modelo.")
                    _modelo_alternativo = modelo = nuevo
                    continue
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (KeyError, IndexError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as e:
            ultimo_error = repr(e)
        time.sleep(5 * (intento + 1))
    raise RuntimeError(f"Gemini no respondió correctamente: {ultimo_error}")

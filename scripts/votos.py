"""Validación de votos hechos con el formulario de issue «Puntuar un apunte».

Cada voto es un issue con la etiqueta `voto`. Reglas:
- Puntuación de 1 a 5 y justificación obligatoria (mínimo configurable).
- El apunte debe existir en el repositorio.
- Un voto por cuenta de GitHub y apunte: si alguien vota de nuevo, cuenta el último.
- No se puede votar por un apunte propio (configurable).
- Opcional: Gemini revisa que la justificación sea una razón concreta y no "por gusto".

Uso en Actions (evento `issues`):  python scripts/votos.py --evento "$GITHUB_EVENT_PATH"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini  # noqa: E402
from comun import GitHub, cargar_config, leer_formulario, normalizar_texto  # noqa: E402

MARCADOR = "<!-- validacion-voto -->"
ETIQUETA_VOTO = "voto"
ETIQUETA_RECHAZADO = "voto-rechazado"
ETIQUETA_VALIDO = "voto-valido"
ETIQUETA_ANULADO = "voto-anulado"  # la pone el mantenedor a mano para anular un voto


def extraer_voto(issue: dict) -> dict:
    campos = leer_formulario(issue.get("body") or "")
    ruta = campos.get("apunte", "").strip().strip("`").strip()
    ruta = re.sub(r"^https?://\S+?/(?:blob|raw)/[^/]+/", "", ruta)  # por si pegan la URL
    m = re.search(r"[1-5]", campos.get("puntuacion", ""))
    return {
        "issue": issue["number"],
        "url": issue.get("html_url"),
        "usuario": (issue.get("user") or {}).get("login", ""),
        "ruta": ruta,
        "puntuacion": int(m.group(0)) if m else None,
        "justificacion": campos.get("justificacion", "").strip(),
        "fecha": issue.get("created_at"),
    }


def problemas_basicos(voto: dict, rutas_existentes: dict[str, dict], config: dict) -> list[str]:
    """Reglas deterministas (se aplican al validar y al reconstruir el ranking)."""
    cfg = config["votos"]
    errores = []
    if voto["ruta"] not in rutas_existentes:
        errores.append(f"El apunte `{voto['ruta'] or '(vacío)'}` no existe. Usa el botón «Puntuar» de la página del ranking.")
    if voto["puntuacion"] is None:
        errores.append("Falta la puntuación (1 a 5 estrellas).")
    j = voto["justificacion"]
    palabras = re.findall(r"\w+", j)
    if len(j) < cfg["min_caracteres_justificacion"] or len(palabras) < cfg["min_palabras_justificacion"]:
        errores.append(f"La justificación es muy corta: escribe al menos {cfg['min_palabras_justificacion']} palabras "
                       f"({cfg['min_caracteres_justificacion']} caracteres) explicando por qué das esa puntuación.")
    elif len({normalizar_texto(p) for p in palabras}) < max(4, len(palabras) // 4) or re.search(r"(.)\1{6,}", j):
        errores.append("La justificación parece texto de relleno. Explica qué tiene de bueno o malo el apunte.")
    if not cfg.get("permitir_autovoto", False):
        apunte = rutas_existentes.get(voto["ruta"])
        if apunte and apunte.get("autor_login") and apunte["autor_login"].lower() == voto["usuario"].lower():
            errores.append("No puedes puntuar tus propios apuntes.")
    return errores


def revisar_justificacion_gemini(voto: dict, config: dict) -> str | None:
    """Devuelve un motivo de rechazo o None si la justificación es aceptable."""
    if not (config["votos"].get("revisar_justificacion_con_gemini") and gemini.disponible()):
        return None
    prompt = f"""Moderas votos de apuntes universitarios de Estadística (UCR). Un estudiante dio
{voto['puntuacion']}/5 estrellas al apunte "{voto['ruta']}" con esta justificación:
\"\"\"{voto['justificacion'][:2000]}\"\"\"
Acepta si da al menos una razón relacionada con el apunte (claridad, orden, completitud, errores,
ejemplos, letra legible, utilidad para estudiar, cobertura de temas, etc.), aunque sea breve o informal.
Rechaza solo si es claramente por gusto personal sin razones ("no me cae bien el autor", "porque sí"),
ofensiva, spam o sin relación con el apunte.
Responde SOLO JSON: {{"aceptable": bool, "motivo": "explicación breve en español"}}"""
    try:
        res = gemini.preguntar_json(prompt, config["validacion"]["gemini_modelo"])
    except Exception as e:  # si Gemini falla, no bloqueamos el voto
        print(f"Aviso: Gemini no disponible: {e}")
        return None
    return None if res.get("aceptable", True) else (res.get("motivo") or "La justificación no explica la puntuación.")


def _rutas_existentes() -> dict[str, dict]:
    from indice import listar_apuntes
    gh = GitHub() if os.environ.get("GITHUB_TOKEN") else None
    return {a["ruta"]: a for a in listar_apuntes(gh)}


def procesar_evento(ruta_evento: str) -> int:
    evento = json.loads(Path(ruta_evento).read_text(encoding="utf-8"))
    issue = evento["issue"]
    etiquetas = {e["name"] for e in issue.get("labels", [])}
    es_voto = ETIQUETA_VOTO in etiquetas or (issue.get("title") or "").lower().startswith("voto:")
    if not es_voto or ETIQUETA_ANULADO in etiquetas:
        print("No es un voto (o fue anulado); nada que hacer.")
        return 0

    gh, config = GitHub(), cargar_config()
    if ETIQUETA_VOTO not in etiquetas:  # el formulario no la puso (p. ej. la etiqueta no existía)
        gh.poner_etiquetas(issue["number"], poner=[ETIQUETA_VOTO])
    voto = extraer_voto(issue)
    errores = problemas_basicos(voto, _rutas_existentes(), config)

    edad_min = config["votos"].get("edad_minima_cuenta_dias", 0)
    if not errores and edad_min:
        creada = gh.get(f"/users/{voto['usuario']}")["created_at"]
        dias = (datetime.now(timezone.utc) - datetime.fromisoformat(creada.replace("Z", "+00:00"))).days
        if dias < edad_min:
            errores.append(f"Tu cuenta de GitHub debe tener al menos {edad_min} días para votar (evita votos duplicados).")
    if not errores:
        motivo = revisar_justificacion_gemini(voto, config)
        if motivo:
            errores.append(f"La justificación no parece explicar la puntuación: {motivo}")

    if errores:
        texto = ("### ❌ Voto no registrado\n\n" + "\n".join(f"- {e}" for e in errores) +
                 "\n\nPuedes **editar este issue** (menú «…» → *Edit*) para corregirlo; se revisará de nuevo automáticamente.")
        gh.comentar(voto["issue"], texto, MARCADOR)
        gh.poner_etiquetas(voto["issue"], poner=[ETIQUETA_RECHAZADO], quitar=[ETIQUETA_VALIDO])
        if issue.get("state") == "open":
            gh.cerrar_issue(voto["issue"], "not_planned")
        print(texto)
        return 0

    estrellas = "⭐" * voto["puntuacion"]
    texto = (f"### ✅ ¡Gracias! Tu voto quedó registrado\n\n{estrellas} ({voto['puntuacion']}/5) para `{voto['ruta']}`.\n\n"
             "El ranking se actualiza en un par de minutos. Si vuelves a votar por este apunte, cuenta solo tu voto más reciente.")
    gh.comentar(voto["issue"], texto, MARCADOR)
    gh.poner_etiquetas(voto["issue"], poner=[ETIQUETA_VALIDO], quitar=[ETIQUETA_RECHAZADO])
    if issue.get("state") == "open":
        gh.cerrar_issue(voto["issue"], "completed")
    print(texto)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--evento", required=True, help="Ruta al JSON del evento (GITHUB_EVENT_PATH)")
    sys.exit(procesar_evento(ap.parse_args().evento))

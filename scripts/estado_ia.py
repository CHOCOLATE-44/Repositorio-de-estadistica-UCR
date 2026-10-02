"""Lleva la cuenta de las consultas a Gemini y la publica en el issue «🤖 Estado de la IA».

Google no informa cuánta cuota queda, así que la contamos nosotros: cada ejecución
que usa Gemini suma sus consultas al issue (etiqueta `estado-ia`). La cuota gratuita
se reinicia a medianoche, hora del Pacífico (EE. UU.); la página del ranking lee este
issue para que todos vean cuánto queda antes de subir muchas cosas de golpe.

Uso:  python scripts/estado_ia.py   (solo vuelve a dibujar el issue; lo corre un cron)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import GitHub, cargar_config  # noqa: E402

ETIQUETA = "estado-ia"
TITULO = "🤖 Estado de la IA (uso de hoy)"
PACIFICO = ZoneInfo("America/Los_Angeles")
COSTA_RICA = ZoneInfo("America/Costa_Rica")
DATOS = re.compile(r"<!-- estado-ia (\{.*?\}) -->", re.S)


def dia_de_cuota(ahora: datetime | None = None) -> str:
    """Fecha del «día» de la cuota: cambia a medianoche del Pacífico."""
    return (ahora or datetime.now(timezone.utc)).astimezone(PACIFICO).date().isoformat()


def proximo_reinicio(ahora: datetime | None = None) -> datetime:
    local = (ahora or datetime.now(timezone.utc)).astimezone(PACIFICO)
    manana = (local + timedelta(days=1)).date()
    return datetime(manana.year, manana.month, manana.day, tzinfo=PACIFICO).astimezone(timezone.utc)


def usos(config: dict) -> list[tuple[str, str]]:
    """[(modelo, para qué se usa)] según config.json."""
    val = config["validacion"]
    pares = [(val.get("gemini_modelo"), "Validar apuntes"),
             (val.get("gemini_modelo_votos"), "Revisar votos"),
             (val.get("gemini_modelo_preguntas"), "Responder preguntas")]
    salida: dict[str, list[str]] = {}
    for modelo, uso in pares:
        if modelo:
            salida.setdefault(modelo, []).append(uso)
    return [(m, " y ".join(u)) for m, u in salida.items()]


def combinar(estado: dict, consultas: dict[str, int], agotados: set[str], ahora: datetime | None = None) -> dict:
    """Suma las consultas nuevas; si cambió el día de la cuota, empieza de cero."""
    dia = dia_de_cuota(ahora)
    if estado.get("dia") != dia:
        estado = {"dia": dia, "consultas": {}, "agotados": []}
    for modelo, n in consultas.items():
        estado["consultas"][modelo] = estado["consultas"].get(modelo, 0) + n
    estado["agotados"] = sorted(set(estado.get("agotados", [])) | agotados)
    estado["actualizado"] = (ahora or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    estado["reinicio"] = proximo_reinicio(ahora).isoformat()
    return estado


def cuerpo(estado: dict, config: dict) -> str:
    limites = config.get("ia", {}).get("limites_diarios", {})
    reinicio = datetime.fromisoformat(estado["reinicio"]).astimezone(COSTA_RICA)
    filas = []
    for modelo, uso in usos(config):
        n = estado["consultas"].get(modelo, 0)
        limite = limites.get(modelo)
        if modelo in estado["agotados"]:
            semaforo = "🔴 Agotada"
        elif limite and n >= 0.8 * limite:
            semaforo = "🟡 Queda poco"
        else:
            semaforo = "🟢 Disponible"
        usado = f"{n} de {limite}" if limite else str(n)
        filas.append(f"| {uso} | `{modelo}` | {usado} | {semaforo} |")
    datos = json.dumps(estado, ensure_ascii=False)
    return f"""Este issue lo actualiza un robot: **no lo cierre ni lo edite**.

La IA (Gemini, cuenta gratuita de Google) tiene un **límite de consultas por día**. Cada apunte que se
valida, cada voto que se revisa y cada pregunta gastan una consulta. Si se acaba, el robot sigue
funcionando con reglas simples, que son menos precisas, hasta que se reinicie.

**Se reinicia:** {reinicio.strftime('%d/%m a las %H:%M')} (hora de Costa Rica).

| Uso | Modelo | Consultas hoy | Estado |
|---|---|---|---|
{chr(10).join(filas)}

💡 Si va a subir muchos archivos y queda poco, espere al reinicio.

<sub>Conteo aproximado hecho por el robot. Última actualización: {estado['actualizado']} (UTC).</sub>
<!-- estado-ia {datos} -->
"""


def _issue(gh: GitHub) -> dict | None:
    for i in gh.paginar(f"/repos/{gh.repo}/issues?labels={ETIQUETA}&state=open"):
        return i
    return None


def registrar(gh: GitHub, consultas: dict[str, int], agotados: set[str] = frozenset()) -> None:
    config = cargar_config()
    issue = _issue(gh)
    previo = {}
    if issue:
        m = DATOS.search(issue.get("body") or "")
        if m:
            try:
                previo = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    texto = cuerpo(combinar(previo, consultas, set(agotados)), config)
    if issue:
        gh.patch(f"/repos/{gh.repo}/issues/{issue['number']}", {"body": texto})
    else:
        gh.post(f"/repos/{gh.repo}/issues", {"title": TITULO, "body": texto, "labels": [ETIQUETA]})


if __name__ == "__main__":
    registrar(GitHub(), {})
    print("Estado de la IA actualizado.")

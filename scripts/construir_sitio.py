"""Construye el sitio de GitHub Pages en `_site/`.

Genera `_site/data/puntuaciones.json` (el «scores.json» público) a partir de:
- los archivos en `apuntes/` (inventario + historial de git), y
- los issues con etiqueta `voto` (se revalidan con las reglas deterministas).
Luego copia la página estática de `sitio/`.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import RAIZ, GitHub, cargar_config, cargar_cursos  # noqa: E402
from indice import listar_apuntes  # noqa: E402
from votos import (ETIQUETA_ANULADO, ETIQUETA_RECHAZADO, ETIQUETA_VOTO,  # noqa: E402
                   extraer_voto, problemas_basicos)


def recolectar_votos(gh: GitHub | None, rutas: dict[str, dict], config: dict) -> list[dict]:
    if gh is None:
        return []
    ultimos: dict[tuple[str, str], dict] = {}
    for issue in gh.paginar(f"/repos/{gh.repo}/issues?labels={ETIQUETA_VOTO}&state=all&sort=created&direction=asc"):
        if "pull_request" in issue:
            continue
        etiquetas = {e["name"] for e in issue.get("labels", [])}
        if etiquetas & {ETIQUETA_RECHAZADO, ETIQUETA_ANULADO}:
            continue
        voto = extraer_voto(issue)
        if problemas_basicos(voto, rutas, config):
            continue
        # Un voto por (usuario, apunte): gana el más reciente.
        ultimos[(voto["usuario"].lower(), voto["ruta"])] = voto
    return list(ultimos.values())


def agregar(apuntes: list[dict], votos: list[dict], config: dict) -> None:
    c, m = config["ranking"]["votos_previos"], config["ranking"]["media_previa"]
    por_ruta: dict[str, list[dict]] = {}
    for v in votos:
        por_ruta.setdefault(v["ruta"], []).append(v)
    for a in apuntes:
        vs = sorted(por_ruta.get(a["ruta"], []), key=lambda v: v["fecha"], reverse=True)
        n, suma = len(vs), sum(v["puntuacion"] for v in vs)
        a["votos"] = n
        a["promedio"] = round(suma / n, 2) if n else None
        # Promedio bayesiano: evita que 1 voto de 5⭐ supere a 30 votos de 4.8⭐.
        a["puntaje_ranking"] = round((c * m + suma) / (c + n), 3)
        a["distribucion"] = {str(k): sum(1 for v in vs if v["puntuacion"] == k) for k in range(1, 6)}
        a["opiniones"] = [{k: v[k] for k in ("usuario", "puntuacion", "justificacion", "fecha", "url")} for v in vs]


def calcular_datos() -> dict:
    """Inventario de apuntes + votos agregados (lo que se publica como puntuaciones.json)."""
    config, cursos = cargar_config(), cargar_cursos()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    gh = GitHub() if os.environ.get("GITHUB_TOKEN") and repo else None
    apuntes = listar_apuntes(gh)
    rutas = {a["ruta"]: a for a in apuntes}
    votos = recolectar_votos(gh, rutas, config)
    agregar(apuntes, votos, config)
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repositorio": repo,
        "rama": os.environ.get("RAMA_PRINCIPAL", "main"),
        "config": {"min_caracteres_justificacion": config["votos"]["min_caracteres_justificacion"]},
        "cursos": [{k: c.get(k) for k in ("sigla", "nombre", "carpeta", "ciclo", "siglas_equivalentes", "alias")} for c in cursos],
        "apuntes": sorted(apuntes, key=lambda a: (-a["puntaje_ranking"], a["titulo"])),
    }


VISIBLES_EN_SITIO = {"pdf", "jpg", "jpeg", "png"}


def main():
    datos = calcular_datos()
    salida = RAIZ / "_site"
    if salida.exists():
        shutil.rmtree(salida)
    shutil.copytree(RAIZ / "sitio", salida)
    # Los PDF e imágenes se publican también en el sitio: así «Abrir» los muestra con el visor
    # del navegador (el de GitHub, en el celular, solo deja ver la primera página). Los HTML no:
    # podrían ejecutar código dentro del sitio.
    for a in datos["apuntes"]:
        if a["formato"] in VISIBLES_EN_SITIO:
            destino = salida / a["ruta"]
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RAIZ / a["ruta"], destino)
    (salida / "data").mkdir(exist_ok=True)
    (salida / "data" / "puntuaciones.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Sitio generado: {len(datos['apuntes'])} apuntes, {sum(a['votos'] for a in datos['apuntes'])} votos válidos.")


if __name__ == "__main__":
    main()

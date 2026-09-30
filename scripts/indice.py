"""Inventario de apuntes a partir de la carpeta `apuntes/` y del historial de git."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from comun import CARPETA_APUNTES, RAIZ, GitHub, cargar_config, curso_por_carpeta, cargar_cursos

NOREPLY = re.compile(r"^(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$")


def titulo_desde_archivo(nombre: str) -> str:
    base = re.sub(r"[-_]+", " ", Path(nombre).stem).strip()
    return base[:1].upper() + base[1:]


def _historial_altas() -> dict[str, dict]:
    """{ruta: {sha, fecha, nombre, email}} del commit que agregó cada archivo."""
    try:
        salida = subprocess.run(
            ["git", "log", "--diff-filter=A", "--reverse", "--format=@@%H|%aI|%an|%ae",
             "--name-only", "--", CARPETA_APUNTES],
            cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    altas, actual = {}, None
    for linea in salida.splitlines():
        if linea.startswith("@@"):
            sha, fecha, nombre, email = linea[2:].split("|", 3)
            actual = {"sha": sha, "fecha": fecha, "nombre": nombre, "email": email}
        elif linea.strip() and actual:
            altas.setdefault(linea.strip(), actual)
    return altas


def _login(alta: dict, gh: GitHub | None, cache: dict[str, str | None]) -> str | None:
    """Usuario de GitHub que hizo el commit que agregó el archivo."""
    m = NOREPLY.match(alta.get("email", ""))
    if m:
        return m.group(1)
    if gh and alta.get("sha"):
        if alta["sha"] not in cache:
            try:
                cache[alta["sha"]] = (gh.get(f"/repos/{gh.repo}/commits/{alta['sha']}").get("author") or {}).get("login")
            except Exception:
                cache[alta["sha"]] = None
        return cache[alta["sha"]]
    return None


def autor_de(ruta: str, gh: GitHub | None = None) -> str | None:
    """Quién subió originalmente el apunte `ruta` (None si no se sabe)."""
    return _login(_historial_altas().get(ruta, {}), gh, {})


def listar_apuntes(gh: GitHub | None = None) -> list[dict]:
    config, cursos = cargar_config(), cargar_cursos()
    extensiones = set(config["validacion"]["extensiones_permitidas"])
    altas = _historial_altas()
    cache_login: dict[str, str | None] = {}
    apuntes = []
    for archivo in sorted((RAIZ / CARPETA_APUNTES).glob("*/*")):
        if not archivo.is_file() or archivo.name.lower() == "readme.md":
            continue
        if archivo.suffix.lower() not in extensiones:
            continue
        curso = curso_por_carpeta(archivo.parent.name, cursos)
        if not curso:
            continue
        ruta = archivo.relative_to(RAIZ).as_posix()
        alta = altas.get(ruta, {})
        login = _login(alta, gh, cache_login)
        fecha = alta.get("fecha") or datetime.fromtimestamp(archivo.stat().st_mtime, timezone.utc).isoformat()
        apuntes.append({
            "ruta": ruta,
            "curso": curso["sigla"],
            "carpeta": curso["carpeta"],
            "titulo": titulo_desde_archivo(archivo.name),
            "formato": archivo.suffix.lower().lstrip("."),
            "tamano_kb": round(archivo.stat().st_size / 1024),
            "fecha": fecha,
            "autor": login or alta.get("nombre") or "desconocido",
            "autor_login": login,
        })
    return apuntes

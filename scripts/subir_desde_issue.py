"""Convierte un issue «Subir un apunte» en un archivo listo para un Pull Request.

Descarga el PDF adjunto, lo coloca en `apuntes/<curso>/` y deja en GITHUB_OUTPUT
la ruta, la rama y el título. El workflow se encarga del commit y del PR.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import (CARPETA_APUNTES, RAIZ, GitHub, cargar_config, cargar_cursos,  # noqa: E402
                   curso_por_sigla, escribir_salida, leer_formulario, slug)

ADJUNTO = re.compile(
    r"https://github\.com/(?:user-attachments/files|[\w.-]+/[\w.-]+/files)/\d+/[^\s)\]\"'>]+", re.I)


def fallar(gh: GitHub, numero: int, mensaje: str):
    gh.comentar(numero, f"### ❌ No se pudo procesar el apunte\n\n{mensaje}\n\n"
                        "Edita este issue para corregirlo y se volverá a intentar automáticamente.",
                "<!-- subir-apunte -->")
    escribir_salida("ok", "false")
    print(mensaje)
    sys.exit(0)


def main():
    evento = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = evento["issue"]
    gh, config, cursos = GitHub(), cargar_config(), cargar_cursos()
    numero, usuario = issue["number"], issue["user"]
    campos = leer_formulario(issue.get("body") or "")

    sigla = campos.get("curso", "").split("—")[0].strip()
    curso = curso_por_sigla(sigla, cursos) if sigla else None
    if not curso:
        fallar(gh, numero, "No se reconoció el curso seleccionado.")
    titulo = campos.get("titulo", "").strip()
    if len(titulo) < 3:
        fallar(gh, numero, "Falta el título del apunte.")

    enlaces = ADJUNTO.findall(campos.get("archivo", ""))
    permitidas = config["validacion"]["extensiones_permitidas"]
    enlaces = [e for e in enlaces if Path(e.split("?")[0]).suffix.lower() in permitidas]
    if len(enlaces) != 1:
        fallar(gh, numero, f"Adjunta exactamente **un** archivo ({', '.join(permitidas)}) en el campo «Archivo» "
                           "arrastrándolo al cuadro de texto y esperando a que termine de subir.")
    ext = Path(enlaces[0].split("?")[0]).suffix.lower()

    carpeta = RAIZ / CARPETA_APUNTES / curso["carpeta"]
    base = f"{slug(titulo, 50)}-{slug(usuario['login'], 30)}"
    destino = carpeta / f"{base}{ext}"
    i = 2
    while destino.exists():
        destino = carpeta / f"{base}-{i}{ext}"
        i += 1
    try:
        gh.descargar(enlaces[0], destino, max_bytes=config["validacion"]["tamano_maximo_mb"] * 1_000_000)
    except Exception as e:
        fallar(gh, numero, f"No se pudo descargar el archivo: {e}")
    if ext == ".pdf" and not destino.read_bytes().startswith(b"%PDF"):
        destino.unlink()
        fallar(gh, numero, "El archivo adjunto no es un PDF válido.")

    ruta = destino.relative_to(RAIZ).as_posix()
    escribir_salida("ok", "true")
    escribir_salida("ruta", ruta)
    escribir_salida("rama", f"apunte/issue-{numero}")
    escribir_salida("curso", curso["sigla"])
    escribir_salida("autor_email", f"{usuario['id']}+{usuario['login']}@users.noreply.github.com")
    escribir_salida("autor_nombre", usuario["login"])
    print(f"Archivo listo: {ruta}")


if __name__ == "__main__":
    main()

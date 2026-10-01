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

MAX_ARCHIVOS = 20

ADJUNTO = re.compile(
    r"https://github\.com/(?:user-attachments/files|[\w.-]+/[\w.-]+/files)/\d+/[^\s)\]\"'>]+", re.I)


def adjuntos_de(texto: str) -> list[tuple[str, str]]:
    """[(nombre, url)] de los archivos adjuntos. GitHub los escribe como
    [nombre.pdf](https://github.com/user-attachments/files/…); si no hay nombre,
    se usa el final de la URL."""
    vistos, salida = set(), []
    for m in re.finditer(r"\[([^\]]*)\]\((" + ADJUNTO.pattern + r")\)|(" + ADJUNTO.pattern + r")", texto, re.I):
        url = m.group(2) or m.group(3)
        if url in vistos:
            continue
        vistos.add(url)
        nombre = (m.group(1) or "").strip() or url.split("?")[0].rsplit("/", 1)[-1]
        salida.append((nombre, url))
    return salida


def fallar(gh: GitHub, numero: int, mensaje: str):
    gh.comentar(numero, f"### ❌ No se pudo procesar el apunte\n\n{mensaje}\n\n"
                        "Edite este issue para corregirlo y se volverá a intentar automáticamente.",
                "<!-- subir-apunte -->")
    escribir_salida("ok", "false")
    print(mensaje)
    sys.exit(0)


def main():
    gh, config, cursos = GitHub(), cargar_config(), cargar_cursos()
    manual = os.environ.get("ISSUE_MANUAL", "").strip()
    if manual:  # reproceso manual (workflow_dispatch)
        issue = gh.get(f"/repos/{gh.repo}/issues/{int(manual)}")
    else:
        issue = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))["issue"]
    numero, usuario = issue["number"], issue["user"]
    escribir_salida("issue", str(numero))
    escribir_salida("titulo", re.sub(r"^\s*apunte:\s*", "", issue.get("title") or "", flags=re.I).replace("\n", " ")[:100])
    if "subir-apunte" not in {e["name"] for e in issue.get("labels", [])}:
        gh.poner_etiquetas(numero, poner=["subir-apunte"])
    campos = leer_formulario(issue.get("body") or "")

    sigla = campos.get("curso", "").split("—")[0].strip()
    curso = curso_por_sigla(sigla, cursos) if sigla else None
    if not curso:
        fallar(gh, numero, "No se reconoció el curso seleccionado.")
    titulo = campos.get("titulo", "").strip()
    if len(titulo) < 3:
        fallar(gh, numero, "Falta el título del apunte.")

    permitidas = config["validacion"]["extensiones_permitidas"]
    adjuntos = [(nombre, url) for nombre, url in adjuntos_de(campos.get("archivo", ""))
                if Path(url.split("?")[0]).suffix.lower() in permitidas]
    if not adjuntos:
        fallar(gh, numero, f"No encontré archivos ({', '.join(permitidas)}) en el campo «Archivo». "
                           "Arrástrelos al cuadro de texto y espere a que terminen de subir antes de enviar.")
    if len(adjuntos) > MAX_ARCHIVOS:
        fallar(gh, numero, f"Adjunte como máximo {MAX_ARCHIVOS} archivos por formulario.")

    carpeta = RAIZ / CARPETA_APUNTES / curso["carpeta"]
    login = slug(usuario["login"], 30)
    rutas = []
    for nombre, url in adjuntos:
        ext = Path(url.split("?")[0]).suffix.lower()
        # Un archivo: se titula con el título del formulario. Varios: cada uno con su nombre.
        base = f"{slug(titulo if len(adjuntos) == 1 else Path(nombre).stem, 60)}-{login}"
        destino = carpeta / f"{base}{ext}"
        i = 2
        while destino.exists():
            destino = carpeta / f"{base}-{i}{ext}"
            i += 1
        try:
            gh.descargar(url, destino, max_bytes=config["validacion"]["tamano_maximo_mb"] * 1_000_000)
        except Exception as e:
            fallar(gh, numero, f"No se pudo descargar «{nombre}»: {e}")
        if ext == ".pdf" and not destino.read_bytes().startswith(b"%PDF"):
            destino.unlink()
            fallar(gh, numero, f"«{nombre}» no es un PDF válido.")
        rutas.append(destino.relative_to(RAIZ).as_posix())

    escribir_salida("ok", "true")
    escribir_salida("carpeta", carpeta.relative_to(RAIZ).as_posix())
    escribir_salida("archivos", str(len(rutas)))
    escribir_salida("rama", f"apunte/issue-{numero}")
    escribir_salida("curso", curso["sigla"])
    escribir_salida("autor_email", f"{usuario['id']}+{usuario['login']}@users.noreply.github.com")
    escribir_salida("autor_nombre", usuario["login"])
    print("Archivos listos:\n" + "\n".join(rutas))

if __name__ == "__main__":
    main()

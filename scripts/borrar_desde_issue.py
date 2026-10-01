"""Procesa un issue «Borrar un apunte».

Comprueba que quien abrió el issue subió ese apunte (o es mantenedor) y deja en
GITHUB_OUTPUT la ruta y la rama. El workflow borra el archivo y abre el PR, que
la validación publica sola.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import CARPETA_APUNTES, RAIZ, GitHub, escribir_salida, leer_formulario  # noqa: E402
from indice import autor_de  # noqa: E402
from validar_apunte import revisar_permiso  # noqa: E402


def terminar(gh: GitHub, numero: int, mensaje: str):
    gh.comentar(numero, f"### ❌ No se pudo borrar el apunte\n\n{mensaje}", "<!-- borrar-apunte -->")
    gh.cerrar_issue(numero, "not_planned")
    escribir_salida("ok", "false")
    print(mensaje)
    sys.exit(0)


def ruta_de(texto: str) -> str:
    """Acepta la ruta tal cual o un enlace de GitHub que la contenga."""
    texto = re.sub(r"[`<>\s]", "", texto or "")
    m = re.search(rf"{CARPETA_APUNTES}/[^?#]+", texto)
    return m.group(0) if m else texto


def main():
    gh = GitHub()
    manual = os.environ.get("ISSUE_MANUAL", "").strip()
    if manual:
        issue = gh.get(f"/repos/{gh.repo}/issues/{int(manual)}")
    else:
        issue = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))["issue"]
    numero, usuario = issue["number"], issue["user"]["login"]
    escribir_salida("issue", str(numero))

    ruta = ruta_de(leer_formulario(issue.get("body") or "").get("apunte", ""))
    partes = PurePosixPath(ruta).parts
    if (len(partes) != 3 or partes[0] != CARPETA_APUNTES or ".." in partes
            or partes[2].lower() == "readme.md" or not (RAIZ / ruta).is_file()):
        terminar(gh, numero, f"No se encontró el apunte `{ruta}`. Use el botón **Borrar** de la página del ranking.")

    error = revisar_permiso("removed", usuario, issue.get("author_association", "NONE"), autor_de(ruta, gh))
    if error:
        terminar(gh, numero, error)

    escribir_salida("ok", "true")
    escribir_salida("ruta", ruta)
    escribir_salida("rama", f"borrar/issue-{numero}")


if __name__ == "__main__":
    main()

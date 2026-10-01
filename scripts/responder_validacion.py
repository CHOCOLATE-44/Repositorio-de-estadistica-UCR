"""Atiende la respuesta de quien subió un apunte rechazado por la validación.

Comandos (comentario en el PR o en el issue de subida, solo el autor o un mantenedor):
  /contenido-nuevo [explicación]  → el tema sí es del curso aunque no esté en la carta:
                                    se marca «revision-manual» y se avisa al mantenedor.
  /curso XS-0122                   → curso equivocado: se mueve el apunte a esa carpeta
                                    y se valida de nuevo.
Uso en Actions (evento issue_comment): python scripts/responder_validacion.py --evento "$GITHUB_EVENT_PATH"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import (CARPETA_APUNTES, RAIZ, GitHub, cargar_cursos,  # noqa: E402
                   curso_por_carpeta, curso_por_sigla)
from validar_apunte import ETIQUETA_REVISION, ROLES_MANTENEDOR, autor_real, issue_de_subida  # noqa: E402

MARCADOR = "<!-- respuesta-validacion -->"


def leer_comando(texto: str) -> tuple[str, str] | None:
    """('contenido-nuevo', explicación) | ('curso', sigla) | None."""
    primera, _, resto = (texto or "").strip().partition("\n")
    m = re.match(r"^/contenido[-_ ]nuevo\b\s*(.*)$", primera.strip(), re.I)
    if m:
        return "contenido-nuevo", (m.group(1) + "\n" + resto).strip()
    m = re.match(r"^/curso\s+([A-Za-z]{2})\s*[-_]?\s*(\d{4})\b", primera.strip(), re.I)
    if m:
        return "curso", f"{m.group(1).upper()}-{m.group(2)}"
    return None


def puede_responder(usuario: str, asociacion: str, autor: str) -> bool:
    return asociacion in ROLES_MANTENEDOR or usuario.lower() == autor.lower()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, check=True, capture_output=True, text=True).stdout


def buscar_pr(gh: GitHub, issue: dict) -> dict | None:
    if issue.get("pull_request"):
        return gh.get(f"/repos/{gh.repo}/pulls/{issue['number']}")
    dueno = gh.repo.split("/")[0]
    prs = gh.get(f"/repos/{gh.repo}/pulls?state=open&head={dueno}:apunte/issue-{issue['number']}")
    return prs[0] if prs else None


def contenido_nuevo(gh: GitHub, pr: dict, usuario: str, explicacion: str) -> str:
    numero = pr["number"]
    dueno = gh.repo.split("/")[0]
    gh.poner_etiquetas(numero, poner=[ETIQUETA_REVISION])
    try:
        gh.post(f"/repos/{gh.repo}/pulls/{numero}/requested_reviewers", {"reviewers": [dueno]})
    except Exception:
        pass  # p. ej. si el dueño es el autor del PR
    cita = "\n".join(f"> {linea}" for linea in explicacion.splitlines()) if explicacion else "> (sin explicación)"
    gh.comentar(numero, f"### 👀 Revisión manual solicitada\n\n@{usuario} indica que es **contenido nuevo del curso** "
                        f"que no aparece en la carta al estudiante:\n\n{cita}\n\n"
                        f"@{dueno}: revise el apunte. Si corresponde, fusione el PR (con *bypass* de la regla de la rama); "
                        "si no, ciérrelo explicando el motivo.", MARCADOR)
    return (f"✅ Listo, @{usuario}: marqué el PR #{numero} para **revisión manual**. "
            "El mantenedor lo revisará y le responderá allí.")


def cambiar_curso(gh: GitHub, pr: dict, usuario: str, sigla: str) -> str:
    cursos = cargar_cursos()
    nuevo = curso_por_sigla(sigla, cursos)
    if not nuevo:
        return f"❌ No reconozco el curso `{sigla}`. Revise la sigla (por ejemplo `/curso XS-0122`)."
    numero, rama = pr["number"], pr["head"]["ref"]
    if (pr["head"].get("repo") or {}).get("full_name") != gh.repo:
        return ("❌ Este PR viene de su copia (fork) del repositorio, así que el robot no puede mover el archivo. "
                f"Muévalo usted a `{CARPETA_APUNTES}/{nuevo['carpeta']}/` y vuelva a hacer push.")

    archivos = [f for f in gh.paginar(f"/repos/{gh.repo}/pulls/{numero}/files")
                if f["status"] != "removed" and len(PurePosixPath(f["filename"]).parts) == 3
                and PurePosixPath(f["filename"]).parts[0] == CARPETA_APUNTES
                and PurePosixPath(f["filename"]).name.lower() != "readme.md"]
    movidos = []
    git("fetch", "origin", rama)
    git("checkout", "-B", rama, f"origin/{rama}")
    for f in archivos:
        origen = PurePosixPath(f["filename"])
        if origen.parts[1] == nuevo["carpeta"]:
            continue
        destino = PurePosixPath(CARPETA_APUNTES, nuevo["carpeta"], origen.name)
        (RAIZ / destino).parent.mkdir(parents=True, exist_ok=True)
        git("mv", str(origen), str(destino))
        movidos.append((origen, destino))
    if not movidos:
        return f"ℹ️ Los archivos ya están en `{nuevo['sigla']}`; no hay nada que mover."

    git("-c", "user.name=github-actions[bot]",
        "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "-m", f"Mover apunte a {nuevo['sigla']} (pedido por @{usuario})")
    git("push", "origin", f"HEAD:{rama}")

    # En subidas por formulario, el issue también debe decir el curso nuevo (por si se edita después).
    issue = issue_de_subida(pr)
    if issue:
        cuerpo = gh.get(f"/repos/{gh.repo}/issues/{issue}").get("body") or ""
        cuerpo = re.sub(r"(### Curso\s*\n\s*\n)[^\n]*", rf"\g<1>{nuevo['sigla']} — {nuevo['nombre']}", cuerpo, count=1)
        gh.patch(f"/repos/{gh.repo}/issues/{issue}", {"body": cuerpo})
    anterior = curso_por_carpeta(movidos[0][0].parts[1], cursos)
    gh.patch(f"/repos/{gh.repo}/pulls/{numero}",
             {"title": re.sub(r"^\[[^\]]+\]", f"[{nuevo['sigla']}]", pr["title"])})
    # El push del robot no dispara la validación por sí solo: la lanzamos.
    base = pr["base"]["ref"]
    gh.post(f"/repos/{gh.repo}/actions/workflows/validar-apunte.yml/dispatches",
            {"ref": base, "inputs": {"pr": str(numero)}})
    lista = "\n".join(f"- `{o}` → `{d}`" for o, d in movidos)
    return (f"✅ Listo, @{usuario}: moví el apunte de **{anterior['sigla'] if anterior else '?'}** a "
            f"**{nuevo['sigla']} {nuevo['nombre']}**:\n\n{lista}\n\nEl robot lo está validando de nuevo en el PR #{numero}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evento", required=True)
    evento = json.loads(Path(ap.parse_args().evento).read_text(encoding="utf-8"))
    comentario, issue = evento["comment"], evento["issue"]
    comando = leer_comando(comentario.get("body", ""))
    if not comando:
        return
    gh = GitHub()
    usuario = comentario["user"]["login"]
    pr = buscar_pr(gh, issue)
    if not pr:
        gh.comentar(issue["number"], "❌ No encontré un Pull Request abierto de este apunte.", MARCADOR)
        return
    autor = autor_real(gh, pr)
    if not puede_responder(usuario, comentario.get("author_association", "NONE"), autor):
        gh.comentar(issue["number"], f"❌ @{usuario}, solo @{autor} (quien subió el apunte) o un mantenedor "
                                     "pueden usar este comando.", MARCADOR)
        return
    tipo, valor = comando
    respuesta = contenido_nuevo(gh, pr, usuario, valor) if tipo == "contenido-nuevo" else cambiar_curso(gh, pr, usuario, valor)
    gh.comentar(issue["number"], respuesta, MARCADOR)
    if issue["number"] != pr["number"] and tipo == "curso":
        gh.comentar(pr["number"], respuesta, MARCADOR)
    print(respuesta)


if __name__ == "__main__":
    main()

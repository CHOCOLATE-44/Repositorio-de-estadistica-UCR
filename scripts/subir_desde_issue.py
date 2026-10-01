"""Convierte un issue «Subir un apunte» en un archivo listo para un Pull Request.

Descarga el PDF adjunto, lo coloca en `apuntes/<curso>/` y deja en GITHUB_OUTPUT
la ruta, la rama y el título. El workflow se encarga del commit y del PR.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comun import (CARPETA_APUNTES, RAIZ, GitHub, cargar_config, cargar_cursos,  # noqa: E402
                   curso_por_sigla, escribir_salida, leer_formulario, slug)

MAX_ARCHIVOS = 20
IMAGENES = {".jpg", ".jpeg", ".png"}
LADO_MAXIMO = 2000  # px: suficiente para leer letra a mano sin que el PDF pese de más


def fotos_a_pdf(fotos: list[bytes]) -> bytes:
    """Une las fotos (en orden) en un solo PDF, enderezadas según el celular y achicadas."""
    from PIL import Image, ImageOps

    paginas = []
    for datos in fotos:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(datos))).convert("RGB")
        img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
        paginas.append(img)
    salida = io.BytesIO()
    # Resolución para que cada página mida como una hoja carta (8,5 pulgadas de ancho).
    paginas[0].save(salida, "PDF", save_all=True, append_images=paginas[1:], quality=85,
                    resolution=max(72.0, paginas[0].width / 8.5))
    return salida.getvalue()

# Archivos: …/user-attachments/files/123/nombre.pdf. Imágenes pegadas: …/user-attachments/assets/<uuid>
# (sin extensión; GitHub las inserta como ![Image](…) o <img src="…">).
ADJUNTO = re.compile(
    r"https://github\.com/(?:(?:user-attachments/files|[\w.-]+/[\w.-]+/files)/\d+/[^\s)\]\"'>]+"
    r"|user-attachments/assets/[0-9a-f-]{36})", re.I)


def extension_de(url: str) -> str:
    """Extensión del enlace; las imágenes pegadas no la traen y se averigua al descargarlas."""
    return "" if "/user-attachments/assets/" in url else Path(url.split("?")[0]).suffix.lower()


def es_imagen(datos: bytes) -> bool:
    from PIL import Image

    try:
        Image.open(io.BytesIO(datos)).verify()
        return True
    except Exception:
        return False


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
    max_bytes = config["validacion"]["tamano_maximo_mb"] * 1_000_000
    # Primero el campo «Archivo»; luego el resto del formulario, porque en el celular es fácil
    # pegar las fotos en «Descripción» por error.
    otros = "\n".join(v for k, v in campos.items() if k != "archivo")
    enlaces = [(nombre, url) for nombre, url in adjuntos_de(campos.get("archivo", "") + "\n" + otros)
               if extension_de(url) in [*permitidas, ".zip", ""]]
    if not enlaces:
        fallar(gh, numero, f"No encontré archivos ({', '.join(permitidas)} o .zip) en el formulario. "
                           "Arrástrelos al cuadro de texto y espere a que terminen de subir antes de enviar.")

    # (nombre, extensión, contenido). Un .zip se abre y cada archivo válido de adentro cuenta
    # como uno más: sirve para formatos que GitHub no deja adjuntar (.Rmd, .html…).
    adjuntos: list[tuple[str, str, bytes]] = []
    temporal = RAIZ / ".adjunto"
    for nombre, url in enlaces:
        ext = extension_de(url)
        try:
            try:
                gh.descargar(url, temporal, max_bytes=max_bytes)
            except Exception:
                if ext:
                    raise
                anonimo = GitHub(gh.repo)  # las imágenes de un repo público se ven sin iniciar sesión
                anonimo.token = ""
                anonimo.descargar(url, temporal, max_bytes=max_bytes)
            datos = temporal.read_bytes()
        except Exception as e:
            fallar(gh, numero, f"No se pudo descargar «{nombre}»: {e}")
        finally:
            temporal.unlink(missing_ok=True)
        if not ext:  # imagen pegada en el cuadro: su nombre es «Image» o un código, mejor el título
            nombre = titulo
            if datos.startswith(b"%PDF"):
                ext = ".pdf"
            elif es_imagen(datos):
                ext = ".jpg"  # cualquier imagen termina dentro del PDF de fotos
            else:
                fallar(gh, numero, "Uno de los archivos pegados no es una imagen ni un PDF.")
        if ext != ".zip":
            adjuntos.append((nombre, ext, datos))
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                miembros = [m for m in z.infolist() if not m.is_dir() and "__MACOSX" not in m.filename
                            and not Path(m.filename).name.startswith(".")
                            and Path(m.filename).suffix.lower() in permitidas]
                if sum(m.file_size for m in miembros) > max_bytes:
                    fallar(gh, numero, f"El contenido de «{nombre}» pesa más de {max_bytes // 1_000_000} MB.")
                adjuntos += [(Path(m.filename).name, Path(m.filename).suffix.lower(), z.read(m)) for m in miembros]
        except zipfile.BadZipFile:
            fallar(gh, numero, f"«{nombre}» no es un .zip válido.")
    if not adjuntos:
        fallar(gh, numero, f"Los .zip no traen archivos válidos ({', '.join(permitidas)}).")
    # Las fotos (páginas de un cuaderno) se unen en un solo PDF: un apunte, no uno por foto.
    fotos = [datos for _, ext, datos in adjuntos if ext in IMAGENES]
    if fotos:
        try:
            pdf = fotos_a_pdf(fotos)
        except Exception as e:
            fallar(gh, numero, f"No se pudieron leer las fotos: {e}")
        adjuntos = [a for a in adjuntos if a[1] not in IMAGENES] + [(f"{titulo}.pdf", ".pdf", pdf)]
    if len(adjuntos) > MAX_ARCHIVOS:
        fallar(gh, numero, f"Adjunte como máximo {MAX_ARCHIVOS} archivos por formulario.")

    carpeta = RAIZ / CARPETA_APUNTES / curso["carpeta"]
    carpeta.mkdir(parents=True, exist_ok=True)
    login = slug(usuario["login"], 30)
    rutas = []
    for nombre, ext, datos in adjuntos:
        if ext == ".pdf" and not datos.startswith(b"%PDF"):
            fallar(gh, numero, f"«{nombre}» no es un PDF válido.")
        # Un archivo: se titula con el título del formulario. Varios: cada uno con su nombre.
        base = f"{slug(titulo if len(adjuntos) == 1 else Path(nombre).stem, 60)}-{login}"
        destino = carpeta / f"{base}{ext}"
        i = 2
        while destino.exists():
            destino = carpeta / f"{base}-{i}{ext}"
            i += 1
        destino.write_bytes(datos)
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

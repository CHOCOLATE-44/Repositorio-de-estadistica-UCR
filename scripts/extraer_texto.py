"""Extracción de texto de apuntes.

Formatos: PDF; texto (.md, .Rmd, .qmd, .txt, .R); HTML; Word (.docx) y
PowerPoint (.pptx), leídos como ZIP+XML sin dependencias; e imágenes (.jpg, .png)
con OCR, que además se le muestran a Gemini.

En los PDF:
1. Capa de texto del PDF (rápido; los PDF de LaTeX y muchos exportados la tienen).
2. Si hay muy poco texto: OCR con Tesseract (PDF escaneados o escritos a mano).
3. Además se pueden generar imágenes de las primeras páginas para que Gemini
   las "lea" cuando el OCR tampoco basta (letra a mano de iPad).

Requiere en el sistema: poppler-utils (pdftoppm) y tesseract-ocr (+ idioma spa)
para los pasos 2 y 3. Ambos se instalan gratis dentro de GitHub Actions.
"""

from __future__ import annotations

import html
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResultadoExtraccion:
    texto: str
    metodo: str  # "capa-de-texto" | "ocr" | "texto" | "html" | "word" | "powerpoint" | "imagen" | "ninguno"
    paginas: int = 0
    imagenes: list[Path] = field(default_factory=list)  # JPEG de las primeras páginas
    avisos: list[str] = field(default_factory=list)


logging.getLogger("pypdf").setLevel(logging.ERROR)  # PDFs «imperfectos» generan avisos inofensivos


def _texto_directo(pdf: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    lector = PdfReader(str(pdf))
    partes = []
    for pagina in lector.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception:  # páginas corruptas no deben tumbar todo
            partes.append("")
    return "\n".join(partes), len(lector.pages)


def _rasterizar(pdf: Path, carpeta: Path, paginas: int, dpi: int, prefijo: str) -> list[Path]:
    if not shutil.which("pdftoppm"):
        return []
    subprocess.run(
        ["pdftoppm", "-f", "1", "-l", str(paginas), "-r", str(dpi), "-jpeg", str(pdf), str(carpeta / prefijo)],
        check=True, capture_output=True, timeout=300,
    )
    return sorted(carpeta.glob(f"{prefijo}*.jpg"))


def _ocr(imagenes: list[Path]) -> str:
    if not shutil.which("tesseract"):
        return ""
    textos = []
    for img in imagenes:
        r = subprocess.run(
            ["tesseract", str(img), "-", "-l", "spa+eng"],
            capture_output=True, text=True, timeout=180,
        )
        textos.append(r.stdout)
    return "\n".join(textos)


TEXTO = {".md", ".rmd", ".qmd", ".txt", ".r"}
IMAGEN = {".jpg", ".jpeg", ".png"}


def _html(texto: str) -> str:
    texto = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", texto)
    texto = re.sub(r"(?i)<(br|/p|/div|/li|/h\d|/tr)\b[^>]*>", "\n", texto)
    return html.unescape(re.sub(r"<[^>]+>", " ", texto))


def _office(archivo: Path) -> tuple[str, int]:
    """Texto de un .docx (párrafos) o .pptx (una diapositiva por bloque)."""
    with zipfile.ZipFile(archivo) as z:
        if archivo.suffix.lower() == ".docx":
            partes = ["word/document.xml"]
        else:
            num = lambda n: int(re.search(r"(\d+)\.xml$", n).group(1))  # noqa: E731
            partes = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=num)
        bloques = []
        for parte in partes:
            xml = z.read(parte).decode("utf-8", errors="replace")
            xml = re.sub(r"</(?:w|a):p>", "\n", xml)  # fin de párrafo
            bloques.append(html.unescape("".join(re.findall(r"<(?:w|a):t(?:\s[^>]*)?>([^<]*)</(?:w|a):t>", xml)
                                                 or [re.sub(r"<[^>]+>", "", xml)])))
        return "\n\n".join(bloques), len(partes)


def extraer(archivo: Path, min_caracteres: int = 300, max_paginas_ocr: int = 8,
            paginas_imagen: int = 3, trabajo: Path | None = None) -> ResultadoExtraccion:
    archivo = Path(archivo)
    ext = archivo.suffix.lower()
    if ext in TEXTO:
        return ResultadoExtraccion(archivo.read_text(encoding="utf-8", errors="replace"), "texto")
    if ext in (".html", ".htm"):
        return ResultadoExtraccion(_html(archivo.read_text(encoding="utf-8", errors="replace")), "html")
    if ext in (".docx", ".pptx"):
        try:
            texto, paginas = _office(archivo)
        except Exception as e:
            return ResultadoExtraccion("", "ninguno", avisos=[f"No se pudo leer el archivo: {e}"])
        return ResultadoExtraccion(texto, "word" if ext == ".docx" else "powerpoint", paginas)
    if ext in IMAGEN:
        # Foto o escaneo: OCR y, si se pidió, la imagen misma para Gemini.
        texto = _ocr([archivo])
        return ResultadoExtraccion(texto, "imagen", 1, [archivo] if paginas_imagen > 0 else [],
                                   [] if shutil.which("tesseract") else ["OCR no disponible (falta tesseract)."])

    if ext != ".pdf":
        return ResultadoExtraccion("", "ninguno", avisos=[f"Formato `{ext}` no soportado."])
    trabajo = trabajo or Path(tempfile.mkdtemp(prefix="apunte-"))
    avisos: list[str] = []
    try:
        texto, paginas = _texto_directo(archivo)
    except Exception as e:  # PDF dañado o cifrado
        return ResultadoExtraccion("", "ninguno", avisos=[f"No se pudo leer el PDF: {e}"])

    metodo = "capa-de-texto"
    if len(texto.strip()) < min_caracteres:
        imgs = _rasterizar(archivo, trabajo, max_paginas_ocr, 200, "ocr")
        if not imgs:
            avisos.append("OCR no disponible (faltan pdftoppm/tesseract).")
        else:
            texto_ocr = _ocr(imgs)
            if len(texto_ocr.strip()) > len(texto.strip()):
                texto, metodo = texto_ocr, "ocr"

    imagenes: list[Path] = []
    if len(texto.strip()) < min_caracteres * 3 and paginas_imagen > 0:
        # Poco texto (típico de notas a mano): preparamos imágenes para Gemini.
        imagenes = _rasterizar(archivo, trabajo, paginas_imagen, 100, "vista")

    return ResultadoExtraccion(texto, metodo, paginas, imagenes, avisos)


if __name__ == "__main__":
    r = extraer(Path(sys.argv[1]))
    print(f"[método: {r.metodo}, páginas: {r.paginas}, imágenes: {len(r.imagenes)}]")
    print(r.texto[:3000])

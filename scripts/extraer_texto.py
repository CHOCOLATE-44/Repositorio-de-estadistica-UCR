"""Extracción de texto de apuntes.

1. Capa de texto del PDF (rápido; los PDF de LaTeX y muchos exportados la tienen).
2. Si hay muy poco texto: OCR con Tesseract (PDF escaneados o escritos a mano).
3. Además se pueden generar imágenes de las primeras páginas para que Gemini
   las "lea" cuando el OCR tampoco basta (letra a mano de iPad).

Requiere en el sistema: poppler-utils (pdftoppm) y tesseract-ocr (+ idioma spa)
para los pasos 2 y 3. Ambos se instalan gratis dentro de GitHub Actions.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResultadoExtraccion:
    texto: str
    metodo: str  # "capa-de-texto" | "ocr" | "markdown" | "ninguno"
    paginas: int = 0
    imagenes: list[Path] = field(default_factory=list)  # JPEG de las primeras páginas
    avisos: list[str] = field(default_factory=list)


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


def extraer(archivo: Path, min_caracteres: int = 300, max_paginas_ocr: int = 8,
            paginas_imagen: int = 3, trabajo: Path | None = None) -> ResultadoExtraccion:
    archivo = Path(archivo)
    if archivo.suffix.lower() == ".md":
        return ResultadoExtraccion(archivo.read_text(encoding="utf-8", errors="replace"), "markdown")

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

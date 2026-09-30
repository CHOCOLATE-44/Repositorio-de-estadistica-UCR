"""Utilidades compartidas: configuración, catálogo de cursos, API de GitHub y
lectura de formularios de issues. Solo usa la biblioteca estándar."""

from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_APUNTES = "apuntes"


# --------------------------------------------------------------------------
# Configuración y cursos
# --------------------------------------------------------------------------

def cargar_config() -> dict:
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))


def cargar_cursos() -> list[dict]:
    return json.loads((RAIZ / "cursos.json").read_text(encoding="utf-8"))["cursos"]


def curso_por_carpeta(carpeta: str, cursos: list[dict] | None = None) -> dict | None:
    for c in cursos or cargar_cursos():
        if c["carpeta"] == carpeta:
            return c
    return None


def curso_por_sigla(sigla: str, cursos: list[dict] | None = None) -> dict | None:
    s = normalizar_sigla(sigla)
    for c in cursos or cargar_cursos():
        if normalizar_sigla(c["sigla"]) == s:
            return c
    return None


def normalizar_sigla(sigla: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", sigla.upper())


def sin_tildes(texto: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", texto) if unicodedata.category(ch) != "Mn"
    )


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados (para comparar).
    Repara los acentos sueltos de PDFs hechos con LaTeX («l´ımites», «funci ´on»)."""
    texto = re.sub(r" ?[´`¨˜ˆ]", "", texto or "").replace("ı", "i")
    return re.sub(r"\s+", " ", sin_tildes(texto).lower()).strip()


def slug(texto: str, largo: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", normalizar_texto(texto)).strip("-")
    return s[:largo].strip("-") or "apunte"


# --------------------------------------------------------------------------
# API de GitHub (REST, sin dependencias)
# --------------------------------------------------------------------------

class GitHub:
    def __init__(self, repo: str | None = None, token: str | None = None):
        self.repo = repo or os.environ["GITHUB_REPOSITORY"]
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.base = os.environ.get("GITHUB_API_URL", "https://api.github.com")

    def _peticion(self, metodo: str, url: str, datos=None, aceptar="application/vnd.github+json"):
        if not url.startswith("http"):
            url = f"{self.base}{url}"
        cuerpo = json.dumps(datos).encode() if datos is not None else None
        req = urllib.request.Request(url, data=cuerpo, method=metodo)
        req.add_header("Accept", aceptar)
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if cuerpo is not None:
            req.add_header("Content-Type", "application/json")
        if self.token:
            # "unredirected" para no reenviar el token si GitHub redirige a otro host.
            req.add_unredirected_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(req, timeout=60) as r:
            contenido = r.read()
            enlace = r.headers.get("Link", "")
        return contenido, enlace

    def get(self, ruta: str):
        contenido, _ = self._peticion("GET", ruta)
        return json.loads(contenido)

    def paginar(self, ruta: str):
        """Recorre todas las páginas de un endpoint de lista."""
        sep = "&" if "?" in ruta else "?"
        url = f"{ruta}{sep}per_page=100"
        while url:
            contenido, enlace = self._peticion("GET", url)
            yield from json.loads(contenido)
            m = re.search(r'<([^>]+)>;\s*rel="next"', enlace)
            url = m.group(1) if m else None

    def post(self, ruta: str, datos: dict):
        contenido, _ = self._peticion("POST", ruta, datos)
        return json.loads(contenido) if contenido else None

    def patch(self, ruta: str, datos: dict):
        contenido, _ = self._peticion("PATCH", ruta, datos)
        return json.loads(contenido) if contenido else None

    def delete(self, ruta: str):
        try:
            self._peticion("DELETE", ruta)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

    def descargar(self, url: str, destino: Path, max_bytes: int | None = None) -> Path:
        contenido, _ = self._peticion("GET", url, aceptar="*/*")
        if max_bytes and len(contenido) > max_bytes:
            raise ValueError(f"El archivo supera el máximo de {max_bytes // 1_000_000} MB")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        return destino

    # --- atajos de issues / PR -------------------------------------------
    def comentar(self, numero: int, texto: str, marcador: str | None = None):
        """Crea un comentario, o actualiza el anterior que tenga `marcador`."""
        if marcador:
            texto = f"{marcador}\n{texto}"
            for c in self.paginar(f"/repos/{self.repo}/issues/{numero}/comments"):
                if marcador in (c.get("body") or ""):
                    return self.patch(f"/repos/{self.repo}/issues/comments/{c['id']}", {"body": texto})
        return self.post(f"/repos/{self.repo}/issues/{numero}/comments", {"body": texto})

    def poner_etiquetas(self, numero: int, poner: list[str] = (), quitar: list[str] = ()):
        for e in quitar:
            self.delete(f"/repos/{self.repo}/issues/{numero}/labels/{urllib.request.quote(e)}")
        if poner:
            self.post(f"/repos/{self.repo}/issues/{numero}/labels", {"labels": list(poner)})

    def cerrar_issue(self, numero: int, motivo: str = "completed"):
        self.patch(f"/repos/{self.repo}/issues/{numero}", {"state": "closed", "state_reason": motivo})


# --------------------------------------------------------------------------
# Formularios de issues
# --------------------------------------------------------------------------

def leer_formulario(cuerpo: str) -> dict[str, str]:
    """Convierte el cuerpo generado por un formulario de issue (secciones
    `### Etiqueta`) en un diccionario {etiqueta_normalizada: valor}."""
    campos: dict[str, str] = {}
    actual = None
    lineas: list[str] = []
    for linea in (cuerpo or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", linea)
        if m:
            if actual is not None:
                campos[actual] = "\n".join(lineas).strip()
            actual = normalizar_texto(m.group(1))
            lineas = []
        elif actual is not None:
            lineas.append(linea)
    if actual is not None:
        campos[actual] = "\n".join(lineas).strip()
    return {k: ("" if v == "_No response_" else v) for k, v in campos.items()}


def escribir_salida(nombre: str, valor: str):
    """Escribe una salida de paso de GitHub Actions (si aplica)."""
    ruta = os.environ.get("GITHUB_OUTPUT")
    if ruta:
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{nombre}={valor}\n")

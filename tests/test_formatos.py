import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import subir_desde_issue as sdi  # noqa: E402
from extraer_texto import extraer  # noqa: E402


def foto(color, tamano=(3000, 4000), formato="JPEG") -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", tamano, color).save(buf, formato)
    return buf.getvalue()


def zip_con(archivos: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return buf.getvalue()


class PruebasExtraccion(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def escribir(self, nombre, datos):
        p = self.dir / nombre
        p.write_bytes(datos if isinstance(datos, bytes) else datos.encode())
        return p

    def test_texto_plano(self):
        for nombre in ("a.Rmd", "b.qmd", "c.txt", "d.R", "e.md"):
            r = extraer(self.escribir(nombre, "Regresión lineal múltiple"))
            self.assertEqual(r.metodo, "texto", nombre)
            self.assertIn("Regresión", r.texto)

    def test_html_sin_etiquetas(self):
        r = extraer(self.escribir("x.html", "<html><style>p{}</style><body><h1>Prueba de hip&oacute;tesis</h1>"
                                            "<script>var a=1;</script><p>Valor p</p></body></html>"))
        self.assertEqual(r.metodo, "html")
        self.assertIn("Prueba de hipótesis", r.texto)
        self.assertNotIn("var a", r.texto)
        self.assertNotIn("<p>", r.texto)

    def test_word(self):
        xml = ('<w:document><w:body><w:p><w:r><w:t>Intervalos de</w:t></w:r><w:r><w:t xml:space="preserve"> '
               'confianza</w:t></w:r></w:p><w:p><w:r><w:t>Muestreo &amp; estimación</w:t></w:r></w:p></w:body></w:document>')
        r = extraer(self.escribir("x.docx", zip_con({"word/document.xml": xml})))
        self.assertEqual(r.metodo, "word")
        self.assertIn("Intervalos de confianza", r.texto)
        self.assertIn("Muestreo & estimación", r.texto)

    def test_powerpoint_en_orden(self):
        diapo = lambda t: f"<p:sld><a:p><a:r><a:t>{t}</a:t></a:r></a:p></p:sld>"  # noqa: E731
        r = extraer(self.escribir("x.pptx", zip_con({"ppt/slides/slide10.xml": diapo("ANOVA"),
                                                     "ppt/slides/slide2.xml": diapo("Bloques"),
                                                     "ppt/slideLayouts/slideLayout1.xml": diapo("plantilla")})))
        self.assertEqual(r.metodo, "powerpoint")
        self.assertEqual(r.paginas, 2)
        self.assertLess(r.texto.index("Bloques"), r.texto.index("ANOVA"))
        self.assertNotIn("plantilla", r.texto)

    def test_office_danado(self):
        r = extraer(self.escribir("x.docx", b"no es un zip"))
        self.assertEqual(r.metodo, "ninguno")

    def test_imagen_se_muestra_a_gemini(self):
        img = self.escribir("foto.png", b"\x89PNG")
        with mock.patch("extraer_texto._ocr", return_value="Examen parcial"):
            r = extraer(img)
        self.assertEqual((r.metodo, r.texto, r.imagenes), ("imagen", "Examen parcial", [img]))


class GitHubFalso:
    repo = "o/r"

    def __init__(self, archivos):
        self.archivos, self.comentarios = archivos, []

    def descargar(self, url, destino, max_bytes=None):
        destino.write_bytes(self.archivos[url])

    def comentar(self, numero, texto, marcador=None):
        self.comentarios.append(texto)

    def poner_etiquetas(self, *a, **k):
        pass


class PruebasSubida(unittest.TestCase):
    def subir(self, enlaces: dict[str, bytes]):
        archivo = "\n".join(f"[{n}](https://github.com/user-attachments/files/{i}/{n})" for i, n in enumerate(enlaces))
        gh = GitHubFalso({f"https://github.com/user-attachments/files/{i}/{n}": d for i, (n, d) in enumerate(enlaces.items())})
        return self.subir_cuerpo(archivo, gh)

    def subir_cuerpo(self, archivo: str, gh):
        raiz = Path(tempfile.mkdtemp())
        shutil.copy(sdi.RAIZ / "config.json", raiz)
        shutil.copy(sdi.RAIZ / "cursos.json", raiz)
        cuerpo = "### Curso\n\nXS-2130 — Modelos de regresión aplicados\n\n### Título\n\nRepaso\n\n### Archivo\n\n" + archivo
        issue = {"number": 5, "title": "Apunte: Repaso", "body": cuerpo, "labels": [{"name": "subir-apunte"}],
                 "user": {"login": "ana", "id": 1}}
        evento = raiz / "evento.json"
        evento.write_text(json.dumps({"issue": issue}))
        salidas = {}
        with mock.patch.object(sdi, "RAIZ", raiz), mock.patch.object(sdi, "GitHub", return_value=gh), \
             mock.patch("comun.RAIZ", raiz), \
             mock.patch.object(sdi, "escribir_salida", side_effect=lambda k, v: salidas.__setitem__(k, v)), \
             mock.patch.dict(os.environ, {"ISSUE_MANUAL": "", "GITHUB_EVENT_PATH": str(evento)}):
            try:
                sdi.main()
            except SystemExit:
                pass
        self.ultima_raiz = raiz
        carpeta = raiz / "apuntes"
        return salidas, sorted(p.name for p in carpeta.rglob("*") if p.is_file()), gh

    def test_zip_se_abre(self):
        datos = zip_con({"tarea/analisis.Rmd": "x", "tarea/pagina.html": "<p>x</p>", "__MACOSX/._a.Rmd": "x",
                         "tarea/datos.csv": "1,2"})
        salidas, archivos, _ = self.subir({"tarea.zip": datos})
        self.assertEqual(salidas["ok"], "true")
        self.assertEqual(archivos, ["analisis-ana.rmd", "pagina-ana.html"])

    def test_formatos_directos(self):
        salidas, archivos, _ = self.subir({"clase.pptx": b"PK", "notas.docx": b"PK"})
        self.assertEqual(salidas["ok"], "true")
        self.assertEqual(archivos, ["clase-ana.pptx", "notas-ana.docx"])

    def test_fotos_se_unen_en_un_pdf_en_orden(self):
        from pypdf import PdfReader
        salidas, archivos, _ = self.subir({"p1.jpg": foto("red"), "p2.png": foto("blue", formato="PNG"),
                                           "p3.jpg": foto("green")})
        self.assertEqual(salidas["ok"], "true")
        self.assertEqual(archivos, ["repaso-ana.pdf"])
        pdf = next(self.ultima_raiz.rglob("*.pdf"))
        lector = PdfReader(str(pdf))
        self.assertEqual(len(lector.pages), 3)
        self.assertLess(pdf.stat().st_size, 2_000_000)  # se achican: no 3 fotos de 12 MP
        caja = lector.pages[0].mediabox
        self.assertAlmostEqual(float(caja.width) / 72, 8.5, places=1)  # ancho de hoja carta

    def test_fotos_pegadas_sin_extension(self):
        # Así inserta GitHub una foto arrastrada al cuadro: <img … src=".../assets/<uuid>"> o ![Image](…)
        uuid1, uuid2 = "a49b981e-81b4-4405-9df1-72036fe23365", "b49b981e-81b4-4405-9df1-72036fe23366"
        cuerpo = (f'<img width="4080" height="3060" alt="Image" src="https://github.com/user-attachments/assets/{uuid1}" />'
                  f"\n![Image](https://github.com/user-attachments/assets/{uuid2})")
        enlaces = sdi.adjuntos_de(cuerpo)
        self.assertEqual([u.rsplit("/", 1)[-1] for _, u in enlaces], [uuid1, uuid2])
        gh = GitHubFalso({u: foto("red") for _, u in enlaces})
        gh.archivos[enlaces[1][1]] = b"%PDF-1.4 algo"
        _, archivos, _ = self.subir_cuerpo(cuerpo, gh)
        self.assertEqual(archivos, ["repaso-ana-2.pdf", "repaso-ana.pdf"])

    def test_fotos_pegadas_en_descripcion(self):
        # Caso real: en el celular las fotos quedaron en «Descripción» y en «Archivo» solo texto.
        uuid = "efd8e6ae-efe0-4ee7-861d-3cc3f316a749"
        url = f"https://github.com/user-attachments/assets/{uuid}"
        archivo = (f"Resumen hecho a mano\n\n### Descripción\n\n"
                   f'<img width="3024" height="4032" alt="Image" src="{url}" />')
        salidas, archivos, _ = self.subir_cuerpo(archivo, GitHubFalso({url: foto("red")}))
        self.assertEqual(salidas["ok"], "true")
        self.assertEqual(archivos, ["repaso-ana.pdf"])

    def test_fotos_y_otro_archivo(self):
        _, archivos, _ = self.subir({"clase.pptx": b"PK", "p1.jpg": foto("red")})
        self.assertEqual(archivos, ["clase-ana.pptx", "repaso-ana.pdf"])

    def test_zip_sin_archivos_validos(self):
        salidas, archivos, gh = self.subir({"x.zip": zip_con({"datos.csv": "1"})})
        self.assertEqual(salidas["ok"], "false")
        self.assertEqual(archivos, [])


if __name__ == "__main__":
    unittest.main()

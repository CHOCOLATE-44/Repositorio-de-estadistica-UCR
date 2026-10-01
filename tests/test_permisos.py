import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import validar_apunte as va  # noqa: E402
from validar_apunte import Veredicto, revisar_permiso  # noqa: E402

RUTA = "apuntes/XS-2130-modelos-de-regresion-aplicados/notas-ana.pdf"


class PruebasRegla(unittest.TestCase):
    def test_agregar_siempre_permitido(self):
        self.assertIsNone(revisar_permiso("added", "cualquiera", "NONE", "ana"))

    def test_autor_puede_modificar_eliminar_y_renombrar(self):
        for estado in ("modified", "removed", "renamed"):
            self.assertIsNone(revisar_permiso(estado, "Ana", "NONE", "ana"), estado)

    def test_propietario_puede_todo(self):
        for rol in ("OWNER", "MEMBER", "COLLABORATOR"):
            self.assertIsNone(revisar_permiso("removed", "dueño", rol, "ana"))

    def test_otro_estudiante_no(self):
        for estado in ("modified", "removed", "renamed"):
            error = revisar_permiso(estado, "beto", "CONTRIBUTOR", "ana")
            self.assertIn("@ana", error)

    def test_autor_desconocido_solo_mantenedores(self):
        self.assertIsNotNone(revisar_permiso("modified", "beto", "NONE", None))
        self.assertIsNone(revisar_permiso("modified", "dueño", "OWNER", None))


class GitHubFalso:
    repo = "o/r"

    def __init__(self, usuario, asociacion, archivos):
        self.pr = {"number": 1, "user": {"login": usuario}, "author_association": asociacion,
                   "head": {"sha": "abc", "ref": "apunte/issue-9", "repo": {"full_name": "o/r"}},
                   "base": {"ref": "main"}}
        self.archivos, self.estados, self.comentarios, self.fusiones = archivos, [], [], []

    def get(self, ruta):
        return self.pr

    def paginar(self, ruta):
        return iter(self.archivos)

    def descargar(self, url, destino, max_bytes=None):
        destino.write_bytes(b"%PDF")

    def comentar(self, numero, texto, marcador=None):
        self.comentarios.append(texto)

    def poner_etiquetas(self, *a, **k):
        pass

    def post(self, ruta, datos):
        if "/statuses/" in ruta:
            self.estados.append(datos)

    def put(self, ruta, datos):
        self.fusiones.append(datos)

    def delete(self, ruta):
        pass


def correr(usuario, asociacion, archivos, autor="ana"):
    gh = GitHubFalso(usuario, asociacion, archivos)
    valido = Veredicto(RUTA, True, "contenido ok")
    with mock.patch.object(va, "GitHub", return_value=gh), \
         mock.patch.object(va, "autor_de", return_value=autor), \
         mock.patch.object(va, "validar_archivo", return_value=valido):
        codigo = va.validar_pr(1)
    return codigo, gh


class PruebasPR(unittest.TestCase):
    def modificado(self):
        return [{"filename": RUTA, "status": "modified", "raw_url": "u"}]

    def test_otro_estudiante_modifica_rechazado(self):
        codigo, gh = correr("beto", "CONTRIBUTOR", self.modificado())
        self.assertEqual(codigo, 1)
        self.assertEqual(gh.estados[-1]["state"], "failure")
        self.assertIn("No tiene permiso", gh.comentarios[-1])

    def test_autor_modifica_aceptado(self):
        codigo, gh = correr("ana", "CONTRIBUTOR", self.modificado())
        self.assertEqual(codigo, 0)
        self.assertEqual(gh.estados[-1]["state"], "success")

    def test_otro_elimina_rechazado_y_propietario_aceptado(self):
        borrar = [{"filename": RUTA, "status": "removed", "raw_url": "u"}]
        self.assertEqual(correr("beto", "NONE", borrar)[0], 1)
        codigo, gh = correr("dueño", "OWNER", borrar)
        self.assertEqual(codigo, 0)
        self.assertTrue(any("Eliminación autorizada" in c for c in gh.comentarios))

    def test_renombrar_usa_ruta_anterior(self):
        otra = RUTA.replace("notas-ana", "otro-nombre")
        archivos = [{"filename": otra, "status": "renamed", "previous_filename": RUTA, "raw_url": "u"}]
        with mock.patch.object(va, "autor_de", return_value="ana") as m:
            gh = GitHubFalso("beto", "NONE", archivos)
            with mock.patch.object(va, "GitHub", return_value=gh):
                self.assertEqual(va.validar_pr(1), 1)
            m.assert_called_with(RUTA, gh)

    def test_estudiante_no_toca_archivos_fuera_de_apuntes(self):
        codigo, _ = correr("beto", "NONE", [{"filename": "sitio/app.js", "status": "modified", "raw_url": "u"}])
        self.assertEqual(codigo, 1)
        codigo, _ = correr("dueño", "OWNER", [{"filename": "sitio/app.js", "status": "modified", "raw_url": "u"}])
        self.assertEqual(codigo, 0)

    def test_pr_de_codigo_del_propietario_queda_en_verde_sin_comentar(self):
        codigo, gh = correr("dueño", "OWNER", [{"filename": "scripts/x.py", "status": "modified", "raw_url": "u"}])
        self.assertEqual(codigo, 0)
        self.assertEqual(gh.estados[-1]["state"], "success")
        self.assertEqual(gh.comentarios, [])

    def test_apunte_nuevo_de_cualquiera(self):
        codigo, _ = correr("beto", "NONE", [{"filename": RUTA, "status": "added", "raw_url": "u"}])
        self.assertEqual(codigo, 0)


class PruebasPublicacion(unittest.TestCase):
    def test_apunte_que_coincide_se_publica_solo(self):
        _, gh = correr("beto", "NONE", [{"filename": RUTA, "status": "added", "raw_url": "u"}])
        self.assertEqual(gh.fusiones, [{"merge_method": "merge", "sha": "abc", "commit_title": "Publicar apunte (#1)"}])
        self.assertTrue(any("Publicado" in c for c in gh.comentarios))

    def test_apunte_rechazado_no_se_publica(self):
        _, gh = correr("beto", "CONTRIBUTOR", [{"filename": RUTA, "status": "modified", "raw_url": "u"}])
        self.assertEqual(gh.fusiones, [])

    def test_pr_con_codigo_no_se_publica_solo(self):
        _, gh = correr("dueño", "OWNER", [{"filename": RUTA, "status": "added", "raw_url": "u"},
                                          {"filename": "scripts/x.py", "status": "modified", "raw_url": "u"}])
        self.assertEqual(gh.fusiones, [])
        _, gh = correr("dueño", "OWNER", [{"filename": "scripts/x.py", "status": "modified", "raw_url": "u"}])
        self.assertEqual(gh.fusiones, [])


if __name__ == "__main__":
    unittest.main()

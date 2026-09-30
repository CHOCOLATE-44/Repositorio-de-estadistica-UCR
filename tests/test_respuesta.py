import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import responder_validacion as rv  # noqa: E402
from validar_apunte import Veredicto, issue_de_subida, pregunta_al_autor  # noqa: E402

INF = "apuntes/XS-1130-principios-de-inferencia-estadistica"
PROB = "apuntes/XS-0122-modelos-probabilisticos-1"


class PruebasComandos(unittest.TestCase):
    def test_leer_comando(self):
        self.assertEqual(rv.leer_comando("/contenido-nuevo lo vimos en clase"), ("contenido-nuevo", "lo vimos en clase"))
        self.assertEqual(rv.leer_comando("/contenido-nuevo\nEl profe lo agregó"), ("contenido-nuevo", "El profe lo agregó"))
        for texto in ("/curso XS-0122", "/curso xs0122", "/curso XS 0122 gracias"):
            self.assertEqual(rv.leer_comando(texto), ("curso", "XS-0122"), texto)
        self.assertIsNone(rv.leer_comando("gracias!"))
        self.assertIsNone(rv.leer_comando("/curso"))

    def test_permiso(self):
        self.assertTrue(rv.puede_responder("Ana", "NONE", "ana"))
        self.assertTrue(rv.puede_responder("dueño", "OWNER", "ana"))
        self.assertFalse(rv.puede_responder("beto", "CONTRIBUTOR", "ana"))

    def test_issue_de_subida(self):
        self.assertEqual(issue_de_subida({"head": {"ref": "apunte/issue-5"}}), 5)
        self.assertIsNone(issue_de_subida({"head": {"ref": "mi-rama"}}))

    def test_pregunta_solo_en_rechazo_por_contenido(self):
        contenido = Veredicto("a.pdf", False, "no coincide", preguntar=True, curso_sugerido="XS-0122")
        permiso = Veredicto("b.pdf", False, "No tienes permiso")
        texto = pregunta_al_autor([contenido], "ana")
        self.assertIn("@ana", texto)
        self.assertIn("/contenido-nuevo", texto)
        self.assertIn("/curso XS-0122", texto)
        self.assertEqual(pregunta_al_autor([permiso], "ana"), "")
        self.assertEqual(pregunta_al_autor([Veredicto("c.pdf", True, "ok", preguntar=True)], "ana"), "")


class GitHubFalso:
    repo = "o/r"

    def __init__(self):
        self.parches, self.posts = [], []

    def paginar(self, ruta):
        return iter([{"filename": f"{INF}/poisson.pdf", "status": "added"},
                     {"filename": f"{INF}/README.md", "status": "modified"}])

    def get(self, ruta):
        return {"body": "### Curso\n\nXS-1130 — Principios de inferencia estadística\n\n### Título\n\nPoisson"}

    def patch(self, ruta, datos):
        self.parches.append((ruta, datos))

    def post(self, ruta, datos):
        self.posts.append((ruta, datos))


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


class PruebaMoverCurso(unittest.TestCase):
    def test_mueve_archivo_y_relanza_validacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            remoto, local = Path(tmp, "remoto.git"), Path(tmp, "local")
            sh(tmp, "git", "init", "-q", "--bare", str(remoto))
            sh(tmp, "git", "clone", "-q", str(remoto), str(local))
            (local / INF).mkdir(parents=True)
            (local / INF / "poisson.pdf").write_bytes(b"%PDF")
            sh(local, "git", "add", ".")
            sh(local, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "apunte")
            sh(local, "git", "push", "-q", "origin", "HEAD:apunte/issue-5")

            gh = GitHubFalso()
            pr = {"number": 10, "title": "[XS-1130] Poisson", "head": {"ref": "apunte/issue-5", "repo": {"full_name": "o/r"}},
                  "base": {"ref": "main"}}
            with mock.patch.object(rv, "RAIZ", local):
                respuesta = rv.cambiar_curso(gh, pr, "ana", "XS-0122")

            self.assertIn("XS-0122", respuesta)
            archivos = sh(local, "git", "ls-tree", "-r", "--name-only", "origin/apunte/issue-5").split()
            self.assertIn(f"{PROB}/poisson.pdf", archivos)
            self.assertNotIn(f"{INF}/poisson.pdf", archivos)
            titulo = [d for r, d in gh.parches if r.endswith("/pulls/10")][0]["title"]
            self.assertEqual(titulo, "[XS-0122] Poisson")
            cuerpo = [d for r, d in gh.parches if r.endswith("/issues/5")][0]["body"]
            self.assertIn("XS-0122 — Modelos probabilísticos I", cuerpo)
            self.assertTrue(any(r.endswith("validar-apunte.yml/dispatches") and d["inputs"]["pr"] == "10" for r, d in gh.posts))

    def test_curso_desconocido(self):
        self.assertIn("No reconozco", rv.cambiar_curso(GitHubFalso(), {"number": 1, "head": {}}, "ana", "XS-9999"))


if __name__ == "__main__":
    unittest.main()

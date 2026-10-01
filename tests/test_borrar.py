import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import borrar_desde_issue as bd  # noqa: E402
import validar_apunte as va  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
EXISTENTE = next(p for p in sorted((RAIZ / "apuntes").glob("*/*")) if p.name.lower() != "readme.md")
RUTA = EXISTENTE.relative_to(RAIZ).as_posix()


class GitHubFalso:
    repo = "o/r"

    def __init__(self):
        self.comentarios, self.cerrados = [], []

    def comentar(self, numero, texto, marcador=None):
        self.comentarios.append(texto)

    def cerrar_issue(self, numero, motivo="completed"):
        self.cerrados.append(motivo)


def correr(usuario, asociacion, apunte, autor="ana"):
    gh, salidas = GitHubFalso(), {}
    issue = {"number": 7, "user": {"login": usuario}, "author_association": asociacion,
             "body": f"### Apunte\n\n{apunte}\n\n### Motivo\n\n_No response_"}
    evento = Path(tempfile.mkdtemp()) / "evento.json"
    evento.write_text(json.dumps({"issue": issue}), encoding="utf-8")
    with mock.patch.object(bd, "GitHub", return_value=gh), \
         mock.patch.object(bd, "autor_de", return_value=autor), \
         mock.patch.object(bd, "escribir_salida", side_effect=lambda k, v: salidas.__setitem__(k, v)), \
         mock.patch.dict(os.environ, {"ISSUE_MANUAL": "", "GITHUB_EVENT_PATH": str(evento)}):
        try:
            bd.main()
        except SystemExit:
            pass
    return salidas, gh


class PruebasBorrar(unittest.TestCase):
    def test_autor_puede_borrar(self):
        salidas, gh = correr("Ana", "NONE", RUTA)
        self.assertEqual(salidas["ok"], "true")
        self.assertEqual(salidas["ruta"], RUTA)
        self.assertEqual(salidas["rama"], "borrar/issue-7")

    def test_acepta_enlace_de_github(self):
        salidas, _ = correr("ana", "NONE", f"https://github.com/o/r/blob/main/{RUTA}")
        self.assertEqual(salidas["ruta"], RUTA)

    def test_otro_no_puede(self):
        salidas, gh = correr("beto", "CONTRIBUTOR", RUTA)
        self.assertEqual(salidas["ok"], "false")
        self.assertEqual(gh.cerrados, ["not_planned"])
        self.assertIn("@ana", gh.comentarios[-1])

    def test_mantenedor_puede(self):
        self.assertEqual(correr("dueño", "OWNER", RUTA)[0]["ok"], "true")

    def test_ruta_invalida(self):
        for mala in ("apuntes/x/no-existe.pdf", "scripts/comun.py", "apuntes/../config.json"):
            self.assertEqual(correr("dueño", "OWNER", mala)[0]["ok"], "false", mala)


class PruebasIssueDelPR(unittest.TestCase):
    def pr(self, rama, repo="o/r"):
        return {"head": {"ref": rama, "repo": {"full_name": repo}}, "base": {"repo": {"full_name": "o/r"}}}

    def test_ramas_del_robot(self):
        self.assertEqual(va.issue_de_subida(self.pr("apunte/issue-3")), 3)
        self.assertEqual(va.issue_de_subida(self.pr("borrar/issue-4")), 4)

    def test_rama_de_un_fork_no_cuenta(self):
        self.assertIsNone(va.issue_de_subida(self.pr("borrar/issue-4", repo="otro/r")))


if __name__ == "__main__":
    unittest.main()

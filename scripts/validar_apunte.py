"""Valida que los apuntes de un Pull Request correspondan al curso de su carpeta.

Uso en Actions:   python scripts/validar_apunte.py --pr 12
Uso local:        python scripts/validar_apunte.py --archivo notas.pdf --carpeta XS-2130-modelos-de-regresion-aplicados

Seguridad: este script corre con `pull_request_target`, por eso NUNCA ejecuta
código del PR; solo descarga los archivos de apuntes y los lee como datos.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini  # noqa: E402
from comun import (CARPETA_APUNTES, RAIZ, GitHub, cargar_config, cargar_cursos,  # noqa: E402
                   curso_por_carpeta, escribir_salida, normalizar_texto)
from extraer_texto import extraer  # noqa: E402
from indice import autor_de  # noqa: E402

MARCADOR = "<!-- validacion-apuntes -->"
CONTEXTO_ESTADO = "Validación de apuntes"  # estado que se puede exigir en las reglas de la rama

# author_association de GitHub que cuentan como propietarios/mantenedores del repositorio.
ROLES_MANTENEDOR = {"OWNER", "MEMBER", "COLLABORATOR"}
ACCIONES = {"modified": "modificar", "removed": "eliminar", "renamed": "renombrar o mover"}


def revisar_permiso(estado: str, usuario: str, asociacion: str, autor_original: str | None) -> str | None:
    """Solo los mantenedores del repo y quien subió el apunte pueden modificarlo,
    renombrarlo o eliminarlo. Devuelve el motivo del rechazo, o None si está permitido."""
    if estado not in ACCIONES or asociacion in ROLES_MANTENEDOR:
        return None
    if autor_original and autor_original.lower() == usuario.lower():
        return None
    quien = f"@{autor_original} (quien lo subió)" if autor_original else "quien lo subió"
    return (f"No tienes permiso para {ACCIONES[estado]} este apunte: solo {quien} o los "
            "mantenedores del repositorio pueden hacerlo. Si tiene un error, avisa en un issue.")

PALABRAS_VACIAS = set("""
para como pero este esta estos estas donde cuando entre sobre desde hasta segun
tiene tienen debe deben sera seran puede pueden cada otro otra otros otras mismo
curso cursos estudiante estudiantes profesor profesora semestre ciclo creditos
evaluacion horas clase clases sesion sesiones semana semanas universidad escuela
estadistica costa rica correo consulta consultas nota notas trabajo trabajos
porcentaje fecha fechas objetivo objetivos general generales especifico
especificos contenido contenidos bibliografia metodologia horario grupo
""".split())


# --------------------------------------------------------------------------
# Heurística (sin IA)
# --------------------------------------------------------------------------

def _regex_sigla(sigla: str) -> re.Pattern:
    pre, num = sigla.split("-")
    return re.compile(rf"\b{pre.lower()}\s*[-_]?\s*{num}\b")


def _terminos(texto: str, n: int = 40) -> list[str]:
    palabras = re.findall(r"[a-z]{6,}", normalizar_texto(texto))
    cuenta = Counter(p for p in palabras if p not in PALABRAS_VACIAS)
    return [p for p, _ in cuenta.most_common(n)]


def puntuar_curso(texto_norm: str, curso: dict, terminos_carta: list[str] = ()) -> tuple[int, list[str]]:
    """Devuelve (puntaje, señales encontradas) del texto para un curso."""
    puntos, señales = 0, []
    for s in [curso["sigla"], *curso.get("siglas_equivalentes", [])]:
        if _regex_sigla(s).search(texto_norm):
            puntos += 4
            señales.append(f"sigla {s}")
            break
    nombre = normalizar_texto(re.sub(r"\bI+$", "", curso["nombre"]).strip())
    if nombre in texto_norm:
        puntos += 4
        señales.append(f"nombre «{curso['nombre']}»")
    temas = [t for t in curso.get("temas", []) if len(t) > 2 and
             re.search(rf"\b{re.escape(normalizar_texto(t))}\b", texto_norm)]
    if temas:
        puntos += min(len(temas), 6)
        señales.append("temas: " + ", ".join(temas[:8]))
    if terminos_carta:
        comunes = [t for t in terminos_carta if re.search(rf"\b{t}\b", texto_norm)]
        if len(comunes) >= 0.3 * len(terminos_carta):
            puntos += 3
            señales.append(f"{len(comunes)}/{len(terminos_carta)} términos de la carta al estudiante")
    return puntos, señales


# --------------------------------------------------------------------------
# Carta al estudiante (desactivada por defecto en config.json)
# --------------------------------------------------------------------------

def cargar_carta(curso: dict, config: dict) -> str:
    """Texto de la carta al estudiante del curso, si la función está activa y
    existe `cartas/<SIGLA>.pdf|.md|.txt`."""
    val = config["validacion"]
    if not val.get("usar_carta_estudiante"):
        return ""
    carpeta = RAIZ / val.get("carpeta_cartas", "cartas")
    for ext in (".pdf", ".md", ".txt"):
        ruta = carpeta / f"{curso['sigla']}{ext}"
        if ruta.exists():
            if ext == ".txt":
                return ruta.read_text(encoding="utf-8", errors="replace")
            return extraer(ruta, paginas_imagen=0).texto
    return ""


# --------------------------------------------------------------------------
# Decisión
# --------------------------------------------------------------------------

@dataclass
class Veredicto:
    archivo: str
    valido: bool
    motivo: str
    detalles: list[str] = field(default_factory=list)


def _prompt(curso: dict, otros: list[dict], texto: str, carta: str, hay_imagenes: bool) -> str:
    lista_otros = "\n".join(f"- {c['sigla']} {c['nombre']}" for c in otros)
    carta_txt = f"\nCARTA AL ESTUDIANTE DEL CURSO (fragmento):\n\"\"\"\n{carta[:8000]}\n\"\"\"\n" if carta else ""
    imgs = "\nTambién se adjuntan imágenes de las primeras páginas (pueden ser notas a mano).\n" if hay_imagenes else ""
    return f"""Eres un verificador de un repositorio de apuntes de la carrera de Estadística de la Universidad de Costa Rica.
Decide si el documento enviado son apuntes/notas de estudio del curso indicado.

CURSO DE LA CARPETA: {curso['sigla']} — {curso['nombre']}
Siglas equivalentes (planes anteriores): {', '.join(curso.get('siglas_equivalentes', [])) or 'ninguna'}
Temas típicos: {', '.join(curso.get('temas', []))}
{carta_txt}
OTROS CURSOS DE LA CARRERA (para detectar si se subió en la carpeta equivocada):
{lista_otros}
{imgs}
TEXTO EXTRAÍDO DEL DOCUMENTO (puede venir de OCR y tener errores):
\"\"\"
{texto[:15000]}
\"\"\"

Criterios:
- "es_apunte": false si es spam, algo sin relación con estudiar, o un documento vacío/ilegible.
- "corresponde": true si el contenido trata mayoritariamente de los temas del curso de la carpeta.
  Temas compartidos con otros cursos son aceptables si encajan razonablemente en este curso.
- Si claramente pertenece a otro curso de la lista, indica su sigla en "curso_probable".
Responde SOLO con JSON:
{{"es_apunte": bool, "corresponde": bool, "confianza": número entre 0 y 1,
  "curso_probable": "sigla o null", "motivo": "explicación breve en español (máx. 2 oraciones)"}}"""


def validar_archivo(archivo: Path, nombre_en_repo: str, carpeta: str, config: dict,
                    cursos: list[dict]) -> Veredicto:
    val = config["validacion"]
    curso = curso_por_carpeta(carpeta, cursos)
    if curso is None:
        return Veredicto(nombre_en_repo, False,
                         f"La carpeta `{carpeta}` no corresponde a ningún curso de `cursos.json`.")

    ext = archivo.suffix.lower()
    if ext not in val["extensiones_permitidas"]:
        return Veredicto(nombre_en_repo, False,
                         f"Tipo de archivo `{ext}` no permitido (se aceptan {', '.join(val['extensiones_permitidas'])}).")
    if archivo.stat().st_size > val["tamano_maximo_mb"] * 1_000_000:
        return Veredicto(nombre_en_repo, False,
                         f"El archivo pesa más de {val['tamano_maximo_mb']} MB. Comprímelo (p. ej. con ilovepdf.com).")

    r = extraer(archivo, val["min_caracteres_texto_directo"], val["max_paginas_ocr"],
                val["paginas_imagen_para_gemini"] if gemini.disponible() else 0)
    detalles = [f"Extracción: **{r.metodo}** ({len(r.texto.strip())} caracteres"
                + (f", {r.paginas} páginas" if r.paginas else "") + ")"] + r.avisos

    texto_norm = normalizar_texto(r.texto)
    carta = cargar_carta(curso, config)
    if val.get("usar_carta_estudiante"):
        detalles.append("Carta al estudiante: " + ("usada" if carta else f"no encontrada (`{val.get('carpeta_cartas')}/{curso['sigla']}.pdf`)"))
    terminos_carta = _terminos(carta) if carta else []

    puntos, señales = puntuar_curso(texto_norm, curso, terminos_carta)
    otros = [c for c in cursos if c["carpeta"] != carpeta]
    mejor_otro = max(otros, key=lambda c: puntuar_curso(texto_norm, c)[0])
    puntos_otro = puntuar_curso(texto_norm, mejor_otro)[0]
    detalles.append(f"Señales del curso ({puntos} pts): " + ("; ".join(señales) or "ninguna"))
    heur_valido = puntos >= val["umbral_heuristico"] and puntos_otro < puntos + 4
    heur_motivo = (f"Se encontraron señales del curso ({puntos} pts)." if heur_valido else
                   f"Parece más de {mejor_otro['sigla']} {mejor_otro['nombre']} ({puntos_otro} pts vs {puntos})."
                   if puntos_otro >= puntos + 4 else
                   f"No se encontraron suficientes señales del curso ({puntos} de {val['umbral_heuristico']} pts necesarios).")

    if gemini.disponible() and (r.texto.strip() or r.imagenes):
        try:
            res = gemini.preguntar_json(_prompt(curso, otros, r.texto, carta, bool(r.imagenes)),
                                        val["gemini_modelo"], r.imagenes)
            valido = bool(res.get("es_apunte")) and bool(res.get("corresponde"))
            motivo = str(res.get("motivo", "")).strip()
            if res.get("curso_probable") and not valido:
                motivo += f" (Curso probable: {res['curso_probable']}.)"
            detalles.append(f"Gemini: confianza {res.get('confianza')}; heurística: {'✅' if heur_valido else '❌'}")
            return Veredicto(nombre_en_repo, valido, motivo or "Sin motivo.", detalles)
        except Exception as e:
            detalles.append(f"Gemini no disponible ({e}); se usó solo la heurística.")

    if not r.texto.strip():
        return Veredicto(nombre_en_repo, False,
                         "No se pudo extraer texto del documento (¿escaneo ilegible o PDF protegido?).", detalles)
    return Veredicto(nombre_en_repo, heur_valido, heur_motivo, detalles)


# --------------------------------------------------------------------------
# Modo Pull Request
# --------------------------------------------------------------------------

def _informe(veredictos: list[Veredicto], notas: list[str]) -> str:
    ok = all(v.valido for v in veredictos)
    if not veredictos:
        cab = "### ℹ️ Este PR no agrega apuntes nuevos"
    elif ok:
        cab = "### ✅ Apuntes validados"
    else:
        cab = "### ❌ Algún apunte no pasó la validación"
    partes = [cab, ""]
    for v in veredictos:
        partes.append(f"**{'✅' if v.valido else '❌'} `{v.archivo}`** — {v.motivo}")
        if v.detalles:
            partes.append("<details><summary>Detalles</summary>\n\n" +
                          "\n".join(f"- {d}" for d in v.detalles) + "\n</details>")
        partes.append("")
    if notas:
        partes += ["**Notas para el mantenedor:**", *[f"- {n}" for n in notas], ""]
    if veredictos and not ok:
        partes.append("Si crees que es un error, responde en este PR explicando por qué; "
                      "el mantenedor lo revisará manualmente. Si te equivocaste de carpeta, "
                      "mueve el archivo a la carpeta correcta y vuelve a hacer push.")
    partes.append("\n<sub>Validación automática · texto directo → OCR (Tesseract) → Gemini (Google AI Studio)</sub>")
    return "\n".join(partes)


def validar_pr(numero: int) -> int:
    gh = GitHub()
    config, cursos = cargar_config(), cargar_cursos()
    veredictos: list[Veredicto] = []
    notas: list[str] = []
    trabajo = Path(tempfile.mkdtemp(prefix="pr-"))
    max_bytes = config["validacion"]["tamano_maximo_mb"] * 1_000_000

    pr = gh.get(f"/repos/{gh.repo}/pulls/{numero}")
    usuario = pr["user"]["login"]
    asociacion = pr.get("author_association", "NONE")
    mantenedor = asociacion in ROLES_MANTENEDOR

    for f in gh.paginar(f"/repos/{gh.repo}/pulls/{numero}/files"):
        ruta = PurePosixPath(f["filename"])
        partes = ruta.parts
        es_apunte = (len(partes) == 3 and partes[0] == CARPETA_APUNTES and ruta.name.lower() != "readme.md")
        if not es_apunte:
            if mantenedor:
                notas.append(f"`{ruta}` ({f['status']}) está fuera de `apuntes/<curso>/`: revísalo antes de fusionar.")
            else:
                veredictos.append(Veredicto(str(ruta), False,
                                            "Solo se pueden agregar o cambiar archivos dentro de `apuntes/<curso>/`. "
                                            "Los demás archivos los cambian los mantenedores."))
            continue

        # Apunte que ya existía: ¿quién lo puede tocar?
        if f["status"] in ACCIONES:
            original = f.get("previous_filename") or f["filename"]
            autor_original = autor_de(original, gh)
            error = revisar_permiso(f["status"], usuario, asociacion, autor_original)
            if error:
                veredictos.append(Veredicto(str(ruta), False, error))
                continue
            quien = "mantenedor" if mantenedor else "autor del apunte"
            if f["status"] == "removed":
                veredictos.append(Veredicto(str(ruta), True, f"Eliminación autorizada ({quien}). Se perderán sus votos."))
                continue
            if f["status"] == "renamed":
                notas.append(f"`{original}` → `{ruta}` ({quien}): renombrar hace que el apunte pierda sus votos.")
            else:
                notas.append(f"`{ruta}` se reemplaza por una nueva versión ({quien}); conserva sus votos.")

        destino = trabajo / ruta.name
        try:
            gh.descargar(f["raw_url"], destino, max_bytes=max_bytes)
        except Exception as e:
            veredictos.append(Veredicto(str(ruta), False, f"No se pudo descargar el archivo: {e}"))
            continue
        veredictos.append(validar_archivo(destino, str(ruta), partes[1], config, cursos))

    texto = _informe(veredictos, notas)
    # Un PR de un mantenedor que no toca apuntes (p. ej. cambios de código) no necesita comentario.
    if veredictos or not mantenedor:
        gh.comentar(numero, texto, MARCADOR)
    if veredictos:
        ok = all(v.valido for v in veredictos)
        gh.poner_etiquetas(numero,
                           poner=["apunte-valido" if ok else "apunte-rechazado"],
                           quitar=["apunte-rechazado" if ok else "apunte-valido"])
    ok = all(v.valido for v in veredictos)
    # Estado en el último commit del PR: sirve como check obligatorio tanto para PRs
    # normales como para los que crea el formulario «Subir un apunte».
    try:
        gh.post(f"/repos/{gh.repo}/statuses/{pr['head']['sha']}", {
            "state": "success" if ok else "failure",
            "context": CONTEXTO_ESTADO,
            "description": ("Apuntes válidos" if ok else "Revisa el comentario del robot en el PR")[:140],
        })
    except Exception as e:
        print(f"Aviso: no se pudo publicar el estado del commit: {e}")
    print(texto)
    escribir_salida("valido", str(ok).lower())
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pr", type=int)
    ap.add_argument("--archivo", type=Path)
    ap.add_argument("--carpeta")
    a = ap.parse_args()
    if a.pr:
        sys.exit(validar_pr(a.pr))
    if a.archivo and a.carpeta:
        v = validar_archivo(a.archivo, a.archivo.name, a.carpeta, cargar_config(), cargar_cursos())
        print(_informe([v], []))
        sys.exit(0 if v.valido else 1)
    ap.error("Usa --pr N o --archivo RUTA --carpeta CARPETA")


if __name__ == "__main__":
    main()

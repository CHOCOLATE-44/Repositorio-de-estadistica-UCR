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
                   curso_por_carpeta, curso_por_sigla, escribir_salida, normalizar_sigla, normalizar_texto)
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
    return (f"No tiene permiso para {ACCIONES[estado]} este apunte: solo {quien} o los "
            "mantenedores del repositorio pueden hacerlo. Si tiene un error, avise en un issue.")

PALABRAS_VACIAS = set("""
para como pero este esta estos estas donde cuando entre sobre desde hasta segun
tiene tienen debe deben sera seran puede pueden cada otro otra otros otras mismo
curso cursos estudiante estudiantes profesor profesora semestre ciclo creditos
evaluacion horas clase clases sesion sesiones semana semanas universidad escuela
estadistica costa rica correo consulta consultas nota notas trabajo trabajos
porcentaje fecha fechas objetivo objetivos general generales especifico
especificos contenido contenidos bibliografia metodologia horario grupo
ejemplo ejemplos entonces siguiente siguientes valores numero numeros tambien
ademas manera primer primera segundo segunda tercer formula formulas resultado
resultados pagina paginas figura tabla tablas cuando siempre ningun alguna
algunos algunas cualquier respecto mediante utilizar utiliza usando dentro
examen examenes parcial parciales tarea tareas quices porcentaje entrega entregas
asistencia calificacion ausencias reposicion lecciones martes miercoles jueves
viernes lunes sabado virtual presencial correo mediacion plataforma
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

_cache_cartas: dict[str, str] = {}
SEPARADOR_CARTAS = "\n\u241e\n"  # separa el texto de varias cartas del mismo curso


def buscar_cartas(curso: dict, config: dict) -> list[Path]:
    """Archivos de carta del curso en `cartas/`: cualquier nombre que contenga la sigla (o una
    equivalente): `XS-2130.pdf`, `Programa_XS-2130v2.pdf`, `carta-xs2130-2026.pdf`…
    Si hay varias versiones, se usan todas."""
    carpeta = RAIZ / config["validacion"].get("carpeta_cartas", "cartas")
    if not carpeta.is_dir():
        return []
    siglas = [normalizar_sigla(x) for x in [curso["sigla"], *curso.get("siglas_equivalentes", [])]]
    return [ruta for ruta in sorted(carpeta.iterdir())
            if ruta.suffix.lower() in (".pdf", ".md", ".txt")
            and any(re.search(rf"{x}(?!\d)", normalizar_sigla(re.sub(r"\s*\(\d+\)$", "", ruta.stem)))
                    for x in siglas)]  # «Programa_XS-3310 (1).pdf» = copia descargada dos veces


def buscar_carta(curso: dict, config: dict) -> Path | None:
    cartas = buscar_cartas(curso, config)
    return cartas[0] if cartas else None


def cargar_carta(curso: dict, config: dict) -> str:
    """Texto de las cartas al estudiante del curso ('' si no hay o la función está apagada)."""
    if not config["validacion"].get("usar_carta_estudiante"):
        return ""
    if curso["sigla"] not in _cache_cartas:
        textos = []
        for ruta in buscar_cartas(curso, config):
            if ruta.suffix.lower() == ".pdf":
                textos.append(extraer(ruta, paginas_imagen=0).texto)
            else:
                textos.append(ruta.read_text(encoding="utf-8", errors="replace"))
        _cache_cartas[curso["sigla"]] = SEPARADOR_CARTAS.join(t for t in textos if t.strip())
    return _cache_cartas[curso["sigla"]]


def temario(carta: str) -> str:
    """Sección de contenidos de la(s) carta(s): desde «contenidos»/«temario» hasta la bibliografía.
    (No se corta en «evaluación» porque suele aparecer dentro del temario: «evaluación de estimadores».)
    Si hay varias cartas unidas, se toma la sección de cada una."""
    secciones = []
    for parte in carta.split(SEPARADOR_CARTAS):
        t = normalizar_texto(parte)
        if not t:
            continue
        inicio = min((m.start() for m in re.finditer(
            r"\b(contenidos?|temario|programa del curso|unidades tematicas)\b", t)), default=0)
        fin = min((m.start() for m in re.finditer(r"\b(bibliografia|referencias bibliograficas)\b", t)
                   if m.start() > inicio + 200), default=len(t))
        secciones.append(t[inicio:fin])
    return " ".join(secciones)


ADMINISTRATIVO = re.compile(r"\b(examen\w*|parcial\w*|tareas?|quiz\w*|quices|evaluacion(?! de)|porcentaje|"
                           r"calificacion\w*|asistencia|horario|consulta|correo|creditos?)\b|%")


def temas_de_carta(carta: str) -> list[str]:
    """Temas del temario de la carta: frases cortas separadas por comas, puntos, dos puntos…
    («técnicas de conteo», «distribución de Poisson», «pruebas de hipótesis»)."""
    t = re.sub(r"\b(unidad|tema|capitulo|semana|modulo)\s+\w+", " ", temario(carta))
    temas = []
    for frase in re.split(r"[,;:.\n()/•·\-–]|\by\b|\be\b", t):
        frase = frase.strip()
        palabras = [w for w in re.findall(r"[a-z]+", frase) if len(w) >= 4 and w not in PALABRAS_VACIAS]
        if ADMINISTRATIVO.search(frase):
            continue  # «tres exámenes parciales», «tareas 15 %»… no son temas del curso
        if 1 <= len(palabras) <= 5 and len(frase) >= 5 and frase not in temas:
            temas.append(frase)
    return temas


def temas_carta_en_apunte(texto_norm: str, carta: str) -> list[str]:
    """Temas de la carta que aparecen en el apunte (todas sus palabras clave presentes;
    se acepta singular/plural cortando la «s» final)."""
    encontrados = []
    for tema in temas_de_carta(carta):
        claves = [w for w in re.findall(r"[a-z]+", tema) if len(w) >= 4 and w not in PALABRAS_VACIAS]
        if claves and all(re.search(rf"\b{w.rstrip('s')}", texto_norm) for w in claves):
            encontrados.append(tema)
    return encontrados


# --------------------------------------------------------------------------
# Decisión
# --------------------------------------------------------------------------

@dataclass
class Veredicto:
    archivo: str
    valido: bool
    motivo: str
    detalles: list[str] = field(default_factory=list)
    preguntar: bool = False              # rechazo por contenido: se pregunta al autor qué pasó
    curso_sugerido: str | None = None    # sigla del curso donde probablemente encaja


def _prompt(curso: dict, otros: list[dict], texto: str, carta: str, hay_imagenes: bool) -> str:
    lista_otros = "\n".join(f"- {c['sigla']} {c['nombre']}" for c in otros)
    carta_txt = (f"\nCARTA AL ESTUDIANTE DEL CURSO — TEMARIO OFICIAL (criterio principal):\n\"\"\"\n{temario(carta)[:9000]}\n\"\"\"\n"
                 if carta else "")
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
{"- HAY CARTA AL ESTUDIANTE: compara el documento con su temario. 'corresponde' es true solo si los temas"
 " del documento están en la carta (basta con que cubra una parte del temario). En 'temas_carta' lista"
 " hasta 5 temas de la carta que el documento trata (vacío si ninguno)." if carta else ""}
- Si claramente pertenece a otro curso de la lista, indica su sigla en "curso_probable".
Responde SOLO con JSON:
{{"es_apunte": bool, "corresponde": bool, "confianza": número entre 0 y 1,
  "curso_probable": "sigla o null", "temas_carta": ["..."],
  "motivo": "explicación breve en español (máx. 2 oraciones), tratando de usted a quien subió el apunte"}}"""


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
                         f"El archivo pesa más de {val['tamano_maximo_mb']} MB. Comprímalo (p. ej. con ilovepdf.com).")

    r = extraer(archivo, val["min_caracteres_texto_directo"], val["max_paginas_ocr"],
                val["paginas_imagen_para_gemini"] if gemini.disponible() else 0)
    detalles = [f"Extracción: **{r.metodo}** ({len(r.texto.strip())} caracteres"
                + (f", {r.paginas} páginas" if r.paginas else "") + ")"] + r.avisos

    texto_norm = normalizar_texto(r.texto)
    carta = cargar_carta(curso, config)
    terminos_carta = _terminos(temario(carta)) if carta else []

    puntos, señales = puntuar_curso(texto_norm, curso, terminos_carta)
    identidad = any(x.startswith(("sigla", "nombre")) for x in señales)  # el apunte nombra al curso
    otros = [c for c in cursos if c["carpeta"] != carpeta]
    (puntos_otro, señales_otro), mejor_otro = max(
        ((puntuar_curso(texto_norm, c), c) for c in otros), key=lambda t: t[0][0])
    detalles.append(f"Señales del curso ({puntos} pts): " + ("; ".join(señales) or "ninguna"))
    # «Es de otro curso» solo si ese otro curso aparece por su sigla o nombre y domina claramente;
    # compartir temas (p. ej. distribuciones) no basta, porque varios cursos los repiten.
    # Si el apunte se nombra como de otro curso (sigla o nombre) y no nombra al suyo, basta con
    # que ese curso puntúe más.
    otro_curso = (puntos_otro > puntos and not identidad
                  and any(x.startswith(("sigla", "nombre")) for x in señales_otro))
    heur_valido = puntos >= val["umbral_heuristico"] and not otro_curso
    heur_motivo = (f"Se encontraron señales del curso ({puntos} pts)." if heur_valido else
                   f"Parece más de {mejor_otro['sigla']} {mejor_otro['nombre']} ({puntos_otro} pts vs {puntos})."
                   if otro_curso else
                   f"No se encontraron suficientes señales del curso ({puntos} de {val['umbral_heuristico']} pts necesarios).")

    # Carta al estudiante: si existe, es requisito para aprobar.
    if carta:
        cubiertos = temas_carta_en_apunte(texto_norm, carta)
        total = len(temas_de_carta(carta))
        minimo = val.get("min_temas_carta", 3)
        nombres = ", ".join(f"`{r.name}`" for r in buscar_cartas(curso, config))
        detalles.append(f"Carta al estudiante ({nombres}): el apunte trata "
                        f"{len(cubiertos)} de {total} temas del temario (mínimo {minimo})"
                        + (f": {', '.join(cubiertos[:8])}" if cubiertos else ""))
        # Si hay cartas de otros cursos, el apunte debe encajar mejor en la de su carpeta.
        propia = len(cubiertos) / max(total, 1)
        mejor_carta = None
        for c in otros:
            otra = cargar_carta(c, config)
            if otra:
                frac = len(temas_carta_en_apunte(texto_norm, otra)) / max(len(temas_de_carta(otra)), 1)
                if frac >= propia + 0.15 and (mejor_carta is None or frac > mejor_carta[1]):
                    mejor_carta = (c, frac)
        if mejor_carta:
            detalles.append(f"Encaja mejor en la carta de {mejor_carta[0]['sigla']} ({mejor_carta[1]:.0%} de sus temas "
                            f"vs {propia:.0%} de la carta de {curso['sigla']}).")
            otro_curso, mejor_otro = True, mejor_carta[0]
            heur_valido = False
            heur_motivo = (f"Coincide más con la carta al estudiante de {mejor_otro['sigla']} {mejor_otro['nombre']} "
                           f"que con la de {curso['sigla']}.")
        elif len(cubiertos) < minimo:
            heur_valido = False
            heur_motivo = (f"El contenido no coincide con la carta al estudiante de {curso['sigla']}: "
                           f"trata {len(cubiertos)} de sus temas (se necesitan {minimo}).")
        elif not otro_curso:
            heur_valido = True
            heur_motivo = f"El contenido coincide con la carta al estudiante ({len(cubiertos)} temas del temario)."
    elif val.get("usar_carta_estudiante"):
        detalles.append(f"⚠️ {curso['sigla']} aún no tiene carta al estudiante en `{val.get('carpeta_cartas', 'cartas')}/`; "
                        "se validó con los temas generales del curso.")
        if val.get("exigir_carta"):
            return Veredicto(nombre_en_repo, False,
                             f"No se puede validar: falta la carta al estudiante de {curso['sigla']}.", detalles)

    # Sin carta y con señales muy claras, no gastamos cuota de Gemini (el plan gratuito tiene límite diario).
    # Con carta siempre se compara con ella.
    if not carta and heur_valido and identidad and puntos >= 2 * val["umbral_heuristico"]:
        detalles.append("Gemini no consultado: las señales del curso son claras (se ahorra cuota).")
        return Veredicto(nombre_en_repo, True, heur_motivo, detalles)

    if gemini.disponible() and (r.texto.strip() or r.imagenes):
        try:
            res = gemini.preguntar_json(_prompt(curso, otros, r.texto, carta, bool(r.imagenes)),
                                        val["gemini_modelo"], r.imagenes)
            valido = bool(res.get("es_apunte")) and bool(res.get("corresponde"))
            motivo = str(res.get("motivo", "")).strip()
            sugerido = curso_por_sigla(str(res.get("curso_probable") or ""), cursos) if not valido else None
            if sugerido and sugerido["sigla"] != curso["sigla"]:
                motivo += f" (Curso probable: {sugerido['sigla']} {sugerido['nombre']}.)"
            else:
                sugerido = None
            if carta and res.get("temas_carta"):
                detalles.append("Temas de la carta que cubre (según Gemini): " + ", ".join(map(str, res["temas_carta"][:5])))
            detalles.append(f"Gemini: confianza {res.get('confianza')}; heurística: {'✅' if heur_valido else '❌'}")
            return Veredicto(nombre_en_repo, valido, motivo or "Sin motivo.", detalles,
                             preguntar=not valido and bool(res.get("es_apunte")),
                             curso_sugerido=sugerido["sigla"] if sugerido else None)
        except Exception as e:
            detalles.append(f"Gemini no disponible ({e}); se usó solo la heurística.")

    if not r.texto.strip():
        return Veredicto(nombre_en_repo, False,
                         "No se pudo extraer texto del documento (¿escaneo ilegible o PDF protegido?).", detalles)
    return Veredicto(nombre_en_repo, heur_valido, heur_motivo, detalles, preguntar=not heur_valido,
                     curso_sugerido=mejor_otro["sigla"] if otro_curso and not heur_valido else None)


# --------------------------------------------------------------------------
# Modo Pull Request
# --------------------------------------------------------------------------

ETIQUETA_REVISION = "revision-manual"


def pregunta_al_autor(veredictos: list[Veredicto], autor: str | None) -> str:
    """Bloque que pregunta a quien subió el apunte si es contenido nuevo o curso equivocado."""
    dudosos = [v for v in veredictos if not v.valido and v.preguntar]
    if not dudosos:
        return ""
    sugeridos = sorted({v.curso_sugerido for v in dudosos if v.curso_sugerido})
    ejemplo = sugeridos[0] if sugeridos else "XS-0122"
    quien = f"@{autor}, " if autor else ""
    return (f"### 🤔 {quien}¿qué pasó con este apunte?\n\n"
            "Responda con **un comentario** en este PR (o en su issue de subida) que empiece con una de estas opciones:\n\n"
            "- **`/contenido-nuevo`** — el tema **sí es del curso**, pero no aparece en la carta al estudiante "
            "(por ejemplo, el profesor lo agregó este semestre). Puede explicarlo en el mismo comentario. "
            "Un mantenedor lo revisará a mano.\n"
            f"- **`/curso {ejemplo}`** — **se equivocó de curso**. Escriba la sigla del curso correcto y el robot "
            "moverá el apunte y lo validará de nuevo."
            + (f"\n\nSegún la revisión, podría ser de: {', '.join(f'`{x}`' for x in sugeridos)}." if sugeridos else ""))


def _informe(veredictos: list[Veredicto], notas: list[str], autor: str | None = None) -> str:
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
    pregunta = pregunta_al_autor(veredictos, autor)
    if pregunta:
        partes.append(pregunta)
    elif veredictos and not ok:
        partes.append("Si cree que es un error, responda en este PR explicando por qué; "
                      "el mantenedor lo revisará manualmente.")
    partes.append("\n<sub>Validación automática · texto directo → OCR (Tesseract) → Gemini (Google AI Studio)</sub>")
    return "\n".join(partes)


def publicar(gh: GitHub, pr: dict) -> bool:
    """Fusiona el PR ya validado, borra su rama y relanza la publicación del ranking."""
    numero = pr["number"]
    try:  # con el sha: solo se fusiona exactamente lo que se validó
        gh.put(f"/repos/{gh.repo}/pulls/{numero}/merge",
               {"merge_method": "merge", "sha": pr["head"]["sha"], "commit_title": f"Publicar apunte (#{numero})"})
    except Exception as e:
        print(f"Aviso: no se pudo publicar el PR automáticamente: {e}")
        return False
    if (pr["head"].get("repo") or {}).get("full_name") == gh.repo:
        gh.delete(f"/repos/{gh.repo}/git/refs/heads/{pr['head']['ref']}")
    try:  # lo que fusiona el robot no dispara otros workflows: se lanza la publicación a mano
        gh.post(f"/repos/{gh.repo}/actions/workflows/publicar.yml/dispatches", {"ref": pr["base"]["ref"]})
    except Exception as e:
        print(f"Aviso: no se pudo relanzar la publicación: {e}")
    return True


def issue_de_subida(pr: dict) -> int | None:
    """Número del issue «Subir un apunte» que originó el PR (ramas `apunte/issue-N`)."""
    m = re.fullmatch(r"apunte/issue-(\d+)", (pr.get("head") or {}).get("ref", ""))
    return int(m.group(1)) if m else None


def autor_real(gh: GitHub, pr: dict) -> str:
    """Quien subió el apunte: el autor del issue de subida, o el autor del PR."""
    issue = issue_de_subida(pr)
    if issue:
        try:
            return gh.get(f"/repos/{gh.repo}/issues/{issue}")["user"]["login"]
        except Exception:
            pass
    return pr["user"]["login"]


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

    otros_archivos = False  # el PR cambia algo fuera de apuntes/ (código): nunca se publica solo
    for f in gh.paginar(f"/repos/{gh.repo}/pulls/{numero}/files"):
        ruta = PurePosixPath(f["filename"])
        partes = ruta.parts
        es_apunte = (len(partes) == 3 and partes[0] == CARPETA_APUNTES and ruta.name.lower() != "readme.md")
        if not es_apunte:
            otros_archivos = True
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
        print(f"Validando {ruta}…", flush=True)
        veredictos.append(validar_archivo(destino, str(ruta), partes[1], config, cursos))

    autor = autor_real(gh, pr)
    texto = _informe(veredictos, notas, autor)
    # Un PR de un mantenedor que no toca apuntes (p. ej. cambios de código) no necesita comentario.
    if veredictos or not mantenedor:
        gh.comentar(numero, texto, MARCADOR)
    # En subidas por formulario, el estudiante sigue su issue: le avisamos allí también.
    issue = issue_de_subida(pr)
    pregunta = pregunta_al_autor(veredictos, autor)
    if issue and pregunta:
        gh.comentar(issue, f"El robot revisó su apunte en el PR #{numero} y **no lo aprobó**. "
                           f"Puede ver el motivo allí.\n\n{pregunta}", "<!-- pregunta-validacion -->")
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
            "description": ("Apuntes válidos" if ok else "Revise el comentario del robot en el PR")[:140],
        })
    except Exception as e:
        print(f"Aviso: no se pudo publicar el estado del commit: {e}")
    if ok and veredictos and not otros_archivos and config.get("publicacion", {}).get("automatica"):
        if publicar(gh, pr):
            gh.comentar(numero, "### 🚀 Publicado\n\nEl contenido coincide con el curso, así que el apunte se "
                                "publicó automáticamente. Aparecerá en el ranking en un par de minutos.",
                        "<!-- publicacion -->")
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

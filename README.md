# Repositorio carrera de Estadística UCR

Apuntes de los cursos del **Bachillerato en Estadística (plan 02) de la Universidad de Costa Rica**,
hechos por estudiantes y **puntuados por la comunidad**, para que quien llegue después vaya directo a los mejores.

**👉 Ranking de apuntes:** https://chocolate-44.github.io/Repositorio-de-estadistica-UCR/

## ¿Cómo participar?

| Para… | ¿Se necesita Git? | Cómo |
|---|---|---|
| **Leer** apuntes | No, ni cuenta | Abra el ranking y pulse «Abrir». |
| **Buscar o preguntar** | No | Escriba en el buscador: «mejor apunte de regresión», «DOE con más de 4 estrellas». |
| **Puntuar** un apunte | No (solo cuenta gratis de GitHub) | Pulse «Puntuar», elija 1–5 ★ y **explique por qué** (obligatorio). |
| **Subir** un apunte | No | Pulse «Subir un apunte», elija el curso y arrastre su archivo (PDF, Word, PowerPoint, fotos, R Markdown, HTML…). |
| Subir por Pull Request | Sí | Ver [CONTRIBUIR.md](CONTRIBUIR.md). |

Cada apunte que se sube pasa por una **validación automática** que comprueba que su contenido
corresponde al curso de la carpeta, comparándolo con la **carta al estudiante** del curso
(extracción de texto → OCR si es escaneado o a mano → Gemini de Google).

## Estructura

```
apuntes/
  XS-0124-analisis-exploratorio-de-datos/
  XS-2130-modelos-de-regresion-aplicados/
  XS-3150-diseno-de-experimentos/
  …                         ← una carpeta por curso (31), creadas desde cursos.json
cursos.json                 ← catálogo de cursos: sigla, nombre y temas
config.json                 ← reglas de votos, validación y ranking
cartas/                     ← cartas al estudiante: los apuntes se comparan con su temario
sitio/                      ← página del ranking (HTML/JS sin dependencias)
scripts/                    ← validación de apuntes y votos, construcción del sitio
.github/ISSUE_TEMPLATE/     ← formularios «Puntuar», «Subir un apunte» y «Preguntar»
.github/workflows/          ← automatizaciones
docs/                       ← decisiones de diseño y guía del mantenedor
```

## Cursos incluidos
Todos los cursos propios del plan 02 (XS), las matemáticas del plan (MA-0155, MA-1004, MA-1023)
e Inglés para Estadística (LM-3039 a LM-3042). No se incluyen Precálculo, cursos de formación
general (humanidades, arte, deporte, repertorio, seminarios de realidad nacional) ni optativos.

## Cómo funciona por dentro

```
 Subir apunte ──► PR ──► [Validar apuntes] texto del archivo → OCR Tesseract → Gemini ──► comentario en el PR
                                                                        │
                                                  si coincide, se publica solo
                                                                        ▼
 Puntuar ──► issue «voto» ──► [Procesar voto] valida y cierra ──► [Publicar] recalcula ranking ──► GitHub Pages
```

- Votos: un issue por voto (formulario). Un voto por cuenta y apunte; vale el más reciente.
  El ranking se **recalcula desde cero** en cada publicación → sin conflictos ni votos perdidos.
  Por qué esta opción y no Supabase/Firebase/Discussions: [docs/decision-votos.md](docs/decision-votos.md).
- Ranking: promedio bayesiano para que pocos votos no dominen; se muestra el promedio real.
- Datos públicos: `…/data/puntuaciones.json` en el sitio.

## Mantenimiento
Guía de puesta en marcha y tareas habituales: [docs/configuracion.md](docs/configuracion.md).
Preguntas en lenguaje natural: [docs/fase-4-consultas.md](docs/fase-4-consultas.md).

## Licencia de los apuntes
Cada apunte pertenece a su autor(a). Al subirlo, usted acepta que se publique aquí para uso educativo.
No suba exámenes ni material que el profesorado haya pedido no compartir.

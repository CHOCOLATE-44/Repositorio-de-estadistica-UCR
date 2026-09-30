# Puesta en marcha (una sola vez)

Todo es gratuito y **ningún paso pide tarjeta de crédito**.

## 1. Nombre del repositorio y rama principal
1. *Settings → General → Repository name*: `Repositorio-de-estadistica-UCR`
   (GitHub no admite espacios; los convierte en guiones). Los enlaces antiguos redirigen solos.
2. La rama principal debe llamarse **`main`** (los workflows publican desde ella).
   *Settings → Branches → Default branch*.
3. Si cambias el nombre, actualiza la URL de `.github/ISSUE_TEMPLATE/config.yml`.

## 2. GitHub Pages
*Settings → Pages → Build and deployment → Source: **GitHub Actions***.
La página quedará en `https://<usuario>.github.io/<repositorio>/`.

## 3. Permisos de Actions
*Settings → Actions → General → Workflow permissions*:
- **Read and write permissions**
- ✅ **Allow GitHub Actions to create and approve pull requests** (necesario para «Subir un apunte» sin Git).

Recomendado en la misma página: *Fork pull request workflows from outside collaborators →
Require approval for first-time contributors*.

## 4. Clave gratuita de Gemini (Google AI Studio)
1. Entra a <https://aistudio.google.com/apikey> con una cuenta de Google y crea una clave
   (plan gratuito, sin tarjeta).
2. *Settings → Secrets and variables → Actions → New repository secret*:
   nombre `GEMINI_API_KEY`, valor la clave.

Sin la clave todo sigue funcionando con reglas simples (sigla, nombre y temas del curso).
Nota: en el plan gratuito Google puede usar los datos enviados para mejorar sus
productos; aquí solo se envían apuntes que de todos modos serán públicos.
Modelos en `config.json` (según los límites del plan gratuito de la cuenta):
- `gemini_modelo` = **gemini-3.5-flash-lite** (15/min, 500/día): valida apuntes contra la carta.
- `gemini_modelo_votos` = **gemini-3.1-flash-lite** (15/min, 500/día, cuota aparte): revisa justificaciones.
- `gemini_modelo_preguntas` = **gemini-3.8-flash** (5/min, 20/día): «Pregúntale a la IA».

Si un modelo se queda sin cuota del día, el robot prueba otro una vez y luego sigue con las reglas simples; si choca con el límite por minuto, espera 30 s. Si Google retira un modelo, se elige solo el más nuevo del mismo tipo. Uso actual: https://ai.dev/rate-limit

## 5. Etiquetas
Se crean solas la primera vez que se usan: `voto`, `voto-valido`, `voto-rechazado`,
`voto-anulado`, `subir-apunte`, `pregunta`, `apunte-valido`, `apunte-rechazado`.

## 6. Protección de la rama (necesaria para que las reglas se cumplan)
*Settings → Rules → Rulesets → New branch ruleset*:
- **Enforcement status:** Active · **Target branches:** *Include default branch*.
- ✅ **Restrict deletions** y ✅ **Block force pushes**.
- ✅ **Require a pull request before merging**.
- ✅ **Require status checks to pass** → *Add checks* → **Validación de apuntes**
  (si no aparece en la lista, escríbelo y elige «Add Validación de apuntes»).
- **Bypass list:** agrega el rol *Repository admin* para que tú puedas fusionar a mano si el robot se equivoca.

Así, un PR que cambie o borre el apunte de otra persona, o que no sea del curso, no se puede fusionar por accidente.

**Quién puede cambiar un apunte existente:** quien lo subió (según el historial de git) y los
mantenedores (dueño, miembros de la organización y colaboradores del repo). Cualquiera puede *agregar* apuntes nuevos.

## 7. Primer despliegue
*Actions → Publicar ranking (GitHub Pages) → Run workflow*.

---

## Tareas habituales del mantenedor

| Quiero… | Cómo |
|---|---|
| Aprobar un apunte | Revisa el comentario del robot en el PR y haz *Merge*. |
| Revisar un apunte marcado `revision-manual` | El autor dice que es contenido nuevo del curso. Revísalo: si corresponde, fusiona con *bypass*; si no, ciérralo explicando. |
| Anular un voto abusivo | Pon la etiqueta `voto-anulado` al issue del voto. |
| Que el buscador entienda otro apodo de un curso | Agrégalo en `alias` del curso en `cursos.json`. |
| Agregar/editar un curso | Edita `cursos.json`, crea la carpeta en `apuntes/` y ejecuta `python scripts/generar_plantillas.py`. |
| Mejorar la validación de un curso | Agrega temas típicos en `cursos.json`. |
| Subir la carta al estudiante de un curso | Ver `cartas/README.md` (ya está activa: los apuntes se comparan con ella). |
| Ajustar reglas de votos | `config.json → votos` (largo mínimo, edad mínima de la cuenta, autovoto…). |

## Límites del plan gratuito (holgados para esta comunidad)
- **Actions:** ilimitado en repos públicos. Cada validación de PDF tarda ~1–3 min.
- **Pages:** sitio de hasta 1 GB y 100 GB/mes de tráfico (los PDF no se copian al sitio; se enlazan al repo).
- **Repositorio:** recomendado < 5 GB; archivos de máx. 100 MB (aquí se limita a 50 MB).
- **Gemini (AI Studio):** cuota diaria gratuita de cientos de peticiones; cada apunte o voto usa una.

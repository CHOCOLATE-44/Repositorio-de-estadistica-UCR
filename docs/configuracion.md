# Puesta en marcha (una sola vez)

Todo es gratuito y **ningún paso pide tarjeta de crédito**.

## 1. Nombre del repositorio y rama principal
1. *Settings → General → Repository name*: `Repositorio-carrera-de-estadistica-UCR`
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
El modelo se cambia en `config.json → validacion.gemini_modelo` si Google retira el actual.

## 5. Etiquetas
Se crean solas la primera vez que se usan: `voto`, `voto-valido`, `voto-rechazado`,
`voto-anulado`, `subir-apunte`, `apunte-valido`, `apunte-rechazado`.

## 6. Protección de la rama (recomendado)
*Settings → Rules → New branch ruleset* sobre `main`: exigir Pull Request y, como
check obligatorio, **Validar apuntes / validar**. Así nadie publica un apunte que no pasó la validación
(tú como admin siempre puedes aprobarlo manualmente si fue un falso rechazo).

## 7. Primer despliegue
*Actions → Publicar ranking (GitHub Pages) → Run workflow*.

---

## Tareas habituales del mantenedor

| Quiero… | Cómo |
|---|---|
| Aprobar un apunte | Revisa el comentario del robot en el PR y haz *Merge*. |
| Anular un voto abusivo | Pon la etiqueta `voto-anulado` al issue del voto. |
| Agregar/editar un curso | Edita `cursos.json`, crea la carpeta en `apuntes/` y ejecuta `python scripts/generar_plantillas.py`. |
| Mejorar la validación de un curso | Agrega temas típicos en `cursos.json`. |
| Activar la validación con la carta al estudiante | Ver `cartas/README.md`. |
| Ajustar reglas de votos | `config.json → votos` (largo mínimo, edad mínima de la cuenta, autovoto…). |

## Límites del plan gratuito (holgados para esta comunidad)
- **Actions:** ilimitado en repos públicos. Cada validación de PDF tarda ~1–3 min.
- **Pages:** sitio de hasta 1 GB y 100 GB/mes de tráfico (los PDF no se copian al sitio; se enlazan al repo).
- **Repositorio:** recomendado < 5 GB; archivos de máx. 100 MB (aquí se limita a 50 MB).
- **Gemini (AI Studio):** cuota diaria gratuita de cientos de peticiones; cada apunte o voto usa una.

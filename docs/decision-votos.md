# Decisión: dónde guardar los votos

GitHub Pages solo sirve archivos estáticos: la página no puede escribir en el
repositorio. Hace falta un lugar externo a la página que reciba los votos. Estas
son las opciones evaluadas para una comunidad de decenas a cientos de personas,
mantenida por una sola persona y sin tarjeta de crédito.

## Opciones

### A. Backend gratuito externo (Supabase / Firebase) + página en GitHub Pages

| | |
|---|---|
| **Cómo** | La página llama a la API de Supabase (Postgres) o Firestore. Inicio de sesión con Google para evitar votos duplicados. |
| **Ventajas** | Votar sin salir de la página; experiencia más pulida; iniciar sesión con Google (todo estudiante UCR tiene cuenta). Se puede exigir justificación con una restricción `CHECK` en la base de datos. |
| **Desventajas** | Otro servicio que mantener (claves, reglas de seguridad/RLS, migraciones). Supabase **pausa proyectos gratuitos tras ~7 días sin actividad** (en vacaciones el sitio dejaría de votar hasta que lo reactives). Firebase Spark no pide tarjeta, pero las reglas de seguridad mal escritas son el error más común y el cliente tiene acceso directo a la base. La moderación (anular un voto abusivo) exige entrar a un panel aparte. Los datos viven fuera del repositorio. |
| **Tarjeta** | No (ambos planes gratuitos). |

### B. GitHub Discussions con reacciones (p. ej. giscus)

| | |
|---|---|
| **Cómo** | Cada apunte tiene una discusión; la gente reacciona 👍/❤️ o comenta. La página lee las reacciones con la API. |
| **Ventajas** | Todo dentro de GitHub; giscus es fácil de incrustar. |
| **Desventajas** | Las reacciones **no son 1–5 estrellas** y **no se puede exigir una justificación**: un 👍 no dice por qué. Mezclar reacciones con puntajes es frágil. Leer reacciones desde la página exige token (límite de 60 peticiones/hora sin él). |
| **Tarjeta** | No. |

### C. **Formularios de issues + GitHub Actions** ✅ recomendada

| | |
|---|---|
| **Cómo** | El botón «Puntuar» abre un formulario de issue ya rellenado con el apunte. El formulario pide estrellas (1–5) y una **justificación obligatoria**. Un workflow valida el voto, comenta el resultado, cierra el issue y regenera `puntuaciones.json` en GitHub Pages recalculando todo desde los issues. |
| **Ventajas** | Cero servicios externos: todo vive en el repo y usa solo minutos gratuitos de Actions (ilimitados en repos públicos). **Un voto por cuenta de GitHub y apunte** (vale el más reciente). Justificación obligatoria, pública y con nombre de usuario → desincentiva votos «por gusto». Se puede revisar además con Gemini (gratis). Moderación trivial: poner la etiqueta `voto-anulado`. Historial auditable y respaldo automático. Como el ranking se recalcula desde cero, nunca hay conflictos de escritura ni votos perdidos. |
| **Desventajas** | Hay que tener cuenta de GitHub (gratis; no hace falta saber Git). El voto no es instantáneo: tarda ~1–2 minutos en reflejarse. La interfaz de votar es la de GitHub, no la de la página. Cada voto es un issue (se cierran solos, así que no ensucian la lista de abiertos). |
| **Tarjeta** | No. |

### D. Otras consideradas

- **Google Forms + Google Sheets:** sin cuenta de GitHub y con inicio de sesión de Google, pero publicar la hoja expone correos si no se hace un paso intermedio con Apps Script; la deduplicación por apunte y la moderación quedan fuera del repo. Buena opción si los usuarios se resisten a crear cuenta de GitHub.
- **Cloudflare Workers + D1/KV:** gratis y rápido, pero hay que programar y mantener autenticación y un backend propio. Demasiado para un mantenedor sin equipo.
- **Utterances/staticman:** proyectos poco mantenidos o que necesitan servidor propio.

## Recomendación

**Opción C.** Es la única que cumple todo sin agregar servicios externos:
justificación obligatoria, antiduplicados razonable (una cuenta = un voto por apunte),
moderación con una etiqueta y cero mantenimiento de infraestructura. La cuenta de
GitHub también es necesaria para subir apuntes, así que es una sola barrera de entrada.

Si en el futuro la fricción de la cuenta de GitHub resulta un problema, la migración
natural es la opción A con Supabase: `scripts/construir_sitio.py` ya separa la
recolección de votos (`recolectar_votos`) del cálculo del ranking, así que solo
cambiaría esa función.

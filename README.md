# Analista económico Colombia 🇨🇴

Este es un agente de IA que construí con Claude Managed Agents. Corre solo en la nube: de lunes a viernes a las 6:30 a. m. revisa los indicadores económicos y logísticos de Colombia y me envía un boletín por correo.

Lo hice en el workshop de Managed Agents en la Universidad de La Salle (Bogotá, octubre de 2026). Lo pensé para buyers y equipos de compras y logística, que necesitan saber cómo amanece la TRM o si hay problemas en las vías antes de tomar decisiones.

## Qué hace

Cada mañana el agente:

- Consulta la TRM oficial en la API de datos abiertos de la Superfinanciera.
- Busca la inflación, la tasa del Banco de la República, el euro y el estado de las vías en fuentes confiables (DANE, Banco de la República, Ministerio de Transporte, Invías y prensa económica).
- Guarda los valores en un historial y calcula cómo se han movido en la semana.
- Me envía un correo con todo, indicando de dónde salió cada cifra.

## Algunas decisiones que tomé

**Las cuentas las hace Python, no el modelo.** Un modelo de lenguaje puede equivocarse con los números, así que las variaciones, rachas y alertas las calcula un script. Así el resultado es siempre el mismo.

**No inventa tendencias.** Si un indicador tiene menos de 5 días de historial, el correo lo dice en vez de sacar conclusiones con pocos datos.

**Cada cifra dice qué tan confiable es.** Puede ser "Fuente oficial", "Vía prensa" o "Sin verificar". En una prueba vi que el agente marcaba datos como oficiales sin haber abierto la página, así que agregué una regla en código: solo dice "Fuente oficial" si la página realmente se abrió.

**Solo busca en sitios confiables.** La búsqueda está limitada a 13 dominios, y la memoria solo guarda números, fechas y fuentes, nunca texto de páginas web.

**La clave del correo no está en el repo.** Vive en un vault y el agente nunca ve su valor real.

## Cómo está organizado

- `agents/analista-colombia/`: el agente (instrucciones, herramientas, memoria y horario). Su README tiene todos los detalles técnicos.
- `skills/reporte-correo-html/`: los scripts de Python que calculan la tendencia, arman el correo y lo envían.
- `scripts/`: herramientas para probar y depurar.
- `tests/unit/`: 55 pruebas que corren sin internet.

## Estado

Funciona y lo probé de punta a punta. Lo tengo pausado para controlar costos (cada corrida cuesta entre USD 0,41 y 0,72), y lo activo cuando lo necesito.

## Lo que me gustaría agregar

- Más días de historial para ver tendencias del mes.

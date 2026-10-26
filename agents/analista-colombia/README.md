# analista-colombia

Analista económico diario para Colombia: cada día hábil lee la TRM oficial, busca en fuentes oficiales y de prensa los indicadores de divisas, logística/vías y macroeconomía, calcula la **tendencia de la semana** con un script, y envía por correo un boletín en HTML. Cada cifra lleva su fuente, su fecha y una etiqueta que dice si la fuente es oficial, vía prensa o sin verificar.

- **Estado:** funciona. Probado de punta a punta en la nube (dry run y envío real).
- **Deployment:** **activo** desde el 2026-10-26 (lo encendió el usuario para probar); corre lunes a viernes 6:30. Para controlar costos se pausa cuando no se necesite: ver [Estado del Deployment](#estado-del-deployment).
- **Costo medido por corrida:** USD 0,41 a 0,72 (8 pruebas el 2026-10-24 y 26; la última, USD 0,72, con apertura de páginas oficiales). El tope por corrida es USD 3.

## Ficha

```
FICHA DEL AGENTE  analista-colombia   (archivos en agents/analista-colombia/)

Modelo        claude-sonnet-5-5 · effort medium                       model.yaml
              por qué: buscar, contrastar fuentes y redactar es trabajo agentico; un
              error en una cifra se ve en el reporte, no mueve dinero solo.
Disparador    30 6 * * 1-5 America/Bogota = "lunes a viernes a las 6:30 a. m."   schedule.yaml
              por qué: el reporte debe estar antes de que empiece la jornada; TRM y DANE
              publican en días hábiles.
Entrega       mensaje (sin outcome)                                   kickoff.md
              por qué: la verificación vive en el prompt y en scripts; la rúbrica se escribe
              después de ver más reportes reales.
Tope de costo USD 3 por corrida (amount "300")                        schedule.yaml
              por qué: la corrida medida cuesta unos USD 0,5; el tope corta una sesión que se
              desboque. Se compone de tokens + USD 10 por 1.000 búsquedas + USD 0,08 por hora.
System prompt system_prompt.md
Tools         habilitadas: bash, read, write, web_search, web_fetch · política auto   tools.yaml
              apagadas: edit, glob, grep (el trabajo no edita código ni busca archivos)
              web_*: allowed_domains = banrep.gov.co, dane.gov.co, superfinanciera.gov.co,
              datos.gov.co, invias.gov.co, mintransporte.gov.co, ani.gov.co, larepublica.co,
              portafolio.co, eltiempo.com, valoraanalitik.com, bloomberg.com, colfecar.org.co
MCP           no usa (Gmail MCP no puede enviar; se usa la API HTTP de Resend)
Skills        reporte-correo-html (propia, skills/reporte-correo-html), con cuatro scripts:
              - tendencia.py: guarda el historial, calcula tendencias y la alerta de la TRM.
                por qué: las cuentas de un script son iguales todos los días y el script
                valida cada fila que entra a la memoria; el modelo no calcula nada.
              - abrir_fuente.py: abre páginas oficiales (.gov.co) y anota en un registro cuáles se
                abrieron de verdad y cuáles bloqueó el sitio.
                por qué: la etiqueta "Fuente oficial" no puede depender de que el modelo diga la
                verdad; depende de que la página se abrió (ver Verificación).
              - render_email.py: convierte reporte.json en HTML de correo (tablas, sin imágenes).
                por qué: el diseño debe ser idéntico cada día.
              - enviar_resend.py: envía por Resend; solo reintenta ante un 429 (no duplica).
Herramientas  no usa
  propias
Subagentes    ninguno (un solo bucle; no hay lectura paralela medida)
Environment   cloud · red limited                                     environment.yaml
              hosts: los dominios de arriba (apex y *.) + api.resend.com
              MCP no · gestores de paquetes no
Memoria       colombia-indicadores en /mnt/memory/colombia-indicadores/ · read_write
              guarda historial.csv: una fila por día e indicador (fecha, indicador, valor,
              fuente), últimos 90 días. Solo tendencia.py escribe en él.
              por qué ese formato: el modelo nunca vuelve a leer texto libre guardado, así que
              una página web no puede meter instrucciones en la memoria.
              por qué read_write: el agente agrega el valor de cada día.
              Semilla: memory/historial.csv (TRM de 30 días + valores migrados de baseline.json).
Tendencia     por indicador: variación de 5 días hábiles (absoluta y %), mínimo, máximo, racha.
              Con menos de 5 días hábiles dice "historial insuficiente" y no inventa tendencia.
              Alerta: si la TRM cambia más de 1 % en un día, va en la primera línea del reporte
              y en un aviso arriba del correo.
Correo        boletín en HTML (papel blanco, texto grafito, un acento azul acero), sin gráficas ni
              imágenes: Gmail bloquea SVG y las imágenes incrustadas son frágiles.
              Secciones: En una mirada, Tendencia de la semana, las cuatro temáticas y
              "Por confirmar hoy". Un dato que no se encontró no sale como tarjeta: se lista
              en "Por confirmar hoy" y nunca dice "No encontrado".
Verificación  cada cifra lleva una etiqueta: Fuente oficial (abrió la página o datos del
              organismo hoy), Vía prensa (un medio que lo cita) o Sin verificar (solo un
              resultado de búsqueda). La TRM es oficial (datos.gov.co).
              La etiqueta se hace cumplir con código: el correo solo dice "Fuente oficial" si
              la página aparece en fuentes_abiertas.json como leída; si no, baja a "Sin
              verificar". Se encontró en la prueba del 2026-10-26: el agente marcó como oficial
              la tasa y el IPC sin abrir ninguna página; por eso existe esta regla.
              Límite conocido: banrep.gov.co bloquea robots, así que esas cifras suelen salir
              "Vía prensa".
Archivos      no usa
Credenciales  vault analista-colombia: Resend (environment_variable RESEND_API_KEY, solo
              cabecera, solo api.resend.com), permiso mínimo "Sending access"   credentials.md
              el agente nunca ve el valor (ve un marcador)
Compuerta     hace solo: buscar, redactar, enviar el correo, actualizar la memoria.
              compuerta real: destinatario fijo en el kickoff, un solo correo por corrida y
              remitente de prueba de Resend, que solo entrega al correo dueño de la cuenta.
Fuera         sin Gmail MCP (no envía), sin outcome (aún), sin subagentes, sin MCP, sin gráficas,
              sin reuters.com (la API lo rechazó: el crawler de Anthropic no puede acceder),
              sin user_location (el buscador no admite country CO).
```

## Archivos

| Archivo | Qué es |
|---|---|
| `model.yaml` | Nombre, descripción, modelo y effort |
| `system_prompt.md` | El system prompt, en Simplified Technical English |
| `tools.yaml` | Tools del sandbox y dominios de `web_search` / `web_fetch` |
| `skills.yaml` | Conecta la skill `../../skills/reporte-correo-html` |
| `environment.yaml` | El contenedor: red y hosts permitidos |
| `vault.yaml` + `credentials.md` | El vault (nunca un secreto) y cómo cargar la clave de Resend |
| `memory_store-indicadores.yaml` | La memoria entre corridas |
| `memory/historial.csv` | Semilla del historial: se sube a la memoria con `ant beta:memory-stores:memories create` |
| `schedule.yaml` + `kickoff.md` | El Deployment: cuándo y con qué mensaje |
| `tests/basico.json` | Prueba en dry run (no envía correo) |
| `tests/correo.json` | Prueba con envío real (cuesta una corrida completa) |
| `agent.md`, `deployment-diario.yaml` | Generados por `scripts/ensamblar.py`. No los edites a mano |

Fuera de esta carpeta:

| Archivo | Qué es |
|---|---|
| `skills/reporte-correo-html/SKILL.md` | Las instrucciones que el agente lee para usar la skill |
| `skills/reporte-correo-html/scripts/abrir_fuente.py` | Abre páginas `.gov.co` y anota cuáles se abrieron (`fuentes_abiertas.json`) |
| `skills/reporte-correo-html/scripts/tendencia.py` | Historial, tendencias, racha y alerta de TRM (`sembrar-trm`, `agregar`, `calcular`) |
| `skills/reporte-correo-html/scripts/render_email.py` | `reporte.json` + `tendencias.json` → `reporte.html` y `reporte.txt` |
| `skills/reporte-correo-html/scripts/enviar_resend.py` | Envío por Resend |
| `skills/reporte-correo-html/ejemplo.json` | Ejemplo del `reporte.json` (sirve para ver el diseño) |
| `scripts/verificar_prueba.py` | Revisa la salida de una prueba en la nube con ~45 comprobaciones |
| `scripts/probar.py`, `trazas.py`, `inspeccionar.py`, `ensamblar.py` | Herramientas de la skill `managed-agents-wizard` |
| `scripts/cargar-resend.ps1` | Carga la clave de Resend al vault sin que pase por el chat |
| `tests/unit/` | Pruebas unitarias (sin internet): `test_tendencia.py`, `test_render.py` y `test_abrir_fuente.py` |

## Estado del Deployment

El Deployment `depl_01A2ZcVTJY7Cbeb1dCRReHJ3` puede estar activo o pausado. Para ver cuál:

```sh
ant beta:deployments retrieve --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3 --transform '{status:status,version:agent.version}'
```

Pausarlo (para controlar costos) y activarlo:

```sh
ant beta:deployments pause --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3
ant beta:deployments unpause --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3
```

Correr uno ahora, sin esperar al horario (envía correo real):

```sh
ant beta:deployments run --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3
```

## Cambiar algo

```sh
uv run --script scripts/ensamblar.py agents/analista-colombia
A=agents/analista-colombia
F=(skills/reporte-correo-html $A/agent.md $A/environment.yaml $A/vault.yaml $A/memory_store-indicadores.yaml $A/deployment-diario.yaml)
ant apply --dry-run -v "${F[@]}"
ant apply --yes "${F[@]}"     # solo después de leer el plan
```

## Probar y depurar

```sh
python -m unittest tests.unit.test_tendencia tests.unit.test_render tests.unit.test_abrir_fuente   # sin internet, 1 segundo
uv run --script scripts/probar.py agents/analista-colombia/tests/basico.json
python scripts/verificar_prueba.py tests/out/analista-colombia/<sesion>
uv run --script scripts/trazas.py <session_id>
uv run --script scripts/inspeccionar.py <session_id>
```

## IDs

| Recurso | ID |
|---|---|
| agent.md | `agent_018v718v6WfZ2SbkA1puZjQd` (v8) |
| skills/reporte-correo-html | `skill_01UbFiNtmj2aDaxmJNz12GvR` |
| environment.yaml | `env_01Ey6tqA2ygpwuLgGL6JkmKZ` |
| vault.yaml | `vlt_011CgMLdGnA7v6zWFqrpEL3C` |
| memory_store-indicadores.yaml | `memstore_0118tjf9YxcNhP28Joqq9AxP` |
| deployment-diario.yaml | `depl_01A2ZcVTJY7Cbeb1dCRReHJ3` |

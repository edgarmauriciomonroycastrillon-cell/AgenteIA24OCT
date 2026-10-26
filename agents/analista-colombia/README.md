# Analista Colombia: detalles técnicos

Aquí explico cómo está armado el agente por dentro. Si buscas la presentación general del proyecto, está en el [README principal](../../README.md).

**Estado:** funciona y lo probé de punta a punta en la nube, tanto en modo prueba (sin enviar correo) como con envío real.

**Deployment:** pausado para controlar costos. Cuando está activo, corre de lunes a viernes a las 6:30 a. m. Más abajo están los comandos para encenderlo o pausarlo.

**Costo:** cada corrida cuesta entre USD 0,41 y 0,72 (lo medí en 8 pruebas). Le puse un tope de USD 3 por corrida por si algo se sale de control.

## Cómo lo armé y por qué

**Modelo.** Uso `claude-sonnet-5-5` con esfuerzo medio. El trabajo es buscar, comparar fuentes y redactar, y para eso no necesita el modelo más grande.

**Horario.** Corre a las 6:30 a. m. de lunes a viernes, para que el reporte llegue antes de empezar el día. La TRM y el DANE publican en días hábiles.

**Herramientas.** El agente puede ejecutar comandos, leer y escribir archivos, y buscar y abrir páginas web. Le apagué las herramientas para editar código o buscar archivos porque no las necesita.

**Sitios permitidos.** Solo puede buscar en 13 dominios: banrep.gov.co, dane.gov.co, superfinanciera.gov.co, datos.gov.co, invias.gov.co, mintransporte.gov.co, ani.gov.co, larepublica.co, portafolio.co, eltiempo.com, valoraanalitik.com, bloomberg.com y colfecar.org.co. Además puede conectarse a api.resend.com para enviar el correo.

**Skill propia.** Todo lo que necesita ser exacto lo hacen cuatro scripts de Python dentro de `skills/reporte-correo-html`:

- `tendencia.py` guarda el historial y calcula la tendencia, las rachas y la alerta de la TRM. Lo hice así porque un script da el mismo resultado todos los días y el modelo puede equivocarse con los números.
- `abrir_fuente.py` abre las páginas oficiales y anota cuáles se abrieron de verdad.
- `render_email.py` arma el correo en HTML, para que el diseño sea siempre igual.
- `enviar_resend.py` envía el correo. Solo reintenta si Resend dice que hay demasiadas solicitudes, para no mandar correos duplicados.

**Memoria.** El agente guarda un `historial.csv` con una fila por día e indicador (fecha, indicador, valor y fuente) de los últimos 90 días. Solo `tendencia.py` puede escribir ahí. Guardo solo números, fechas y fuentes para que ninguna página web pueda colar instrucciones en la memoria. El historial arrancó con 30 días de TRM descargados de datos.gov.co.

**Tendencia.** Para cada indicador calcula la variación de 5 días hábiles, el mínimo, el máximo y la racha. Si hay menos de 5 días de datos, dice "historial insuficiente" en vez de inventar. Si la TRM cambia más de 1 % en un día, lo avisa al principio del correo.

**El correo.** Es un boletín en HTML con secciones: En una mirada, Tendencia de la semana, Divisas, Logística/Vías, Indicadores macro, Otros eventos y "Por confirmar hoy". No uso gráficas porque Gmail bloquea muchas imágenes. Si un dato no se encontró, va en "Por confirmar hoy".

**Qué tan confiable es cada cifra.** Cada número lleva una etiqueta: "Fuente oficial", "Vía prensa" o "Sin verificar". En una prueba vi que el agente marcaba la tasa y el IPC como oficiales sin haber abierto ninguna página, así que lo controlé con código: el correo solo dice "Fuente oficial" si la página aparece como abierta en el registro. Un límite que encontré: banrep.gov.co bloquea robots, así que sus cifras suelen salir como "Vía prensa".

**La clave de Resend.** Está guardada en un vault de Anthropic y el agente nunca ve el valor real, solo un marcador. Tiene el permiso mínimo: solo enviar correos.

**Límites de seguridad.** El agente solo puede buscar, redactar, enviar un correo por corrida a un destinatario fijo y actualizar su memoria. Además, el remitente de prueba de Resend solo entrega correos al dueño de la cuenta.

**Lo que dejé por fuera.** No uso Gmail (su conector no puede enviar correos), ni subagentes, ni gráficas. Tampoco Reuters, porque su sitio no deja entrar al buscador.

## Archivos de esta carpeta

| Archivo | Qué es |
|---|---|
| `model.yaml` | Nombre, descripción y modelo |
| `system_prompt.md` | Las instrucciones del agente |
| `tools.yaml` | Herramientas y sitios permitidos |
| `skills.yaml` | Conecta la skill con los scripts |
| `environment.yaml` | El contenedor en la nube y su acceso a internet |
| `vault.yaml` + `credentials.md` | El vault (sin secretos) y cómo cargar la clave |
| `memory_store-indicadores.yaml` | La memoria entre corridas |
| `memory/historial.csv` | Los datos iniciales del historial |
| `schedule.yaml` + `kickoff.md` | Cuándo corre y con qué mensaje |
| `tests/basico.json` | Prueba sin enviar correo |
| `tests/correo.json` | Prueba con envío real (cuesta una corrida) |
| `agent.md`, `deployment-diario.yaml` | Se generan solos con `scripts/ensamblar.py`. No los edites a mano |

## Encender, pausar o correr el agente

Ver si está activo o pausado:

```sh
ant beta:deployments retrieve --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3 --transform '{status:status,version:agent.version}'
```

Pausarlo o activarlo:

```sh
ant beta:deployments pause --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3
ant beta:deployments unpause --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3
```

Correrlo ahora mismo, sin esperar al horario (envía un correo real):

```sh
ant beta:deployments run --deployment-id depl_01A2ZcVTJY7Cbeb1dCRReHJ3
```

## Hacer cambios

```sh
uv run --script scripts/ensamblar.py agents/analista-colombia
A=agents/analista-colombia
F=(skills/reporte-correo-html $A/agent.md $A/environment.yaml $A/vault.yaml $A/memory_store-indicadores.yaml $A/deployment-diario.yaml)
ant apply --dry-run -v "${F[@]}"
ant apply --yes "${F[@]}"     # solo después de revisar el plan
```

## Probar

```sh
python -m unittest tests.unit.test_tendencia tests.unit.test_render tests.unit.test_abrir_fuente   # sin internet, 1 segundo
uv run --script scripts/probar.py agents/analista-colombia/tests/basico.json
python scripts/verificar_prueba.py tests/out/analista-colombia/<sesion>
```

## IDs en la nube

| Recurso | ID |
|---|---|
| Agente | `agent_018v718v6WfZ2SbkA1puZjQd` (v8) |
| Skill | `skill_01UbFiNtmj2aDaxmJNz12GvR` |
| Environment | `env_01Ey6tqA2ygpwuLgGL6JkmKZ` |
| Vault | `vlt_011CgMLdGnA7v6zWFqrpEL3C` |
| Memoria | `memstore_0118tjf9YxcNhP28Joqq9AxP` |
| Deployment | `depl_01A2ZcVTJY7Cbeb1dCRReHJ3` |

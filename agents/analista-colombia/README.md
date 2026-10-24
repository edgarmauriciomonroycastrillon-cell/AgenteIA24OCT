# analista-colombia

Analista económico diario para Colombia: cada día hábil busca en fuentes oficiales y de prensa los indicadores de divisas, logística/vías y macroeconomía, redacta un reporte en español con fuente y fecha de cada cifra, y lo envía por correo.

- **Costo medido por corrida:** pendiente (se mide en la primera prueba). Estimado: USD 0,5–1,5.

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
              por qué: la verificación vive en el prompt; la rúbrica se escribe después de ver
              2-3 reportes reales.
Tope de costo USD 3 por corrida (amount "300")                        schedule.yaml
              por qué: estimado 0,5–1,5; se ajusta tras la prueba. Se compone de tokens +
              USD 10 por 1.000 búsquedas + USD 0,08 por hora en running.
System prompt system_prompt.md
Tools         habilitadas: bash, read, write, web_search, web_fetch · política auto   tools.yaml
              apagadas: edit, glob, grep (el trabajo no edita código ni busca archivos)
              web_*: allowed_domains = banrep.gov.co, dane.gov.co, superfinanciera.gov.co,
              datos.gov.co, invias.gov.co, mintransporte.gov.co, ani.gov.co, larepublica.co,
              portafolio.co, eltiempo.com, valoraanalitik.com, bloomberg.com,
              colfecar.org.co · user_location CO / America/Bogota
MCP           no usa (Gmail MCP no puede enviar; se usa la API HTTP de Resend)
Skills        no usa (el reporte es Markdown/HTML simple)
Herramientas  no usa
  propias
Subagentes    ninguno (un solo bucle; no hay lectura paralela medida)
Environment   cloud · red limited                                     environment.yaml
              hosts: los dominios de arriba (apex y *.) + api.resend.com
              MCP no · gestores de paquetes no
Memoria       colombia-indicadores en /mnt/memory/colombia-indicadores/ · read_write
              guarda baseline.json (valor, fecha, fuente) para decir "sube/baja vs. ayer".
Archivos      no usa
Credenciales  vault analista-colombia: Resend (environment_variable RESEND_API_KEY, solo
              cabecera, solo api.resend.com), permiso mínimo "Sending access"   credentials.md
              el agente nunca ve el valor (ve un marcador)
Compuerta     hace solo: buscar, redactar, enviar el correo, actualizar la memoria.
              compuerta real: destinatario fijo en el kickoff y remitente de prueba de Resend,
              que solo entrega al correo dueño de la cuenta; no hay herramienta de borrado.
Fuera         sin Gmail MCP (no envía), sin outcome (aún), sin subagentes, sin MCP, sin reuters.com
              (la API lo rechazó: el crawler de Anthropic no puede acceder), sin user_location
              (el buscador no admite country CO).
```

## Archivos

| Archivo | Qué es |
|---|---|
| `model.yaml` | Nombre, descripción, modelo y effort |
| `system_prompt.md` | El system prompt, en Simplified Technical English |
| `tools.yaml` | Tools del sandbox, dominios web y permisos |
| `environment.yaml` | El contenedor: red y hosts permitidos |
| `vault.yaml` + `credentials.md` | El vault (nunca un secreto) y cómo cargar la clave de Resend |
| `memory_store-indicadores.yaml` | La memoria entre corridas |
| `schedule.yaml` + `kickoff.md` | El Deployment: cuándo y con qué mensaje |
| `tests/` | Casos de prueba para `scripts/probar.py` |
| `agent.md`, `deployment-diario.yaml` | Generados por `scripts/ensamblar.py`. No los edites a mano |

## Cambiar algo

```sh
uv run --script scripts/ensamblar.py agents/analista-colombia
F=(agents/analista-colombia/agent.md agents/analista-colombia/environment.yaml agents/analista-colombia/vault.yaml agents/analista-colombia/memory_store-indicadores.yaml agents/analista-colombia/deployment-diario.yaml)
ant apply --dry-run -v "${F[@]}"
ant apply --yes "${F[@]}"     # solo después de leer el plan
```

## Probar y depurar

```sh
uv run --script scripts/probar.py agents/analista-colombia/tests/basico.json
uv run --script scripts/inspeccionar.py <session_id>
```

## IDs

| Recurso | ID |
|---|---|
| agent.md | `agent_018v718v6WfZ2SbkA1puZjQd` (v1) |
| environment.yaml | `env_01Ey6tqA2ygpwuLgGL6JkmKZ` |
| vault.yaml | `vlt_011CgMLdGnA7v6zWFqrpEL3C` |
| memory_store-indicadores.yaml | `memstore_0118tjf9YxcNhP28Joqq9AxP` |
| deployment-diario.yaml | `depl_01A2ZcVTJY7Cbeb1dCRReHJ3` (en pausa) |

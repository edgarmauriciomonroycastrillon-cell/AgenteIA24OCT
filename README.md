# AgenteIA24OCT

Agente de Claude Managed Agents: analista económico diario para Colombia. Lee la TRM oficial,
busca divisas, vías y macroeconomía en fuentes confiables, calcula la tendencia de la semana y
envía por correo un boletín en HTML. Cada cifra dice de dónde viene y qué tan verificada está.

- **Estado:** funciona. Probado de punta a punta en la nube. Construido con la skill `managed-agents-wizard`.
- **Disparador:** Deployment, lunes a viernes 6:30 (America/Bogota). Está **activo** desde el
  2026-10-26 (lo encendió el usuario para probar). Para controlar costos se pausa cuando no se
  necesite; los comandos están en
  [agents/analista-colombia/README.md](agents/analista-colombia/README.md#estado-del-deployment).
- **Costo medido por corrida:** USD 0,41 a 0,72 (8 pruebas el 2026-10-24 y 26; la última, USD 0,72, con apertura de páginas oficiales). El tope por corrida es USD 3.
- **Modelo:** `claude-sonnet-5-5` (ver `agents/analista-colombia/model.yaml`).

## Cómo está organizado

| Carpeta | Qué hay |
|---|---|
| `agents/analista-colombia/` | El agente: prompt, tools, red, memoria, horario. Su README tiene la ficha completa con el porqué de cada capa |
| `skills/reporte-correo-html/` | La skill del agente: historial y tendencias (`tendencia.py`), páginas oficiales (`abrir_fuente.py`), correo HTML (`render_email.py`) y envío (`enviar_resend.py`) |
| `scripts/` | Herramientas para construir, probar y depurar (`ensamblar.py`, `probar.py`, `verificar_prueba.py`, ...) |
| `tests/unit/` | Pruebas unitarias sin internet |
| `claude-lock.json` | Los IDs de lo que existe en la nube (no contiene secretos) |

## Cómo funciona un día

1. El Deployment arranca una Session a las 6:30.
2. El agente pide la TRM oficial a datos.gov.co y la guarda en su memoria (`historial.csv`).
3. Busca el resto de indicadores y guarda sus valores, siempre a través de `tendencia.py`, que
   valida cada fila.
4. `tendencia.py calcular` hace las cuentas (variación de 5 días hábiles, mínimo, máximo, racha y
   alerta si la TRM cambia más de 1 % en un día). El modelo solo copia las frases.
5. `render_email.py` arma el HTML y `enviar_resend.py` lo envía.

## Probar

```sh
python -m unittest tests.unit.test_tendencia tests.unit.test_render tests.unit.test_abrir_fuente
uv run --script scripts/probar.py agents/analista-colombia/tests/basico.json   # dry run, no envía correo
python scripts/verificar_prueba.py tests/out/analista-colombia/<sesion>
```

## Secretos

Los secretos **no** están en este repo. La clave de Resend vive en el vault de Anthropic y se
carga con `scripts/cargar-resend.ps1`, que la lee oculta en tu terminal. El agente nunca ve el
valor real. `.env` está en `.gitignore`; `.env.example` es solo una plantilla vacía.

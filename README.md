# AgenteIA24OCT

Agente de Claude Managed Agents: analista económico diario para Colombia
(divisas, logística/vías, indicadores macro). Busca en fuentes confiables y
envía el reporte por correo.

- Disparador: Deployment, lunes a viernes 6:30 (America/Colombia) , deployment está en pausa para controlar costos
- Modelo: ver `agents/<nombre>/model.yaml`
- Los secretos NO están en este repo: van en variables de entorno / vault.
  Ver `.env.example`.

Construido con la skill `managed-agents-wizard`.

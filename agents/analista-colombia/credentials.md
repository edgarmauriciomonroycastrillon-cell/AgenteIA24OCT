# Credenciales

| Servicio | Tipo | Para qué |
|---|---|---|
| Resend (`api.resend.com`) | `environment_variable` `RESEND_API_KEY`, solo cabecera, solo host `api.resend.com` | enviar el reporte por correo |

Permisos mínimos: clave de Resend con permiso "Sending access" (solo enviar), no "Full access".
Crea la cuenta de Resend con el mismo correo que recibirá el reporte: el remitente de prueba
`onboarding@resend.dev` solo entrega a ese correo.

Carga (el secreto lo pegas tú; nunca pasa por el chat ni por un archivo del repo):

```sh
read -rs CMA_KEY && export CMA_KEY
jq -n -f /dev/stdin <<'JQ' | ant beta:vaults:credentials create --vault-id <vlt_...>
{display_name: "Resend", auth: {type: "environment_variable", secret_name: "RESEND_API_KEY", secret_value: (env.CMA_KEY // error("CMA_KEY is not set")),
  networking: {type: "limited", allowed_hosts: ["api.resend.com"]}, injection_location: {header: true}}}
JQ
unset CMA_KEY
```

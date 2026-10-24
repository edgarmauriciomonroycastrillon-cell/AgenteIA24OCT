# Carga la clave de Resend al vault del agente. La clave se escribe en este terminal (oculta),
# viaja a la API de Anthropic por stdin y nunca se guarda en un archivo ni pasa por el chat.
# Uso (desde la raiz del proyecto): powershell -ExecutionPolicy Bypass -File scripts/cargar-resend.ps1

$ErrorActionPreference = "Stop"
$ant = Join-Path $env:LOCALAPPDATA "Programs\ant\ant.exe"
$lock = Get-Content "claude-lock.json" -Raw | ConvertFrom-Json
$vaultId = $lock.resources.'./agents/analista-colombia/vault.yaml'.id
if (-not $vaultId) { throw "No encuentro el vault en claude-lock.json" }

$secure = Read-Host "Pega tu clave de Resend (empieza con re_) y presiona Enter" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    if (-not $key.StartsWith("re_")) { throw "La clave no empieza con re_. Esa no parece una clave de Resend; no la cargo." }

    $body = @{
        display_name = "Resend"
        auth = @{
            type = "environment_variable"
            secret_name = "RESEND_API_KEY"
            secret_value = $key
            networking = @{ type = "limited"; allowed_hosts = @("api.resend.com") }
            injection_location = @{ header = $true }
        }
    } | ConvertTo-Json -Depth 6 -Compress

    $body | & $ant beta:vaults:credentials create --vault-id $vaultId --transform "{id:id,display_name:display_name,secret_name:auth.secret_name}"
    if ($LASTEXITCODE -ne 0) { throw "ant devolvio error al crear la credencial" }
    Write-Host "Listo: credencial cargada en el vault $vaultId" -ForegroundColor Green
}
finally {
    $key = $null; $body = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

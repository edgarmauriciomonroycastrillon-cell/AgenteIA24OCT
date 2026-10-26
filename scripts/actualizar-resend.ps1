# Cambia la clave de Resend que ya está en el vault (actualiza la credencial existente).
# La clave se escribe oculta en este terminal y viaja a la API por stdin: no queda en ningún
# archivo, ni en el historial, ni pasa por el chat. NO la pegues dentro de este script.
# Uso (desde la raiz del proyecto): powershell -ExecutionPolicy Bypass -File scripts/actualizar-resend.ps1

$ErrorActionPreference = "Stop"
$ant = Join-Path $env:LOCALAPPDATA "Programs\ant\ant.exe"
$lock = Get-Content "claude-lock.json" -Raw | ConvertFrom-Json
$vaultId = $lock.resources.'./agents/analista-colombia/vault.yaml'.id
if (-not $vaultId) { throw "No encuentro el vault en claude-lock.json" }

# busca la credencial de Resend que ya existe (sin mostrar secretos)
$lista = & $ant beta:vaults:credentials list --vault-id $vaultId --transform "{id:id,secreto:auth.secret_name}" --format jsonl | ConvertFrom-Json
$cred = @($lista) | Where-Object { $_.secreto -eq "RESEND_API_KEY" } | Select-Object -First 1
if (-not $cred) { throw "No hay una credencial RESEND_API_KEY en el vault. Usa scripts/cargar-resend.ps1" }
Write-Host "Voy a cambiar la clave de la credencial $($cred.id) del vault $vaultId"

$secure = Read-Host "Pega la clave NUEVA de Resend (empieza con re_) y presiona Enter" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    if (-not $key.StartsWith("re_")) { throw "La clave no empieza con re_. No parece una clave de Resend; no la cargo." }
    if ($key.Length -lt 20) { throw "La clave es demasiado corta; no la cargo." }

    $body = @{ auth = @{ type = "environment_variable"; secret_value = $key } } | ConvertTo-Json -Depth 4 -Compress
    $body | & $ant beta:vaults:credentials update --vault-id $vaultId --credential-id $cred.id --transform "{id:id,secreto:auth.secret_name,actualizada:updated_at}"
    if ($LASTEXITCODE -ne 0) { throw "ant devolvio error al actualizar la credencial" }
    Write-Host "Listo: la clave de Resend quedo actualizada en el vault." -ForegroundColor Green
}
finally {
    $key = $null; $body = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

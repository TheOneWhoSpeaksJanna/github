# Dashboard, local Ollama and encrypted backups must stay in ONE Actions step.
# GitHub's Windows runner can stop detached processes when a step completes.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if (-not $env:TAILSCALE_IP -or $env:TAILSCALE_IP -notmatch '^100\.') { throw "Tailscale address missing" }
if (-not $env:HERMES_DASHBOARD_PASSWORD -or $env:HERMES_DASHBOARD_PASSWORD.Length -lt 14) { throw "HERMES_DASHBOARD_PASSWORD must be 14+ characters" }

$env:HERMES_HOME = Join-Path $env:RUNNER_TEMP "hermes"
$env:OLLAMA_MODELS = Join-Path $env:RUNNER_TEMP "ollama-models"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_CONTEXT_LENGTH = "65536"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:OLLAMA_KEEP_ALIVE = "30m"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:HIP_VISIBLE_DEVICES = "-1"
$env:NO_PROXY = "127.0.0.1,localhost"
$workdir = Join-Path $env:RUNNER_TEMP "HermesWorkspace"
New-Item -ItemType Directory -Path $workdir -Force | Out-Null
$ollama = Join-Path $env:RUNNER_TEMP "ollama-bin\ollama.exe"
$hermes = Join-Path $env:HERMES_HOME "bin\hermes.exe"
if (-not (Test-Path $ollama) -or -not (Test-Path $hermes)) { throw "Prepared Hermes or Ollama binary missing" }

$adapter = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $env:TAILSCALE_IP } | Select-Object -First 1
if (-not $adapter) { throw "Tailscale adapter missing" }
New-NetFirewallRule -DisplayName "Hermes dashboard via private Tailscale" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9119 -InterfaceAlias $adapter.InterfaceAlias -RemoteAddress "100.64.0.0/10" | Out-Null

# Start only local backend. No public Ollama API; only the authenticated
# Hermes dashboard binds its Tailscale IP.
$olog = Join-Path $env:RUNNER_TEMP "ollama-fast.stdout.log"
$oerr = Join-Path $env:RUNNER_TEMP "ollama-fast.stderr.log"
$ollamaProc = Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru -RedirectStandardOutput $olog -RedirectStandardError $oerr
$ready = $false
for ($i=0; $i -lt 70; $i++) {
  try {
    $models = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    if (@($models.models | Where-Object { $_.name -like "qwen3.5:2b*" }).Count -eq 0) {
      throw "Prepared standard model missing"
    }
    $ready = $true
    break
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) {
  if (Test-Path $oerr) { Get-Content $oerr -Tail 25 }
  throw "Cached Ollama backend or model unavailable"
}
Write-Host "Cached Ollama and model ready. No download or installation."

# Restored private Hermes config (if any) is overridden only for the local
# model and safer execution defaults. Keep memory, history, skills and sessions.
$config = @(
  @("model.default","qwen3.5:2b"),
  @("model.provider","custom"),
  @("model.base_url","http://127.0.0.1:11434/v1"),
  @("model.context_length","65536"),
  @("approvals.mode","manual"),
  @("approvals.unattended_mode","deny"),
  @("approvals.single_query_mode","deny"),
  @("terminal.cwd",$workdir)
)
foreach ($entry in $config) {
  & $hermes config set $entry[0] $entry[1]
  if ($LASTEXITCODE -ne 0) { throw "Hermes configuration failed at $($entry[0])" }
}
$env:HERMES_DASHBOARD_BASIC_AUTH_USERNAME = "owner"
$env:HERMES_DASHBOARD_BASIC_AUTH_PASSWORD = $env:HERMES_DASHBOARD_PASSWORD
$secretBytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($secretBytes)
$rng.Dispose()
$env:HERMES_DASHBOARD_BASIC_AUTH_SECRET = [Convert]::ToBase64String($secretBytes)

$log = Join-Path $env:RUNNER_TEMP "hermes-fast.stdout.log"
$err = Join-Path $env:RUNNER_TEMP "hermes-fast.stderr.log"
Write-Host "Launching password-protected Hermes dashboard on Tailscale port 9119..."
$dashboard = Start-Process -FilePath $hermes -ArgumentList "dashboard --no-open --host $($env:TAILSCALE_IP) --port 9119" -WorkingDirectory $workdir -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
$up = $false
for ($i=0; $i -lt 75; $i++) {
  try {
    $status = Invoke-RestMethod "http://$($env:TAILSCALE_IP):9119/api/status" -TimeoutSec 3
    if ($status.auth_required -eq $false) { throw "Dashboard authentication disabled" }
    if ($status.auth_required -eq $true -and $status.auth_providers -contains "basic") { $up = $true; break }
    if ($status.auth_required -eq $true) { throw "Dashboard missing password login" }
  } catch {
    if ($_.Exception.Message -match "authentication disabled|missing password login") { throw }
    Start-Sleep -Seconds 2
  }
}
if (-not $up) {
  if (Test-Path $err) { Get-Content $err -Tail 25 }
  throw "Authenticated Hermes dashboard failed to start"
}
Write-Host "HERMES DASHBOARD STARTED - Tailscale port 9119, owner password required"
"## Hermes Agent" | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Private dashboard: find hermes-$env:GITHUB_RUN_ID in Tailscale, use port 9119 and username owner. Never expose this service publicly." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY

$backup = Join-Path $env:RUNNER_TEMP "hermes-state.enc"
$backupScript = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes_persist.py"
function Save-EncryptedState {
  & python $backupScript save --home $env:HERMES_HOME --workspace $workdir --file $backup
  if ($LASTEXITCODE -ne 0) { throw "Encrypted state checkpoint failed" }
}
# Even a short smoke test should upload a valid encrypted snapshot.
Save-EncryptedState
$sessionMinutes = 300
if ($env:HERMES_SESSION_MINUTES) { $sessionMinutes = [int]$env:HERMES_SESSION_MINUTES }
if ($sessionMinutes -lt 1 -or $sessionMinutes -gt 310) { throw "Invalid session minutes" }
$deadline = (Get-Date).AddMinutes($sessionMinutes)
$nextSave = (Get-Date).AddMinutes(15)
$unhealthy = 0
try {
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 20
    $healthy = $false
    try {
      $check = Invoke-RestMethod "http://$($env:TAILSCALE_IP):9119/api/status" -TimeoutSec 5
      $null = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
      $healthy = ($check.auth_required -eq $true -and $check.auth_providers -contains "basic")
    } catch { $healthy = $false }
    if ($healthy) { $unhealthy = 0 }
    else {
      $unhealthy++
      Write-Warning "Hermes HTTP health check failed ($unhealthy consecutive)."
      if ($unhealthy -ge 5) {
        if (Test-Path $err) { Get-Content $err -Tail 20 }
        throw "Hermes dashboard stopped responding"
      }
    }
    if ((Get-Date) -ge $nextSave) {
      Save-EncryptedState
      $nextSave = (Get-Date).AddMinutes(15)
      Write-Host "Encrypted local checkpoint refreshed."
    }
  }
  Write-Host "Hermes session completed as scheduled."
} finally {
  try { Save-EncryptedState } catch { Write-Warning "Final encrypted save failed." }
  if (-not $dashboard.HasExited) { Stop-Process -Id $dashboard.Id -Force -ErrorAction SilentlyContinue }
  if (-not $ollamaProc.HasExited) { Stop-Process -Id $ollamaProc.Id -Force -ErrorAction SilentlyContinue }
  Write-Host "Encrypted snapshot can now be uploaded from this job."
}

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if (-not $env:TAILSCALE_IP -or $env:TAILSCALE_IP -notmatch '^100\.') { throw "Missing Tailscale address" }
if (-not $env:HERMES_DASHBOARD_PASSWORD -or $env:HERMES_DASHBOARD_PASSWORD.Length -lt 14) { throw "Create HERMES_DASHBOARD_PASSWORD GitHub secret (14+ characters)" }
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_CONTEXT_LENGTH = "65536"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:OLLAMA_KEEP_ALIVE = "30m"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:HIP_VISIBLE_DEVICES = "-1"
$env:NO_PROXY = "127.0.0.1,localhost"
$env:HERMES_HOME = Join-Path $env:LOCALAPPDATA "hermes"
$workdir = Join-Path $env:RUNNER_TEMP "HermesWorkspace"
New-Item -ItemType Directory -Path $workdir,$env:HERMES_HOME -Force | Out-Null

$adapter = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $env:TAILSCALE_IP } | Select-Object -First 1
if (-not $adapter) { throw "Tailscale adapter missing" }
New-NetFirewallRule -DisplayName "Hermes Dashboard via Tailscale" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9119 -InterfaceAlias $adapter.InterfaceAlias -RemoteAddress "100.64.0.0/10" | Out-Null

Write-Host "Runner logical processors: $([Environment]::ProcessorCount)"
Write-Host "Installing Ollama for Hermes..."
irm https://ollama.com/install.ps1 | iex
$paths = @("$env:LOCALAPPDATA\Programs\Ollama\ollama.exe","$env:ProgramFiles\Ollama\ollama.exe")
$ollama = $paths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ollama) { throw "Ollama executable missing" }
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$ollamaProc = Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru
$ready = $false
for ($i=0; $i -lt 70; $i++) {
  try {
    Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
    $ready = $true
    break
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { throw "Ollama backend did not become ready" }

# Separate standard tool-capable model, not the user's existing chat configuration.
$model = "qwen3.5:2b"
Write-Host "Downloading standard tool-capable model..."
& $ollama pull $model
if ($LASTEXITCODE -ne 0) { throw "Model download failed" }

Write-Host "Installing official Hermes Agent..."
$installer = Invoke-RestMethod "https://hermes-agent.nousresearch.com/install.ps1"
& ([scriptblock]::Create($installer)) -NonInteractive -HermesHome $env:HERMES_HOME
if (-not $?) { throw "Hermes installer failed" }
$hermes = Join-Path $env:HERMES_HOME "bin\hermes.exe"
if (-not (Test-Path $hermes)) { throw "Hermes executable missing" }
& $hermes --version
if ($LASTEXITCODE -ne 0) { throw "Hermes CLI failed" }

# Config is local to the VM; no credentials in the public repository.
$config = @(
  @("model.default", $model),
  @("model.provider", "custom"),
  @("model.base_url", "http://127.0.0.1:11434/v1"),
  @("model.context_length", "65536"),
  @("approvals.mode", "manual"),
  @("approvals.unattended_mode", "deny"),
  @("approvals.single_query_mode", "deny"),
  @("terminal.cwd", $workdir)
)
foreach ($entry in $config) {
  & $hermes config set $entry[0] $entry[1]
  if ($LASTEXITCODE -ne 0) { throw "Hermes config set failed at $($entry[0])" }
}

# Remote dashboard never runs without login.
$env:HERMES_DASHBOARD_BASIC_AUTH_USERNAME = "owner"
$env:HERMES_DASHBOARD_BASIC_AUTH_PASSWORD = $env:HERMES_DASHBOARD_PASSWORD
$bytes = New-Object byte[] 48
$rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
$rng.GetBytes($bytes)
$rng.Dispose()
$env:HERMES_DASHBOARD_BASIC_AUTH_SECRET = [Convert]::ToBase64String($bytes)
$log = Join-Path $env:RUNNER_TEMP "hermes-dashboard-stdout.log"
$err = Join-Path $env:RUNNER_TEMP "hermes-dashboard-stderr.log"
$arguments = "dashboard --no-open --host $($env:TAILSCALE_IP) --port 9119"
Write-Host "Starting authenticated Hermes dashboard on private Tailscale network..."
$dashboard = Start-Process -FilePath $hermes -ArgumentList $arguments -WorkingDirectory $workdir -PassThru -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err
$up = $false
for ($i=0; $i -lt 100; $i++) {
  if ($dashboard.HasExited) { break }
  try {
    $check = Invoke-RestMethod -Uri "http://$($env:TAILSCALE_IP):9119/api/status" -TimeoutSec 3
    if ($check.auth_required -eq $true -and $check.auth_providers -contains "basic") { $up = $true; break }
    if ($check.auth_required -eq $true -and $check.auth_providers -notcontains "basic") { throw "Dashboard login provider missing - refusing to continue" }
    if ($check.auth_required -eq $false) { throw "Dashboard has no authentication; refusing to continue" }
  } catch {
    if ($_.Exception.Message -match "has no authentication|login provider missing") { throw }
    Start-Sleep -Seconds 2
  }
}
if (-not $up) {
  if (Test-Path $err) { Get-Content $err -Tail 35 }
  throw "Hermes dashboard did not start with verified authentication"
}
Write-Host "HERMES DASHBOARD STARTED - Tailscale port 9119, login required"
Write-Host "Open in an Android browser on your authorized Tailnet device."
Write-Host "Login username: owner. Password: the private repository Actions secret."
"## Hermes Agent" | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Authenticated Hermes dashboard running. Find hermes-$env:GITHUB_RUN_ID in Tailscale; use port 9119 and username owner." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"HERMES_DASHBOARD_PID=$($dashboard.Id)" >> $env:GITHUB_ENV
Write-Host "Hermes dashboard ready; it stays running during the workflow's backup checkpoints."

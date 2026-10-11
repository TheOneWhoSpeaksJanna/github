# Dashboard, local Ollama and encrypted backups must stay in ONE Actions step.
# GitHub's Windows runner can stop detached processes when a step completes.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if (-not $env:TAILSCALE_IP -or $env:TAILSCALE_IP -notmatch '^100\.') { throw "Tailscale address missing" }
if (-not $env:HERMES_DASHBOARD_PASSWORD -or $env:HERMES_DASHBOARD_PASSWORD.Length -lt 14) { throw "HERMES_DASHBOARD_PASSWORD must be 14+ characters" }
# The GitHub token is needed only for encrypted checkpoint uploads and to
# observe Stop requests. Do not inherit it into the Hermes agent child process.
if (-not $env:GH_TOKEN) { throw "Github token is needed for safe checkpoints" }
$checkpointGithubToken = $env:GH_TOKEN
Remove-Item Env:GH_TOKEN


$env:HERMES_HOME = Join-Path $env:RUNNER_TEMP "hermes"
$env:OLLAMA_MODELS = Join-Path $env:RUNNER_TEMP "ollama-models"
$env:OLLAMA_HOST = "127.0.0.1:11434"
# Hermes requires 64,000+ tokens for tool use. Ollama must actually serve
# at least that many; smaller contexts cause the 8,192-token startup refusal.
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
$modelHelper = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-model-config.py"
$modelConfig = Join-Path $env:GITHUB_WORKSPACE "hermes-models.txt"
$activeModel = & python $modelHelper default $modelConfig
if ($LASTEXITCODE -ne 0 -or -not $activeModel) { throw "No default Hermes model set in hermes-models.txt" }
$activeTag = if ($activeModel.Contains(":")) { $activeModel } else { "${activeModel}:latest" }
Write-Host "Selected agent model from hermes-models.txt: $activeModel"
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
    if (@($models.models | Where-Object { $_.name -eq $activeTag }).Count -eq 0) {
      throw "Selected Ollama model is not installed: $activeModel"
    }
    $ready = $true
    break
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) {
  if (Test-Path $oerr) { Get-Content $oerr -Tail 25 }
  throw "Cached Ollama backend or model unavailable"
}
Write-Host "Selected Ollama agent model is ready. No download needed in the serving step."
Write-Host "Ollama will serve 65536 context tokens; Hermes model.ollama_num_ctx=65536."

# Restored private Hermes config (if any) is overridden only for the local
# model and safer execution defaults. Keep memory, history, skills and sessions.
$config = @(
  @("model.default",$activeModel),
  @("model.provider","custom"),
  @("model.base_url","http://127.0.0.1:11434/v1"),
  @("model.context_length","65536"),
  @("model.ollama_num_ctx","65536"),
  @("approvals.mode","manual"),
  @("approvals.unattended_mode","deny"),
  @("approvals.single_query_mode","deny"),
  @("terminal.cwd",$workdir)
)
foreach ($entry in $config) {
  & $hermes config set $entry[0] $entry[1]
  if ($LASTEXITCODE -ne 0) { throw "Hermes configuration failed at $($entry[0])" }
}
# Tool schemas dominate prompt prefilling on 4-vCPU runners. Restore memory,
# but prefer a small explicit tool list unless the user opts into full mode.
$agentMode = "light"
if ($env:HERMES_AGENT_MODE) { $agentMode = $env:HERMES_AGENT_MODE.Trim().ToLowerInvariant() }
& (Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-mode-config.ps1") -HermesExe $hermes -Mode $agentMode
if (-not $?) { throw "Hermes agent tool mode could not be applied" }

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
Write-Host "HERMES DASHBOARD STARTED - model $activeModel, Tailscale port 9119, owner password required"
"## Hermes Agent" | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Private dashboard: find hermes-$env:GITHUB_RUN_ID in Tailscale, use port 9119 and username owner. Never expose this service publicly." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Encrypted state: remotely checkpointed at startup, every 10 minutes, and after a graceful Stop." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Tool mode: $agentMode (chat=zero tools; light=file only; full=all default tools)." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"To stop safely: Actions > Hermes Agent > Run workflow > operation = stop. Do NOT press Cancel on this running job." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
$healthPath = Join-Path $env:RUNNER_TEMP "hermes-health.jsonl"
$healthScript = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-health.ps1"
try {
  & $healthScript -Destination $healthPath
} catch {
  Write-Warning "Initial private VM metrics were unavailable."
}


# An encrypted snapshot saved only on the VM is NOT durable. Upload one at
# startup, every 10 minutes, and at shutdown to a rolling GitHub prerelease.
# Every upload uses a new immutable encrypted filename; only encrypted bytes
# are retained, and old rolling checkpoints are pruned.
$backup = Join-Path $env:RUNNER_TEMP "hermes-state.enc"
$backupScript = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes_persist.py"
$checkpointScript = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-checkpoint.ps1"
function Save-EncryptedState {
  & python $backupScript save --home $env:HERMES_HOME --workspace $workdir --file $backup
  if ($LASTEXITCODE -ne 0) { throw "Encrypted state checkpoint failed" }
}
function Upload-EncryptedState {
  Save-EncryptedState
  $env:GH_TOKEN = $checkpointGithubToken
  try {
    & $checkpointScript -EncryptedFile $backup -Repository $env:GITHUB_REPOSITORY -RunId $env:GITHUB_RUN_ID
    if (-not $?) { throw "Could not upload encrypted backup to GitHub" }
  } finally {
    Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
  }
}
function Stop-Requested {
  # A separate manual workflow_dispatch run named "Hermes stop" serves as
  # a durable signal. A Stop run is NOT in the long-running job concurrency
  # group and thus never abruptly cancels the server.
  $env:GH_TOKEN = $checkpointGithubToken
  try {
    $json = & gh api "repos/$env:GITHUB_REPOSITORY/actions/workflows/hermes-agent.yml/runs?event=workflow_dispatch&per_page=60"
    if ($LASTEXITCODE -ne 0) { throw "Could not poll workflow control requests" }
    $data = ($json -join "`n") | ConvertFrom-Json
    $match = @($data.workflow_runs | Where-Object {
      [long]$_.id -gt [long]$env:GITHUB_RUN_ID -and
      $_.display_title -eq "Hermes stop" -and
      $_.head_branch -eq "main"
    })
    return ($match.Count -gt 0)
  } finally {
    Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
  }
}
Write-Host "Creating the first encrypted off-VM checkpoint."
Upload-EncryptedState
$sessionMinutes = 300
if ($env:HERMES_SESSION_MINUTES) { $sessionMinutes = [int]$env:HERMES_SESSION_MINUTES }
if ($sessionMinutes -lt 1 -or $sessionMinutes -gt 310) { throw "Invalid session minutes" }
$deadline = (Get-Date).AddMinutes($sessionMinutes)
$nextSave = (Get-Date).AddMinutes(10)
$nextControlPoll = (Get-Date).AddSeconds(30)
$nextHealth = (Get-Date).AddMinutes(2)
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
    if ((Get-Date) -ge $nextHealth) {
      try {
        & $healthScript -Destination $healthPath
      } catch {
        Write-Warning "Non-critical CPU/RAM telemetry unavailable."
      }
      $nextHealth = (Get-Date).AddMinutes(2)
    }
    if ((Get-Date) -ge $nextSave) {
      try {
        Upload-EncryptedState
        $nextSave = (Get-Date).AddMinutes(10)
        Write-Host "10-minute encrypted checkpoint saved remotely on GitHub."
      } catch {
        Write-Warning "Remote backup failed, retrying in 1 minute: $($_.Exception.Message)"
        $nextSave = (Get-Date).AddMinutes(1)
      }
    }
    if ((Get-Date) -ge $nextControlPoll) {
      try {
        if (Stop-Requested) {
          Write-Host "Graceful Stop requested from GitHub Actions. Finishing safely."
          break
        }
      } catch {
        Write-Warning "Could not check for Stop request: $($_.Exception.Message)"
      }
      $nextControlPoll = (Get-Date).AddSeconds(45)
    }
  }
  Write-Host "Hermes session finished normally."
} finally {
  try {
    Upload-EncryptedState
    Write-Host "Final encrypted state uploaded to the rolling GitHub backup release."
  } catch {
    Write-Warning "Final remote checkpoint failed; end-of-run Actions artifact upload will still be attempted."
    try { Save-EncryptedState } catch { Write-Warning "Final local checkpoint failed." }
  }
  try { & $healthScript -Destination $healthPath } catch { }
  if (-not $dashboard.HasExited) { Stop-Process -Id $dashboard.Id -Force -ErrorAction SilentlyContinue }
  if (-not $ollamaProc.HasExited) { Stop-Process -Id $ollamaProc.Id -Force -ErrorAction SilentlyContinue }
  Write-Host "Hermes stopped gracefully. Final encrypted artifact can now upload."
}

# Single Actions step holds Ollama, private File Agent and encrypted snapshots.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if (-not $env:TAILSCALE_IP -or $env:TAILSCALE_IP -notmatch '^100\.') { throw "Tailscale IP missing" }
if (-not $env:HERMES_DASHBOARD_PASSWORD -or $env:HERMES_DASHBOARD_PASSWORD.Length -lt 14) { throw "Configure dashboard password (14+ chars)" }
if (-not $env:GH_TOKEN) { throw "GitHub token needed for encrypted backup" }
$checkpointToken = $env:GH_TOKEN
Remove-Item Env:GH_TOKEN
$env:OLLAMA_MODELS = Join-Path $env:RUNNER_TEMP "ollama-models"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_CONTEXT_LENGTH = "4096"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:OLLAMA_KEEP_ALIVE = "30m"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:HIP_VISIBLE_DEVICES = "-1"
$env:NO_PROXY = "127.0.0.1,localhost"
$env:AGENT_PASSWORD = $env:HERMES_DASHBOARD_PASSWORD
$workspace = Join-Path $env:RUNNER_TEMP "FileAgentWorkspace"
$home = Join-Path $env:RUNNER_TEMP "FileAgentState"
New-Item -ItemType Directory -Force -Path $workspace,$home | Out-Null
$helper = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-model-config.py"
$model = & python $helper default (Join-Path $env:GITHUB_WORKSPACE "agent-models.txt")
if ($LASTEXITCODE -ne 0 -or -not $model) { throw "Invalid local task model" }
$exe = Join-Path $env:RUNNER_TEMP "ollama-bin\ollama.exe"
if (-not (Test-Path $exe)) { throw "Cached Ollama executable missing" }
$nic = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $env:TAILSCALE_IP } | Select-Object -First 1
if (-not $nic) { throw "Private Tailscale network interface missing" }
New-NetFirewallRule -DisplayName "File Agent private Tailscale" -Direction Inbound -Protocol TCP -Action Allow -LocalPort 9120 -InterfaceAlias $nic.InterfaceAlias -RemoteAddress "100.64.0.0/10" | Out-Null
$ollamaOut = Join-Path $env:RUNNER_TEMP "file-agent-ollama.stdout.log"
$ollamaErr = Join-Path $env:RUNNER_TEMP "file-agent-ollama.stderr.log"
$ollamaProc = Start-Process -FilePath $exe -ArgumentList "serve" -PassThru -WindowStyle Hidden -RedirectStandardOutput $ollamaOut -RedirectStandardError $ollamaErr
$ready = $false
for ($i=0; $i -lt 70; $i++) {
  if ($ollamaProc.HasExited) { break }
  try {
    $tags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    $name = if ($model.Contains(":")) { $model } else { "$($model):latest" }
    if (@($tags.models | Where-Object { $_.name -eq $name }).Count -eq 0) { throw "Model unavailable" }
    $ready = $true
    break
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { throw "Local model runtime failed" }
Write-Host "Private model engine ready ($model) using 4096 context, no Ollama chat port exposed."
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$out = Join-Path $env:RUNNER_TEMP "file-agent-web.stdout.log"
$err = Join-Path $env:RUNNER_TEMP "file-agent-web.stderr.log"
$args = @("agent/file_agent.py","--bind",$env:TAILSCALE_IP,"--port","9120","--workspace",$workspace,"--model",$model)
$agentProc = Start-Process -FilePath $pythonExe -ArgumentList $args -WorkingDirectory $env:GITHUB_WORKSPACE -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
$up = $false
for ($i=0; $i -lt 60; $i++) {
  if ($agentProc.HasExited) { break }
  try {
    $check = Invoke-RestMethod "http://$($env:TAILSCALE_IP):9120/health" -TimeoutSec 3
    if ($check.status -eq "ok") { $up = $true; break }
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $up) {
  if (Test-Path $err) { Get-Content $err -Tail 12 }
  throw "File agent website did not start"
}
try {
  $bad = Invoke-WebRequest "http://$($env:TAILSCALE_IP):9120/" -UseBasicParsing -TimeoutSec 5
  throw "Private file agent failed its password protection test"
} catch {
  if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) {
    Write-Host "Password challenge verified, unauthenticated page access rejected."
  } else { throw }
}
Write-Host "FILE AGENT STARTED - Tailscale port 9120, username owner, password required."
"## Pocket File Agent" | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Private address: find file-agent-$env:GITHUB_RUN_ID in Tailscale; port 9120, username owner." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Download finished files from the private mobile page. Use operation=stop to save and shut down safely." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
$backup = Join-Path $env:RUNNER_TEMP "file-agent-state.enc"
$encryptor = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes_persist.py"
$uploader = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-checkpoint.ps1"
$tag = "file-agent-encrypted-checkpoints"
function Save-EncryptedWorkspace {
  & python $encryptor save --home $home --workspace $workspace --file $backup
  if ($LASTEXITCODE -ne 0) { throw "Workspace encryption failed" }
}
function Upload-EncryptedWorkspace {
  Save-EncryptedWorkspace
  $env:GH_TOKEN = $checkpointToken
  try {
    & $uploader -EncryptedFile $backup -Repository $env:GITHUB_REPOSITORY -RunId $env:GITHUB_RUN_ID -Tag $tag
    if (-not $?) { throw "Remote encrypted workspace upload failed" }
  } finally { Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue }
}
function Stop-Requested {
  $env:GH_TOKEN = $checkpointToken
  try {
    $raw = & gh api "repos/$env:GITHUB_REPOSITORY/actions/workflows/file-agent.yml/runs?event=workflow_dispatch&per_page=60"
    if ($LASTEXITCODE -ne 0) { throw "Cannot check Stop command" }
    $data = ($raw | Out-String) | ConvertFrom-Json
    $found = @($data.workflow_runs | Where-Object {
      [long]$_.id -gt [long]$env:GITHUB_RUN_ID -and
      $_.display_title -eq "File agent stop" -and
      $_.head_branch -eq "main"
    })
    return ($found.Count -gt 0)
  } finally { Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue }
}
Upload-EncryptedWorkspace
$minutes = 300
if ($env:AGENT_SESSION_MINUTES) { $minutes = [int]$env:AGENT_SESSION_MINUTES }
if ($minutes -lt 1 -or $minutes -gt 310) { throw "Invalid session minutes" }
$deadline = (Get-Date).AddMinutes($minutes)
$nextBackup = (Get-Date).AddMinutes(10)
$nextPoll = (Get-Date).AddSeconds(30)
$unhealthy = 0
try {
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 15
    try {
      $check = Invoke-RestMethod "http://$($env:TAILSCALE_IP):9120/health" -TimeoutSec 5
      $null = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
      if ($check.status -eq "ok") { $unhealthy = 0 } else { $unhealthy++ }
    } catch { $unhealthy++ }
    if ($unhealthy -ge 6) { throw "Agent or local Ollama service became unresponsive" }
    if ((Get-Date) -ge $nextBackup) {
      try {
        Upload-EncryptedWorkspace
        Write-Host "10-minute encrypted workspace checkpoint uploaded."
        $nextBackup = (Get-Date).AddMinutes(10)
      } catch {
        Write-Warning "Checkpoint upload failed; retrying in one minute."
        $nextBackup = (Get-Date).AddMinutes(1)
      }
    }
    if ((Get-Date) -ge $nextPoll) {
      try { if (Stop-Requested) { Write-Host "Graceful Stop requested."; break } }
      catch { Write-Warning "Stop signal poll failed; continuing." }
      $nextPoll = (Get-Date).AddSeconds(40)
    }
  }
  Write-Host "File agent session finished normally."
} finally {
  try {
    Upload-EncryptedWorkspace
    Write-Host "Final encrypted workspace backup uploaded."
  } catch {
    Write-Warning "Remote final backup failed; encrypted end-of-run artifact will be attempted."
    try { Save-EncryptedWorkspace } catch { }
  }
  if (-not $agentProc.HasExited) { Stop-Process -Id $agentProc.Id -Force -ErrorAction SilentlyContinue }
  if (-not $ollamaProc.HasExited) { Stop-Process -Id $ollamaProc.Id -Force -ErrorAction SilentlyContinue }
  Write-Host "Agent processes stopped gracefully. Windows VM can terminate."
}

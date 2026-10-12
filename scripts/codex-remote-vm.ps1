# Keep Codex, Ollama and the private pairing site in one long-running job step.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$privateIp = $env:TAILSCALE_IP
if (-not $privateIp -or $privateIp -notmatch '^100\.') { throw "Private Tailscale address missing" }
if (-not $env:PAIR_PORTAL_PASSWORD -or $env:PAIR_PORTAL_PASSWORD.Length -lt 14) { throw "Private portal password missing" }
if (-not $env:GH_TOKEN) { throw "Workflow read token missing" }
$privatePassword = $env:PAIR_PORTAL_PASSWORD
$stopToken = $env:GH_TOKEN
Remove-Item Env:PAIR_PORTAL_PASSWORD,Env:GH_TOKEN -ErrorAction SilentlyContinue
$env:CODEX_HOME = Join-Path $env:RUNNER_TEMP "CodexRemoteHome"
$env:OLLAMA_MODELS = Join-Path $env:RUNNER_TEMP "ollama-models"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_CONTEXT_LENGTH = "65536"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:HIP_VISIBLE_DEVICES = "-1"
$env:NO_PROXY = "127.0.0.1,localhost"
New-Item -ItemType Directory -Force -Path $env:CODEX_HOME | Out-Null
$model = & python scripts/hermes-model-config.py default agent-models.txt
if ($LASTEXITCODE -ne 0 -or -not $model) { throw "No valid local Ollama model configured" }
if ($model -notmatch '^[a-zA-Z0-9._:/-]+$') { throw "Invalid model name" }
$configLines = @(
  ('model = "' + $model + '"')
  'model_provider = "ollama-local"'
  'model_context_window = 65536'
  'model_auto_compact_token_limit = 60000'
  'approval_policy = "on-request"'
  'sandbox_mode = "workspace-write"'
  'preferred_auth_method = "chatgpt"'
  '[model_providers.ollama-local]'
  'name = "Local Ollama"'
  'base_url = "http://127.0.0.1:11434/v1"'
  'wire_api = "responses"'
)
# Use UTF-8 without BOM for Rust/TOML CLI parsing; PowerShell 5.1
# Set-Content -Encoding UTF8 adds a BOM on Windows Server 2022.
[IO.File]::WriteAllLines((Join-Path $env:CODEX_HOME "config.toml"), $configLines, (New-Object System.Text.UTF8Encoding($false)))
$ollama = Join-Path $env:RUNNER_TEMP "ollama-bin\ollama.exe"
if (-not (Test-Path $ollama)) { throw "Ollama missing after cache restore" }
$ollamaOut = Join-Path $env:RUNNER_TEMP "codex-ollama.stdout.log"
$ollamaErr = Join-Path $env:RUNNER_TEMP "codex-ollama.stderr.log"
$ollamaProc = Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru -RedirectStandardOutput $ollamaOut -RedirectStandardError $ollamaErr
$ready = $false
for ($i=0; $i -lt 45; $i++) {
  try {
    $models = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    $tag = if ($model.Contains(":")) { $model } else { $model + ":latest" }
    if (@($models.models | Where-Object { $_.name -eq $tag }).Count -eq 0) { throw "Chosen model unavailable" }
    $ready = $true; break
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { throw "Ollama did not become ready" }
Write-Host "Codex local model engine ready on loopback, model selected privately."
$adapter = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $privateIp } | Select-Object -First 1
if (-not $adapter) { throw "Tailscale network interface missing" }
New-NetFirewallRule -DisplayName "Private Codex pairing portal" -Direction Inbound -Protocol TCP -Action Allow -LocalPort 9130 -InterfaceAlias $adapter.InterfaceAlias -RemoteAddress "100.64.0.0/10" | Out-Null
$env:PAIR_PORTAL_PASSWORD = $privatePassword
$pyExe = (Get-Command python -ErrorAction Stop).Source
$portalOut = Join-Path $env:RUNNER_TEMP "codex-pair-portal.stdout.log"
$portalErr = Join-Path $env:RUNNER_TEMP "codex-pair-portal.stderr.log"
$portalArgs = @("codex-remote/pair_portal.py","--ip",$privateIp,"--port","9130","--model",$model)
$portal = Start-Process -FilePath $pyExe -ArgumentList $portalArgs -WorkingDirectory $env:GITHUB_WORKSPACE -WindowStyle Hidden -PassThru -RedirectStandardOutput $portalOut -RedirectStandardError $portalErr
Remove-Item Env:PAIR_PORTAL_PASSWORD -ErrorAction SilentlyContinue
$webReady = $false
for ($i=0; $i -lt 45; $i++) {
  if ($portal.HasExited) { break }
  try {
    $h = Invoke-RestMethod ("http://" + $privateIp + ":9130/health") -TimeoutSec 3
    if ($h.status -eq "ok") { $webReady = $true; break }
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $webReady) {
  if (Test-Path $portalErr) { Get-Content $portalErr -Tail 8 }
  throw "Private Codex pairing site failed to start"
}
try {
  Invoke-WebRequest ("http://" + $privateIp + ":9130/") -UseBasicParsing -TimeoutSec 5 | Out-Null
  throw "The pairing site failed to require authentication"
} catch {
  if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) {
    Write-Host "The private pairing page correctly challenges unauthenticated requests."
  } else { throw }
}
Write-Host "CODEX REMOTE PAIRING PORTAL ONLINE - Tailscale port 9130, username owner, password required."
# Confirm the authenticated setup endpoint works without printing any codes.
try {
  $basic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("owner:" + $privatePassword))
  $safe = Invoke-RestMethod ("http://" + $privateIp + ":9130/api/status") -Headers @{Authorization=("Basic " + $basic)} -TimeoutSec 5
  Write-Host "Codex private authenticated setup endpoint available; interactive ChatGPT authorization still required."
} catch {
  throw "Authenticated Codex status page could not be reached"
}

"## Codex Remote on GitHub Windows VM" | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Find Tailscale device codex-remote-$env:GITHUB_RUN_ID and open its private 9130 port." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Use username owner and your existing dashboard password to authorize ChatGPT, then read the private pairing code." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Pairing/login codes and account tokens are never printed to public GitHub logs." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
$minutes = 300
if ($env:CODEX_SESSION_MINUTES) { $minutes = [int]$env:CODEX_SESSION_MINUTES }
if ($minutes -lt 2 -or $minutes -gt 310) { throw "Session minutes must be 2-310" }
$deadline = (Get-Date).AddMinutes($minutes)
$nextPoll = (Get-Date).AddSeconds(35)
$badHealth = 0
try {
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 15
    try {
      $h = Invoke-RestMethod ("http://" + $privateIp + ":9130/health") -TimeoutSec 5
      if ($h.status -eq "ok") { $badHealth = 0 } else { $badHealth++ }
    } catch { $badHealth++ }
    if ($badHealth -ge 6) { throw "Private pairing page stopped responding" }
    if ((Get-Date) -ge $nextPoll) {
      $env:GH_TOKEN = $stopToken
      try {
        $raw = & gh api ("repos/" + $env:GITHUB_REPOSITORY + "/actions/workflows/codex-remote.yml/runs?event=workflow_dispatch&per_page=70")
        if ($LASTEXITCODE -eq 0) {
          $data = ($raw | Out-String) | ConvertFrom-Json
          $stop = @($data.workflow_runs | Where-Object {
            [long]$_.id -gt [long]$env:GITHUB_RUN_ID -and
            $_.display_title -eq "Codex Remote stop" -and $_.head_branch -eq "main"
          })
          if ($stop.Count -gt 0) { Write-Host "Codex Remote safe Stop requested."; break }
        }
      } catch { Write-Warning "Could not check for remote Stop request." }
      finally { Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue }
      $nextPoll = (Get-Date).AddSeconds(40)
    }
  }
} finally {
  # No Codex account credentials or manual pairing codes are archived.
  if (-not $portal.HasExited) { Stop-Process -Id $portal.Id -Force -ErrorAction SilentlyContinue }
  if (-not $ollamaProc.HasExited) { Stop-Process -Id $ollamaProc.Id -Force -ErrorAction SilentlyContinue }
  Write-Host "Codex Remote session ended, with no ChatGPT credentials uploaded."
}

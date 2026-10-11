$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_CONTEXT_LENGTH = "16384"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:HIP_VISIBLE_DEVICES = "-1"
$env:HERMES_HOME = Join-Path $env:RUNNER_TEMP "hermes-sandbox"
$logDir = Join-Path $env:RUNNER_TEMP "hermes-test-logs"
New-Item -ItemType Directory -Path $logDir,$env:HERMES_HOME -Force | Out-Null
Write-Host "Allocated logical CPUs: $([Environment]::ProcessorCount)"

# Hermes agent uses an independently downloaded official tool-capable model.
# Do not change the user's existing Android Ollama chat model or Tailscale server.
Write-Host "Installing Ollama..."
irm https://ollama.com/install.ps1 | iex
$paths = @("$env:LOCALAPPDATA\Programs\Ollama\ollama.exe", "$env:ProgramFiles\Ollama\ollama.exe")
$ollama = $paths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ollama) { throw "Ollama executable not found" }
Get-Process -Name ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$server = Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru
$ready = $false
for ($i=0; $i -lt 90; $i++) {
  try {
    Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
    $ready = $true
    break
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { throw "Ollama server failed readiness check" }
& $ollama pull qwen2.5-coder:3b
if ($LASTEXITCODE -ne 0) { throw "Unable to pull the tool-capable standard 3B model" }
Write-Host "Ollama model ready."

# Validate that the model endpoint exists before introducing another component.
$body = @{model="qwen2.5-coder:3b";messages=@(@{role="user";content="Say HELLO"});stream=$false;options=@{num_ctx=16384;num_predict=30}} | ConvertTo-Json -Depth 6
$r = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/chat" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 240
if (-not $r.message.content) { throw "Ollama did not return chat content" }
Write-Host "Ollama chat API responded."

Write-Host "Installing official Hermes Agent for Windows..."
$installer = Invoke-RestMethod "https://hermes-agent.nousresearch.com/install.ps1"
& ([scriptblock]::Create($installer)) -NonInteractive -HermesHome $env:HERMES_HOME
if (-not $?) { throw "Hermes installer failed" }
$hermes = Join-Path $env:HERMES_HOME "bin\hermes.exe"
if (-not (Test-Path $hermes)) { throw "Hermes launcher missing at $hermes" }
& $hermes --version
if ($LASTEXITCODE -ne 0) { throw "Hermes version command failed" }

& $hermes config set model.default "qwen2.5-coder:3b"
if ($LASTEXITCODE -ne 0) { throw "Hermes model.default config failed" }
& $hermes config set model.provider custom
if ($LASTEXITCODE -ne 0) { throw "Hermes provider config failed" }
& $hermes config set model.base_url "http://127.0.0.1:11434/v1"
if ($LASTEXITCODE -ne 0) { throw "Hermes base URL config failed" }
& $hermes config set model.context_length 16384
if ($LASTEXITCODE -ne 0) { Write-Warning "Context override may not be supported." }

# Non-interactive, bounded, read-only task. Hermes may need more RAM/context
# for a full agent session. Keep this test separate from production credentials.
$work = Join-Path $env:RUNNER_TEMP "hermes-probe-workspace"
New-Item -ItemType Directory -Path $work -Force | Out-Null
Set-Content -Path (Join-Path $work "note.txt") -Value "HERMES_SAFE_TEST_NOTE" -Encoding utf8
Push-Location $work
try {
  Write-Host "Starting bounded Hermes agent smoke test..."
  $outputFile = Join-Path $logDir "agent-output.txt"
  $started = Get-Date
  $proc = Start-Process -FilePath $hermes -ArgumentList @("chat","--oneshot","--max-turns","3","-q","Read note.txt in the current folder using a file/terminal tool and tell me its exact contents.") -WorkingDirectory $work -PassThru -RedirectStandardOutput $outputFile -RedirectStandardError (Join-Path $logDir "agent-errors.txt") -WindowStyle Hidden
  if (-not $proc.WaitForExit(180000)) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Write-Warning "Agent smoke test exceeded 3 minutes. Installation and Ollama checks passed."
  } else {
    Write-Host "Hermes test exited with code $($proc.ExitCode) in $([math]::Round(((Get-Date)-$started).TotalSeconds,1)) seconds"
    $answer = Get-Content $outputFile -Raw -ErrorAction SilentlyContinue
    if ($answer -match "HERMES_SAFE_TEST_NOTE") {
      Write-Host "Hermes tool-mediated file reading appears successful; inspect test output."
    } else {
      Write-Warning "Hermes could not verify reading the test file. Inspect logs."
    }
  }
} finally { Pop-Location }

Write-Host "Hermes Agent installation probe completed."
"## Hermes Agent installation probe" | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY
"Native Windows installer and standard Qwen2.5 Coder 3B Ollama model attempted; see smoke-test logs. No Tailscale or Android configuration was modified." | Out-File -Append -FilePath $env:GITHUB_STEP_SUMMARY

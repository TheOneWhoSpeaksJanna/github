# Prepare only Ollama + user-selected standard local text models.
# No private conversations or credentials enter this cache-producing step.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$env:OLLAMA_MODELS = Join-Path $env:RUNNER_TEMP "ollama-models"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_CONTEXT_LENGTH = "4096"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:HIP_VISIBLE_DEVICES = "-1"
$env:NO_PROXY = "127.0.0.1,localhost"
$binaryDir = Join-Path $env:RUNNER_TEMP "ollama-bin"
$exe = Join-Path $binaryDir "ollama.exe"
$helper = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-model-config.py"
$modelsFile = Join-Path $env:GITHUB_WORKSPACE "agent-models.txt"
$names = @(& python $helper list $modelsFile)
if ($LASTEXITCODE -ne 0 -or $names.Count -lt 1) { throw "Invalid file-agent model list" }
Write-Host "File agent model: $($names[0]). Additional configured models: $($names.Count - 1)"
New-Item -ItemType Directory -Force -Path $binaryDir,$env:OLLAMA_MODELS | Out-Null
if (-not (Test-Path $exe)) {
  Write-Host "Installing Ollama runtime into clean cache."
  irm https://ollama.com/install.ps1 | iex
  $locations = @("$env:LOCALAPPDATA\Programs\Ollama", "$env:ProgramFiles\Ollama")
  $source = $locations | Where-Object { Test-Path (Join-Path $_ "ollama.exe") } | Select-Object -First 1
  if (-not $source) { throw "Ollama Windows installation missing" }
  Copy-Item "$source\*" $binaryDir -Force -Recurse
  if (-not (Test-Path $exe)) { throw "Ollama executable missing" }
} else {
  Write-Host "Cached Ollama executable available."
}
$missing = @()
foreach ($name in $names) {
  $manifest = & python $helper manifest $modelsFile --models-root $env:OLLAMA_MODELS --model $name
  if ($LASTEXITCODE -ne 0) { throw "Invalid model name" }
  if (-not (Test-Path $manifest)) { $missing += $name }
}
if ($missing.Count -gt 0) {
  Write-Host "Downloading selected model(s), no credentials or chat data."
  Get-Process -Name ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  $log = Join-Path $env:RUNNER_TEMP "agent-ollama-prepare.out.log"
  $err = Join-Path $env:RUNNER_TEMP "agent-ollama-prepare.err.log"
  $proc = Start-Process $exe -ArgumentList "serve" -PassThru -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err
  $ready = $false
  for ($i=0; $i -lt 55; $i++) {
    try {
      Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
      $ready = $true; break
    } catch { Start-Sleep -Seconds 2 }
  }
  if (-not $ready) { throw "Ollama model download server did not start" }
  try {
    foreach ($name in $missing) {
      Write-Host "Pulling $name"
      & $exe pull $name
      if ($LASTEXITCODE -ne 0) { throw "Ollama model download failed: $name" }
    }
  } finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
  }
} else {
  Write-Host "Selected model(s) already cached, no downloads required."
}
foreach ($name in $names) {
  $manifest = & python $helper manifest $modelsFile --models-root $env:OLLAMA_MODELS --model $name
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $manifest)) { throw "Model missing after download: $name" }
}
Write-Host "Ollama runtime and task-model caches are ready."

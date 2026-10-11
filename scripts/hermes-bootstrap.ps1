# Build/cache only standard public runtime components. Do not pass any secrets.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$env:HERMES_HOME = Join-Path $env:RUNNER_TEMP "hermes"
$env:OLLAMA_MODELS = Join-Path $env:RUNNER_TEMP "ollama-models"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:HIP_VISIBLE_DEVICES = "-1"
$env:NO_PROXY = "127.0.0.1,localhost"
$binaryDir = Join-Path $env:RUNNER_TEMP "ollama-bin"
$ollama = Join-Path $binaryDir "ollama.exe"
$hermes = Join-Path $env:HERMES_HOME "bin\hermes.exe"
$modelManifest = Join-Path $env:OLLAMA_MODELS "manifests\registry.ollama.ai\library\qwen3.5\2b"
New-Item -ItemType Directory -Force -Path $env:HERMES_HOME,$env:OLLAMA_MODELS | Out-Null
if (-not (Test-Path $ollama)) {
  Write-Host "Ollama cache missing. Downloading Windows runtime once."
  irm https://ollama.com/install.ps1 | iex
  $locations = @("$env:LOCALAPPDATA\Programs\Ollama","$env:ProgramFiles\Ollama")
  $source = $locations | Where-Object { Test-Path (Join-Path $_ "ollama.exe") } | Select-Object -First 1
  if (-not $source) { throw "Windows Ollama installation did not include ollama.exe" }
  New-Item -ItemType Directory -Path $binaryDir -Force | Out-Null
  Copy-Item -Path "$source\*" -Destination $binaryDir -Recurse -Force
  if (-not (Test-Path $ollama)) { throw "Could not stage cached Ollama binary" }
  Start-Sleep -Seconds 8
} else {
  Write-Host "Using cached Ollama runtime. Windows installer skipped."
}

if (-not (Test-Path $modelManifest)) {
  Write-Host "Model cache missing. Downloading standard Qwen3.5 2B once."
  $pulled = $false
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    Get-Process -Name ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $proc = Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $env:RUNNER_TEMP "ollama-bootstrap.stdout.log") -RedirectStandardError (Join-Path $env:RUNNER_TEMP "ollama-bootstrap.stderr.log")
    $ready = $false
    for ($i=0; $i -lt 45; $i++) {
      if ($proc.HasExited) { break }
      try {
        Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
        $ready = $true
        break
      } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) {
      Write-Warning "Ollama API failed to start on attempt $attempt."
      continue
    }
    & $ollama pull "qwen3.5:2b"
    if ($LASTEXITCODE -eq 0 -and (Test-Path $modelManifest)) {
      $pulled = $true
      Write-Host "Model downloaded and manifest verified."
      break
    }
    Write-Warning "Model pull failed; retrying after server restart."
    Start-Sleep -Seconds (3 * $attempt)
  }
  if (-not $pulled) { throw "Model pull never succeeded; cannot cache incomplete model files." }
} else {
  Write-Host "Using cached Qwen3.5 2B model. Download skipped."
}
Get-Process -Name ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if (-not (Test-Path $hermes)) {
  Write-Host "Hermes executable cache missing. Bootstrapping trusted official pinned version once."
  $installer = Invoke-RestMethod "https://hermes-agent.nousresearch.com/install.ps1"
  & ([scriptblock]::Create($installer)) -NonInteractive -HermesHome $env:HERMES_HOME -Commit "79b45d1647f6b5680768d851c4c406e8cc550a1e"
  if (-not $?) { throw "Hermes installer failed" }
  if (-not (Test-Path $hermes)) { throw "Hermes launcher missing after installation" }
} else {
  Write-Host "Using cached Hermes Agent binaries and Python environment. Installer skipped."
}
& $hermes --version
if ($LASTEXITCODE -ne 0) { throw "Cached Hermes executable did not run" }
if (-not (Test-Path $modelManifest)) { throw "Cached Ollama model missing after preparation" }
Write-Host "Hermes and Ollama public binaries prepared. Cache contains no user secrets or conversations."

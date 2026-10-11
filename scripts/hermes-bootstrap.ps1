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
$modelHelper = Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-model-config.py"
$modelConfig = Join-Path $env:GITHUB_WORKSPACE "hermes-models.txt"
$selectedModels = @(& python $modelHelper list $modelConfig)
if ($LASTEXITCODE -ne 0 -or $selectedModels.Count -eq 0) { throw "Invalid Hermes model list" }
Write-Host "Hermes default model: $($selectedModels[0]); total configured: $($selectedModels.Count)."
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

# No hardcoded default model. The first uncommented line of hermes-models.txt
# is the agent model; additional lines are installed too. Check Ollama manifests
# before pulling so an exact cache hit requires no network downloads.
$missingModels = @()
foreach ($modelName in $selectedModels) {
  $manifest = & python $modelHelper manifest $modelConfig --models-root $env:OLLAMA_MODELS --model $modelName
  if ($LASTEXITCODE -ne 0) { throw "Invalid Ollama model name in Hermes file" }
  if (-not (Test-Path $manifest)) { $missingModels += $modelName }
}
if ($missingModels.Count -gt 0) {
  Write-Host "Downloading $($missingModels.Count) additional model(s) selected in hermes-models.txt."
  for ($attempt = 1; $attempt -le 4 -and $missingModels.Count -gt 0; $attempt++) {
    Get-Process -Name ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $log = Join-Path $env:RUNNER_TEMP "ollama-model-bootstrap-$attempt.stdout.log"
    $err = Join-Path $env:RUNNER_TEMP "ollama-model-bootstrap-$attempt.stderr.log"
    $proc = Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    $ready = $false
    for ($i = 0; $i -lt 45; $i++) {
      if ($proc.HasExited) { break }
      try {
        Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
        $ready = $true
        break
      } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) {
      Write-Warning "Ollama API failed to start for model downloads (attempt $attempt)."
      continue
    }
    $remaining = @()
    foreach ($modelName in $missingModels) {
      Write-Host "Installing Hermes Ollama model: $modelName"
      & $ollama pull $modelName
      $manifest = & python $modelHelper manifest $modelConfig --models-root $env:OLLAMA_MODELS --model $modelName
      if ($LASTEXITCODE -ne 0) { throw "Could not resolve model manifest" }
      if (-not (Test-Path $manifest)) {
        Write-Warning "Model not ready: $modelName"
        $remaining += $modelName
      }
    }
    $missingModels = @($remaining)
    if ($missingModels.Count -gt 0) { Start-Sleep -Seconds (3 * $attempt) }
  }
  if ($missingModels.Count -gt 0) { throw "Some models in hermes-models.txt failed to download" }
} else {
  Write-Host "All requested Hermes models found in the clean cache. No download needed."
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
# Confirm all configured Ollama manifests exist before caching public model files.
foreach ($modelName in $selectedModels) {
  $manifest = & python $modelHelper manifest $modelConfig --models-root $env:OLLAMA_MODELS --model $modelName
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $manifest)) { throw "Required Hermes model was not prepared: $modelName" }
}

# Add a real mobile-native textarea to Hermes Chat without opening another
# unauthenticated API or modifying the Ollama runtime. Reuse the pinned source
# and rebuild the frontend ONLY when this patch version is missing.
$projectRoot = Join-Path $env:HERMES_HOME "hermes-agent"
$chatSource = Join-Path $projectRoot "web\src\pages\ChatPage.tsx"
$distIndex = Join-Path $projectRoot "hermes_cli\web_dist\index.html"
$mobileMarker = Join-Path $projectRoot "hermes_cli\web_dist\mobile-composer-v1.marker"
if (-not (Test-Path $chatSource)) { throw "Hermes ChatPage source not found" }
& python (Join-Path $env:GITHUB_WORKSPACE "scripts\hermes-mobile-composer.py") $chatSource
if ($LASTEXITCODE -ne 0) { throw "Hermes Android composer patch failed" }
if (-not (Test-Path $mobileMarker)) {
  Write-Host "Building patched Hermes web UI once (Android native text composer)..."
  Push-Location $projectRoot
  try {
    $env:HERMES_WEB_BUILD_LIGHT = "1"
    & npm run build --workspace web
    if ($LASTEXITCODE -ne 0) { throw "Hermes mobile web UI build failed" }
  } finally {
    Pop-Location
  }
  if (-not (Test-Path $distIndex)) { throw "Patched dashboard HTML not produced" }
  Set-Content -Path $mobileMarker -Value "mobile-composer-v1" -Encoding ASCII
  Write-Host "Patched Hermes dashboard built."
} else {
  Write-Host "Using cached Android-friendly Hermes dashboard."
}

Write-Host "Hermes and Ollama public binaries prepared. Cache contains no user secrets or conversations."

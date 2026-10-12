# Prepare a personally controlled Windows PC for ChatGPT Codex Remote.
# Run INTERACTIVELY as the normal Windows user, not on GitHub Actions.
# The ChatGPT desktop app must be signed in and paired manually with Android.
#
# Check-only:
#   powershell -File .\scripts\setup-codex-remote-windows.ps1
# Install official desktop prerequisites after reviewing:
#   powershell -File .\scripts\setup-codex-remote-windows.ps1 -Install
# Select an already-downloaded Ollama model for Codex desktop:
#   powershell -File .\scripts\setup-codex-remote-windows.ps1 -Model MODEL_NAME
param(
  [switch]$Install,
  [string]$Model
)
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
  throw "This setup requires Windows 10/11 on your own PC."
}
if ($env:GITHUB_ACTIONS -eq "true" -or $env:CI -eq "true") {
  throw "ChatGPT Codex Remote requires an interactive signed-in desktop. Do not run this script on GitHub Actions."
}

function Find-Ollama {
  $cmd = Get-Command "ollama.exe" -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
  )
  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p) { return $p }
  }
  return $null
}
function Install-Package([string]$Id, [string]$Source) {
  $params = @("install", "--id", $Id, "--exact",
              "--accept-package-agreements", "--accept-source-agreements")
  if ($Source) { $params += @("--source", $Source) }
  Write-Host "Installing reviewed package: $Id"
  & winget @params
  if ($LASTEXITCODE -ne 0) {
    throw "Package $Id was not installed. Use the official desktop download page if your Microsoft Store or winget is restricted."
  }
}
if ($Install) {
  if (-not (Get-Command "winget.exe" -ErrorAction SilentlyContinue)) {
    throw "Windows Package Manager (winget) is not installed. Install App Installer from Microsoft or download the official applications manually."
  }
  # The package ID is from OpenAI's current Windows desktop documentation.
  # The Ollama package ID is its official Windows package-manager manifest.
  Install-Package "9PLM9XGG6VKS" "msstore"
  Install-Package "Ollama.Ollama" "winget"
  Write-Host "Installation completed or confirmed. Open the ChatGPT desktop app and sign in manually."
}

Write-Host ""
Write-Host "=== PRIVATE WINDOWS HOST CHECK ==="
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Write-Host "Windows: $($os.Caption)"
Write-Host "CPU logical processors: $($cpu.NumberOfLogicalProcessors)"
Write-Host "Installed memory: $([math]::Round($os.TotalVisibleMemorySize / 1MB, 1)) GB"
Write-Host "Free memory: $([math]::Round($os.FreePhysicalMemory / 1MB, 1)) GB"

$installedApps = @(Get-AppxPackage -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like "*ChatGPT*" -or $_.PackageFamilyName -like "*ChatGPT*" })
if ($installedApps.Count -gt 0) {
  Write-Host "ChatGPT desktop app package: detected."
} else {
  Write-Host "ChatGPT desktop app package: not detected by Appx enumeration."
  Write-Host "Confirm installation and sign in using the official ChatGPT app."
}

$ollama = Find-Ollama
if ($ollama) {
  Write-Host "Local Ollama executable: found."
  & $ollama --version
  if ($LASTEXITCODE -ne 0) { Write-Warning "Ollama version check returned an error." }
} else {
  Write-Host "Ollama executable: NOT FOUND. Install it before selecting a model."
}
if ($Model) {
  if ($Model.Length -gt 160 -or $Model -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._/-]*(?::[a-zA-Z0-9._-]+)?$') {
    throw "Invalid Ollama model name."
  }
  if (-not $ollama) { throw "Install Ollama before configuring a model." }
  # Do not download arbitrary sizes implicitly. Explicitly request a model
  # that is already installed on your PC.
  $localModels = & $ollama list
  if ($LASTEXITCODE -ne 0) { throw "Ollama list failed. Open Ollama and try again." }
  $matches = @($localModels | Select-String -Pattern ([regex]::Escape($Model)))
  if ($matches.Count -eq 0) {
    throw "Model $Model is not installed. Download a tool-capable model suitable for your PC using Ollama, then rerun with -Model."
  }
  Write-Host "Setting selected local model for the Codex desktop application."
  & $ollama launch codex-app --model $Model
  if ($LASTEXITCODE -ne 0) {
    throw "Ollama could not launch Codex desktop with this model. Open the desktop app once, update Ollama to 0.24+, and retry."
  }
}
Write-Host ""
Write-Host "=== PAIR ANDROID WITH THIS PC ==="
Write-Host "1. Launch the latest ChatGPT DESKTOP application and sign in with your own ChatGPT account."
Write-Host "2. Open Codex, then Settings > Connections > Control this Mac or PC > Set up."
Write-Host "3. Approve the remote connection and scan its QR code with ChatGPT on Android."
Write-Host "4. Finish pairing on your phone with the SAME account and workspace."
Write-Host "5. Open ChatGPT Android > Codex (or Remote) and select this PC."
Write-Host "6. Keep the PC awake, connected to the Internet, and ChatGPT signed in."
Write-Host ""
Write-Host "WARNING: This script cannot pair the apps, authorize your ChatGPT account, or make an ephemeral GitHub Actions VM a Codex Remote host."
Write-Host "For actual local Codex tool use, choose a model with strong tool calling and roughly 64K or larger native context, on a PC with adequate resources."

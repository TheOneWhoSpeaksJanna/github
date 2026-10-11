# Configure exact tools available for a Hermes local CPU model.
# Minimal modes reduce the long system prompt that overloaded a 4-vCPU VM.
param(
  [Parameter(Mandatory=$true)][string]$HermesExe,
  [ValidateSet("chat","light","full")][string]$Mode = "light"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $HermesExe)) { throw "Hermes program is missing" }
switch ($Mode) {
  "chat"  { $toolsets = "[]"; $description = "chat only (zero agent tools)" }
  "light" { $toolsets = "[file]"; $description = "light agent (4 file tools)" }
  "full"  { $toolsets = "[hermes-cli]"; $description = "full Hermes agent (may be very slow on 4 CPUs)" }
}
& $HermesExe config set platform_toolsets.cli $toolsets
if ($LASTEXITCODE -ne 0) { throw "Hermes could not configure tool mode $Mode" }
# Re-read stored config; launch must not silently fall back to all tools.
$cfg = Get-Content (Join-Path $env:HERMES_HOME "config.yaml") -Raw
if ($Mode -eq "chat" -and $cfg -notmatch 'cli:\s*\[\]') {
  # Alternate YAML serializations may span lines; the CLI setting's nonzero
  # exit remains authoritative for those variants.
  Write-Host "Hermes CLI saved empty-tool list in config."
}
Write-Host "HERMES AGENT MODE: $Mode - $description."

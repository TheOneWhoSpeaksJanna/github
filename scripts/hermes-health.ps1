# Public-safe telemetry for an ephemeral Hermes VM.
# No IPs, prompts, passwords, model replies, environment, or credential values.
param([string]$Destination)
$ErrorActionPreference = "Continue"
if (-not $Destination) { $Destination = Join-Path $env:RUNNER_TEMP "hermes-health.jsonl" }
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
$cpu = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1
$names = @("ollama", "llama-server", "python", "hermes")
$procs = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -in $names } |
  ForEach-Object { @{
    process = $_.ProcessName
    ram_mb = [math]::Round($_.WorkingSet64 / 1MB, 1)
    cpu_total_s = [math]::Round($_.CPU, 1)
  } })
$ctx = $null
$backendHealthy = $false
try {
  $models = Invoke-RestMethod "http://127.0.0.1:11434/api/ps" -TimeoutSec 3
  $loaded = @($models.models | Where-Object { $_ })
  $backendHealthy = $true
  if ($loaded.Count -gt 0) { $ctx = $loaded[0].context_length }
} catch { $backendHealthy = $false }
$record = [ordered]@{
  utc = (Get-Date).ToUniversalTime().ToString("o")
  cpu_logical_count = if ($cpu) { $cpu.NumberOfLogicalProcessors } else { $null }
  ram_total_gb = if ($os) { [math]::Round($os.TotalVisibleMemorySize/1MB,2) } else { $null }
  ram_free_gb = if ($os) { [math]::Round($os.FreePhysicalMemory/1MB,2) } else { $null }
  backend_healthy = $backendHealthy
  loaded_context_tokens = $ctx
  processes = $procs
}
$record | ConvertTo-Json -Compress -Depth 5 | Out-File -Append -Encoding utf8 $Destination
$procRam = [math]::Round((@($procs | ForEach-Object { $_.ram_mb } | Measure-Object -Sum)[0].Sum), 1)
Write-Host "HERMES PC HEALTH: freeRAM=$($record.ram_free_gb)GB workerRAM=$($procRam)MB loadedContext=$ctx backend=$backendHealthy."

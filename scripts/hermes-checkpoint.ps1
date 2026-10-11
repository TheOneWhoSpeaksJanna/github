# Upload only AES-256-GCM encrypted Hermes state to a rolling prerelease.
# Each checkpoint is remotely durable even while its Actions job keeps running.
param(
  [Parameter(Mandatory=$true)][string]$EncryptedFile,
  [Parameter(Mandatory=$true)][string]$Repository,
  [Parameter(Mandatory=$true)][string]$RunId,
  [string]$Tag = "hermes-encrypted-checkpoints"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $EncryptedFile)) { throw "Encrypted backup missing" }
if (-not $env:GH_TOKEN) { throw "GitHub upload token missing" }
if ($Repository -notmatch '^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$') { throw "Invalid repository name" }
if ($Tag -notmatch '^[a-zA-Z0-9_.-]+$') { throw "Invalid release tag" }
# Expected 404 on the first session; don't treat native stderr as fatal.
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
  $releaseData = & gh api "repos/$Repository/releases/tags/$Tag" 2>$null
  $releaseExists = ($LASTEXITCODE -eq 0)
} finally {
  $ErrorActionPreference = $previousErrorAction
}
if (-not $releaseExists) {
  Write-Host "Creating dedicated encrypted checkpoint prerelease."
  & gh release create $Tag --repo $Repository --target main --title "Encrypted Hermes checkpoints" --notes "Rolling AES-256-GCM encrypted Hermes state. No plaintext user data. Encrypted release assets are downloadable on this public repository." --prerelease
  if ($LASTEXITCODE -ne 0) { throw "Could not create checkpoint release" }
}
$destDir = Join-Path $env:RUNNER_TEMP "hermes-checkpoint-upload"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfff")
$name = "hermes-state-$RunId-$stamp.enc"
$staged = Join-Path $destDir $name
Copy-Item -LiteralPath $EncryptedFile -Destination $staged -Force
try {
  & gh release upload $Tag $staged --repo $Repository
  if ($LASTEXITCODE -ne 0) { throw "Encrypted checkpoint upload failed" }
  Write-Host "Encrypted Hermes state saved off-VM as release asset: $name"
  # Retain eight recent backups for rolling recovery. A successful final
  # job also creates a separate 90-day encrypted Actions artifact.
  $release = & gh api "repos/$Repository/releases/tags/$Tag" | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not list checkpoints to prune; leaving them intact."
  } else {
    $old = @($release.assets | Where-Object { $_.name -like "hermes-state-*.enc" } | Sort-Object created_at -Descending | Select-Object -Skip 8)
    foreach ($item in $old) {
      & gh api -X DELETE "repos/$Repository/releases/assets/$($item.id)" | Out-Null
      if ($LASTEXITCODE -ne 0) { Write-Warning "Could not prune one older encrypted checkpoint." }
    }
  }
} finally {
  Remove-Item -LiteralPath $staged -Force -ErrorAction SilentlyContinue
}

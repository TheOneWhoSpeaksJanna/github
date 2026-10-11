# Upload a previously AES-256-GCM encrypted Hermes backup to a rolling
# GitHub Release. Called inside the long-running Hermes job, so the backup
# survives VM cancellation/crashes. Only ciphertext is uploaded.
param(
  [Parameter(Mandatory=$true)][string]$EncryptedFile,
  [Parameter(Mandatory=$true)][string]$Repository,
  [Parameter(Mandatory=$true)][string]$RunId,
  [string]$Tag = "hermes-encrypted-checkpoints"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $EncryptedFile)) { throw "Encrypted backup missing" }
if (-not $env:GH_TOKEN) { throw "GitHub upload token was not supplied" }
if ($Repository -notmatch '^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$') { throw "Invalid GitHub repository" }
if ($Tag -notmatch '^[a-zA-Z0-9_.-]+
# A dedicated prerelease makes the checkpoint assets accessible to the GitHub
# REST API during a running job, unlike end-of-job Actions artifacts.
# gh returns 404 on first use. Do not turn the expected missing-release
# stderr into a terminating PowerShell NativeCommandError.
$priorErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
  $releaseInfo = & gh api "repos/$Repository/releases/tags/$tag" 2>$null
  $releaseExists = ($LASTEXITCODE -eq 0)
} finally {
  $ErrorActionPreference = $priorErrorAction
}
if (-not $releaseExists) {
  Write-Host "Creating first dedicated encrypted checkpoint release."
  & gh release create $tag --repo $Repository --target main --title "Encrypted Hermes checkpoints" --notes "Rolling encrypted Hermes state backups. Assets contain AES-256-GCM ciphertext, not plaintext. This release is an internal backup mechanism." --prerelease
  if ($LASTEXITCODE -ne 0) { throw "Could not create checkpoint release; check workflow contents:write permission" }
}
$destDir = Join-Path $env:RUNNER_TEMP "hermes-checkpoint-upload"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfff")
$name = "hermes-state-$RunId-$stamp.enc"
$staged = Join-Path $destDir $name
Copy-Item -LiteralPath $EncryptedFile -Destination $staged -Force
try {
  & gh release upload $tag $staged --repo $Repository
  if ($LASTEXITCODE -ne 0) { throw "Encrypted checkpoint upload failed" }
  Write-Host "Encrypted Hermes backup uploaded as a GitHub release asset: $name"
  # Keep only the latest 8 live checkpoints (80 min at 10-min intervals).
  # The final Actions artifact from a successfully completed run is retained
  # separately for up to 90 days.
  $release = & gh api "repos/$Repository/releases/tags/$tag" | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not list older checkpoint assets; leaving them untouched."
  } else {
    $old = @($release.assets | Where-Object { $_.name -like "hermes-state-*.enc" } | Sort-Object created_at -Descending | Select-Object -Skip 8)
    foreach ($item in $old) {
      & gh api -X DELETE "repos/$Repository/releases/assets/$($item.id)" | Out-Null
      if ($LASTEXITCODE -ne 0) { Write-Warning "Could not prune an older encrypted checkpoint." }
    }
  }
} finally {
  Remove-Item -LiteralPath $staged -Force -ErrorAction SilentlyContinue
}
) { throw "Invalid checkpoint release tag" }
$tag = $Tag
# A dedicated prerelease makes the checkpoint assets accessible to the GitHub
# REST API during a running job, unlike end-of-job Actions artifacts.
$releaseInfo = & gh api "repos/$Repository/releases/tags/$tag" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Creating first dedicated encrypted checkpoint release."
  & gh release create $tag --repo $Repository --target main --title "Encrypted Hermes checkpoints" --notes "Rolling encrypted Hermes state backups. Assets contain AES-256-GCM ciphertext, not plaintext. This release is an internal backup mechanism." --prerelease
  if ($LASTEXITCODE -ne 0) { throw "Could not create checkpoint release; check workflow contents:write permission" }
}
$destDir = Join-Path $env:RUNNER_TEMP "hermes-checkpoint-upload"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfff")
$name = "hermes-state-$RunId-$stamp.enc"
$staged = Join-Path $destDir $name
Copy-Item -LiteralPath $EncryptedFile -Destination $staged -Force
try {
  & gh release upload $tag $staged --repo $Repository
  if ($LASTEXITCODE -ne 0) { throw "Encrypted checkpoint upload failed" }
  Write-Host "Encrypted Hermes backup uploaded as a GitHub release asset: $name"
  # Keep only the latest 8 live checkpoints (80 min at 10-min intervals).
  # The final Actions artifact from a successfully completed run is retained
  # separately for up to 90 days.
  $release = & gh api "repos/$Repository/releases/tags/$tag" | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not list older checkpoint assets; leaving them untouched."
  } else {
    $old = @($release.assets | Where-Object { $_.name -like "hermes-state-*.enc" } | Sort-Object created_at -Descending | Select-Object -Skip 8)
    foreach ($item in $old) {
      & gh api -X DELETE "repos/$Repository/releases/assets/$($item.id)" | Out-Null
      if ($LASTEXITCODE -ne 0) { Write-Warning "Could not prune an older encrypted checkpoint." }
    }
  }
} finally {
  Remove-Item -LiteralPath $staged -Force -ErrorAction SilentlyContinue
}

<#
.SYNOPSIS
    Downloads every image referenced by the converted posts into its page bundle.

.DESCRIPTION
    Run this from the repository root WHILE THE OLD WORDPRESS SITE IS STILL UP.
    Re-running is safe: files that already exist are skipped. Anything that could
    not be fetched is written to image-failures.tsv so you can retry or source it
    from a backup.

.PARAMETER Manifest
    Path to the TSV produced by wxr2hugo.py. Defaults to image-manifest.tsv.

.PARAMETER FallbackHost
    Host to retry against when the canonical host fails. This is the App Service
    default hostname, which still serves some of the older uploads.

.PARAMETER Parallel
    Number of simultaneous downloads. Requires PowerShell 7+. Defaults to 1.

.PARAMETER Retry
    Attempts per URL before falling back. Defaults to 3.

.EXAMPLE
    .\download-images.ps1

.EXAMPLE
    .\download-images.ps1 -Parallel 8 -Retry 2
#>
[CmdletBinding()]
param(
    [string]$Manifest = 'image-manifest.tsv',
    [string]$FallbackHost = 'blogehn.azurewebsites.net',
    [ValidateRange(1, 32)][int]$Parallel = 1,
    [ValidateRange(1, 10)][int]$Retry = 3,
    [string]$FailureLog = 'image-failures.tsv'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Windows PowerShell renders a progress bar per request, which is dramatically slow.
$ProgressPreference = 'SilentlyContinue'

if (-not (Test-Path -LiteralPath $Manifest)) {
    throw "Manifest '$Manifest' not found. Run this from the repository root."
}

if ($PSVersionTable.PSVersion.Major -lt 6) {
    # Windows PowerShell 5.1 still negotiates TLS 1.0 by default, which the
    # site will refuse.
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.SecurityProtocolType]::Tls12
}

if ($Parallel -gt 1 -and $PSVersionTable.PSVersion.Major -lt 7) {
    Write-Warning "Parallel downloads need PowerShell 7 or later. Falling back to sequential."
    $Parallel = 1
}

# --- Load the manifest -----------------------------------------------------

$rows = Import-Csv -LiteralPath $Manifest -Delimiter "`t" |
    Where-Object { $_.url -and $_.bundle -and $_.filename }

if (-not $rows) { throw "No usable rows in '$Manifest'." }

$queue = [System.Collections.Generic.List[object]]::new()
$skipped = 0

foreach ($row in $rows) {
    $destination = Join-Path $row.bundle $row.filename
    if ((Test-Path -LiteralPath $destination) -and
        (Get-Item -LiteralPath $destination).Length -gt 0) {
        $skipped++
        continue
    }
    $queue.Add([pscustomobject]@{
        Url         = $row.url
        Bundle      = $row.bundle
        Filename    = $row.filename
        Destination = $destination
    })
}

Write-Host "$($rows.Count) images in manifest, $skipped already present, $($queue.Count) to fetch."
if ($queue.Count -eq 0) {
    Write-Host 'Nothing to do.'
    return
}

# --- The worker ------------------------------------------------------------
# Held as text rather than a scriptblock: ForEach-Object -Parallel refuses to
# marshal a scriptblock through $using:, so each runspace recreates it.

$workerSource = @'
param($Item, $FallbackHost, $Retry)

$ProgressPreference = 'SilentlyContinue'
$temporary = "$($Item.Destination).part"
New-Item -ItemType Directory -Path $Item.Bundle -Force | Out-Null

# Try the canonical host, then the App Service hostname.
$candidates = @($Item.Url)
$alternate = $Item.Url -replace 'blog\.ehn\.nu', $FallbackHost
if ($alternate -ne $Item.Url) { $candidates += $alternate }

function Get-StatusCode($ErrorRecord) {
    $response = $ErrorRecord.Exception.PSObject.Properties['Response']
    if (-not $response -or -not $response.Value) { return 0 }
    try { return [int]$response.Value.StatusCode } catch { return 0 }
}

$lastError = $null
foreach ($candidate in $candidates) {
    for ($attempt = 1; $attempt -le $Retry; $attempt++) {
        try {
            Invoke-WebRequest -Uri $candidate -OutFile $temporary `
                -TimeoutSec 60 -UseBasicParsing -ErrorAction Stop

            if ((Get-Item -LiteralPath $temporary).Length -eq 0) {
                throw 'Empty response body.'
            }
            Move-Item -LiteralPath $temporary -Destination $Item.Destination -Force
            return [pscustomobject]@{ Ok = $true; Item = $Item; Error = $null }
        }
        catch {
            $lastError = $_.Exception.Message
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue

            # A missing or forbidden file will not appear on retry. Anything
            # else (timeouts, 5xx, throttling) is worth another go.
            $status = Get-StatusCode $_
            if ($status -ge 400 -and $status -lt 500 -and
                $status -notin @(408, 429)) { break }

            if ($attempt -lt $Retry) { Start-Sleep -Seconds (2 * $attempt) }
        }
    }
}

return [pscustomobject]@{ Ok = $false; Item = $Item; Error = $lastError }
'@

$worker = [scriptblock]::Create($workerSource)

# --- Run -------------------------------------------------------------------

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

if ($Parallel -gt 1) {
    $results = $queue | ForEach-Object -ThrottleLimit $Parallel -Parallel {
        $worker = [scriptblock]::Create($using:workerSource)
        & $worker $_ $using:FallbackHost $using:Retry
    }
}
else {
    $index = 0
    $results = foreach ($item in $queue) {
        $index++
        Write-Progress -Activity 'Downloading images' `
            -Status "$index of $($queue.Count): $($item.Filename)" `
            -PercentComplete (100 * $index / $queue.Count)
        & $worker $item $FallbackHost $Retry
    }
    Write-Progress -Activity 'Downloading images' -Completed
}

$stopwatch.Stop()

# --- Report ----------------------------------------------------------------

$failures = @($results | Where-Object { -not $_.Ok })
$downloaded = @($results | Where-Object { $_.Ok }).Count

if ($failures.Count -gt 0) {
    $failures | ForEach-Object {
        [pscustomobject]@{
            url      = $_.Item.Url
            bundle   = $_.Item.Bundle
            filename = $_.Item.Filename
            error    = $_.Error
        }
    } | Export-Csv -LiteralPath $FailureLog -Delimiter "`t" -NoTypeInformation
}
elseif (Test-Path -LiteralPath $FailureLog) {
    Remove-Item -LiteralPath $FailureLog -Force
}

Write-Host ''
Write-Host ("downloaded={0} skipped={1} failed={2} in {3:n1}s" -f `
    $downloaded, $skipped, $failures.Count, $stopwatch.Elapsed.TotalSeconds)

if ($failures.Count -gt 0) {
    Write-Warning "$($failures.Count) image(s) did not come down. See $FailureLog."
    Write-Host 'Retry just those with:  .\download-images.ps1 -Manifest image-failures.tsv'
}

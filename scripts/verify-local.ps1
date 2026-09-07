<#
.SYNOPSIS
    Verify the SupportPilot local environment: checks V-01 through V-16.

.DESCRIPTION
    Thin wrapper around scripts/verify_local.py.

    The logic lives in Python rather than PowerShell for one practical reason: Windows PowerShell
    treats any output a native executable writes to stderr as a terminating error, and docker writes
    ordinary progress there. A verification script that reports a false failure because docker
    printed "Container Started" is worse than useless.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

& python (Join-Path $PSScriptRoot 'verify_local.py')
exit $LASTEXITCODE

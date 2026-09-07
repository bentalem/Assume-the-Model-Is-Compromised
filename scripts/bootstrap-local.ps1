<#
.SYNOPSIS
    Bring up the SupportPilot local environment from a clean machine.

.DESCRIPTION
    Thin wrapper around scripts/bootstrap_local.py.

    The logic lives in Python because Windows PowerShell treats anything a native executable writes
    to stderr as a terminating error, and docker writes ordinary progress there — so a PowerShell
    implementation aborts on a successful build.

.PARAMETER WithOnyx
    Also start Onyx (see docs/decisions/0002-onyx-in-the-local-environment.md).

.PARAMETER Rebuild
    Rebuild images without the layer cache.

.PARAMETER Reset
    Destroy volumes first. The database is rebuilt from migrations and seeds.
#>
[CmdletBinding()]
param(
    [switch]$WithOnyx,
    [switch]$Rebuild,
    [switch]$Reset
)

$ErrorActionPreference = 'Stop'

$arguments = @((Join-Path $PSScriptRoot 'bootstrap_local.py'))
if ($WithOnyx) { $arguments += '--with-onyx' }
if ($Rebuild)  { $arguments += '--rebuild' }
if ($Reset)    { $arguments += '--reset' }

& python @arguments
exit $LASTEXITCODE

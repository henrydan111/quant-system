[CmdletBinding()]
param(
    [switch]$PrintPath,
    [switch]$Quiet,
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Command = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$repoRgDir = Join-Path $repoRoot ".codex\tools\bin"
$repoRgPath = Join-Path $repoRgDir "rg.exe"
$commandList = @($Command | Where-Object { $null -ne $_ })

function Get-PackagedRipgrepPath {
    $commands = @(Get-Command rg -All -ErrorAction SilentlyContinue)
    foreach ($command in $commands) {
        $path = $command.Path
        if (
            $path -and
            $path -ine $repoRgPath -and
            $path -like "*\OpenAI.Codex_*\app\resources\rg.exe"
        ) {
            return $path
        }
    }

    return $null
}

function Ensure-RepoRipgrep {
    if (Test-Path -LiteralPath $repoRgPath) {
        return $repoRgPath
    }

    $sourcePath = Get-PackagedRipgrepPath
    if (-not $sourcePath) {
        throw "Could not locate a packaged Codex ripgrep binary to copy into the repo."
    }

    New-Item -ItemType Directory -Force -Path $repoRgDir | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $repoRgPath -Force
    return $repoRgPath
}

Ensure-RepoRipgrep | Out-Null

$pathEntries = @($env:PATH -split ';' | Where-Object { $_ })
if ($pathEntries -notcontains $repoRgDir) {
    $env:PATH = "$repoRgDir;$env:PATH"
}

$resolvedRipgrepPath = (Get-Command rg -ErrorAction Stop).Path

if (-not $Quiet -and ($PrintPath -or $commandList.Count -eq 0)) {
    Write-Output $resolvedRipgrepPath
}

if ($commandList.Count -gt 0) {
    $commandName = $commandList[0]
    $commandArgs = @()
    if ($commandList.Count -gt 1) {
        $commandArgs = $commandList[1..($commandList.Count - 1)]
    }

    & $commandName @commandArgs
    if ($null -ne $LASTEXITCODE) {
        exit $LASTEXITCODE
    }
}

[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$CodexArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$useRepoRipgrepScript = Join-Path $PSScriptRoot "use_repo_ripgrep.ps1"

. $useRepoRipgrepScript -Quiet

$codexCommand = (Get-Command codex -ErrorAction Stop).Source
$arguments = @()

if ($CodexArgs -notcontains "-C" -and $CodexArgs -notcontains "--cd") {
    $arguments += @("-C", $repoRoot)
}

$arguments += $CodexArgs

& $codexCommand @arguments
if ($null -ne $LASTEXITCODE) {
    exit $LASTEXITCODE
}

param(
    [switch]$All,
    [switch]$Changed,
    [string[]]$Files
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $repoRoot "tools\template_tests\run.py"

$argsList = @()
if ($All) {
    $argsList += "--all"
} elseif ($Changed -or -not $Files) {
    $argsList += "--changed"
}
if ($Files) {
    $argsList += "--files"
    $argsList += $Files
}

python $scriptPath @argsList
exit $LASTEXITCODE

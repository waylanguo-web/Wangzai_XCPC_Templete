param(
    [switch]$NoPdf,
    [string]$OutputDir = "dist\book",
    [string]$Browser = "",
    [int]$TocDepth = 2,
    [string]$Title = "Wangzai_XCPC_Templete"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $repoRoot "tools\book_builder\build.py"

$argsList = @(
    "--output-dir", (Join-Path $repoRoot $OutputDir),
    "--toc-depth", $TocDepth,
    "--title", $Title
)

if (-not $NoPdf) {
    $argsList += "--pdf"
}
if ($Browser) {
    $argsList += "--browser"
    $argsList += $Browser
}

python $scriptPath @argsList
exit $LASTEXITCODE

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$hookSource = Join-Path $repoRoot ".githooks\pre-push"
$hookTargetDir = Join-Path $repoRoot ".git\hooks"
$hookTarget = Join-Path $hookTargetDir "pre-push"

if (-not (Test-Path $hookTargetDir)) {
    throw "未找到 .git/hooks 目录，请确认当前目录是 Git 仓库。"
}

Copy-Item -Force $hookSource $hookTarget
Write-Host "已安装 pre-push hook：$hookTarget"
Write-Host "以后执行 git push 前，会自动运行模板测试。"

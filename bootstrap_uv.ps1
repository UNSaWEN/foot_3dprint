$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path $PSScriptRoot
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$venvPath = Join-Path $projectRoot ".venv"

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
    throw "未找到 uv。请先安装 uv，或把 uv.exe 加入 PATH 后重新运行 bootstrap_uv.ps1。"
}

Write-Host "[bootstrap] using uv at $($uvCommand.Source)"

& $uvCommand.Source python install 3.12
& $uvCommand.Source venv $venvPath --python 3.12

$venvPython = Join-Path $venvPath "Scripts\\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "虚拟环境创建失败：$venvPython 不存在。"
}

& $uvCommand.Source pip install --python $venvPython -r $requirementsPath

Write-Host "[bootstrap] environment ready"
Write-Host "[bootstrap] python: $venvPython"
Write-Host "[bootstrap] next: & `"$venvPython`" scripts\\run_pipeline.py"

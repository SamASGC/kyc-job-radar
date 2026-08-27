$ErrorActionPreference = "Stop"

Write-Host "== KYC Job Radar: setup Windows ==" -ForegroundColor Cyan

$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} else {
    throw "Python 3.11+ no está instalado o no está en PATH. Instálalo desde python.org y vuelve a ejecutar este script."
}

if (!(Test-Path ".venv")) {
    & $python -m venv .venv
}

$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar pip." }

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }

& $venvPython -m compileall -q job_radar radar.py
if ($LASTEXITCODE -ne 0) { throw "Falló la compilación de comprobación." }

& $venvPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Los tests han fallado." }

Write-Host "" 
Write-Host "Primera búsqueda. Puede tardar unos minutos..." -ForegroundColor Yellow
& $venvPython radar.py scan
if ($LASTEXITCODE -ne 0) { throw "La primera búsqueda ha fallado." }

& $venvPython radar.py health
if ($LASTEXITCODE -ne 0) { throw "El health check ha fallado." }

$dashboard = Join-Path $PWD "public\index.html"
Write-Host "" 
Write-Host "Dashboard: $dashboard" -ForegroundColor Green
Start-Process $dashboard

@echo off
if not exist .venv\Scripts\python.exe (
  echo Ejecuta primero setup_windows.ps1
  exit /b 1
)
echo.
echo ===== KYC JOB RADAR =====
echo Iniciando escaneo. Veras progreso mientras trabaja.
echo.
.venv\Scripts\python.exe -u radar.py scan
if errorlevel 1 (
  echo.
  echo ERROR: el escaneo termino con fallo.
  exit /b 1
)
echo.
echo ===== HEALTH =====
.venv\Scripts\python.exe -u radar.py health
echo.
echo Abriendo dashboard...
start "" public\index.html

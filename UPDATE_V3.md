# Actualización v1.1 / v3

Esta versión amplía cobertura sin borrar el histórico `seen` del usuario si se extrae encima de una instalación existente. El ZIP de actualización no contiene `data/state.json` ni `data/health.json`.

En Windows, con el ZIP en el Escritorio:

```powershell
cd "$HOME\Desktop"
Expand-Archive .\kyc_job_radar_v3.zip -DestinationPath . -Force
cd .\kyc_job_radar
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

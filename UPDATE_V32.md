# v3.2 hotfix

- El escaneo ya no parece congelado: muestra progreso mientras termina empresas.
- `run_once_windows.bat` usa Python sin buffer (`-u`) y muestra fases.
- Añadido timeout de seguridad de 240 s por empresa, además de los timeouts HTTP.
- Si el scan falla, el BAT se detiene y no abre un dashboard engañoso.

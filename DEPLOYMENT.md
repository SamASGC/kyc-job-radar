# Despliegue: cada hora y coste máximo 0

## Opción A — repositorio público (la forma más simple de garantizar 0 €)

GitHub indica que los runners estándar de GitHub Actions son gratuitos en repositorios públicos. Este proyecto no incluye PII ni el CV original.

### 1. Crea y sube el repositorio

Si tienes GitHub CLI (`gh`):

```powershell
gh auth login
gh repo create kyc-job-radar --public --source=. --remote=origin --push
```

Sin GitHub CLI: crea en github.com un repositorio vacío llamado `kyc-job-radar` y ejecuta:

```powershell
git init
git add .
git commit -m "Initial KYC job radar"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/kyc-job-radar.git
git push -u origin main
```

### 2. Comprueba la automatización

En GitHub: `Actions` → `Hourly KYC job radar` → `Run workflow`. Después funcionará cada hora por cron.

## Opción B — repositorio privado, también 0 € con hard stop

GitHub Free incluye 2.000 minutos/mes para Actions en repositorios privados. 24 ejecuciones/día son unas 720–744 ejecuciones/mes, por lo que este proyecto está diseñado para hacer I/O concurrente, no usar navegador y terminar rápido.

Para que **nunca exista cobro** aunque consumas toda la cuota:

1. La garantía más simple es no tener un método de pago válido asociado a GitHub; la documentación de GitHub indica que, al agotarse la cuota incluida, el uso se bloquea.
2. Si necesitas mantener un método de pago, crea antes un presupuesto para **GitHub Actions** y activa `Stop usage when budget limit is reached`, con el límite pagado más bajo que permita tu cuenta (0 si la UI lo admite). No uses solo alertas: el hard stop es la parte importante.

Para crear el repo privado con `gh`:

```powershell
gh auth login
gh repo create kyc-job-radar --private --source=. --remote=origin --push
```

## Publicar el HTML con Cloudflare Pages

Cloudflare Pages permite servir assets estáticos gratis. Conecta el repositorio desde `Workers & Pages` → `Create` → `Pages` → `Connect to Git`.

Usa:

```text
Framework preset: None
Build command: (vacío)
Build output directory: public
Root directory: /
```

Pages Free admite 500 builds/mes. El workflow **no hace commit en escaneos sin cambios**, así que no debería provocar 744 builds mensuales: solo hay despliegue cuando cambia el conjunto visible/deduplicado o la detección persistida.

Si necesitas que el dashboard no sea público, añade Cloudflare Access después de confirmar que todo funciona. El radar no depende de Access para escanear.

## Primera ejecución recomendada antes de subir

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Después revisa `public/index.html` y `data/health.json`. Así el primer commit ya lleva un dashboard inicial y la caché de detección de ATS.

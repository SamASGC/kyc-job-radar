# KYC / KYB / AML Job Radar v1.2

Radar personal de ofertas orientado a KYC/KYB/AML/FinCrime/Payments. Busca en career pages oficiales y ATS públicos, añade agregadores con feed/API pública, puntúa cada vacante contra un perfil profesional sin datos personales, deduplica de forma persistente y genera un dashboard HTML interactivo.

## Qué incluye

- **173 targets de empresas**: las **81 entradas del PDF original**, **83 targets de ampliación web** y **9 targets adicionales** en `config/extra_companies.json` para ampliar Malta, Estonia y Chequia.
- Nuevos targets de expansión geográfica: **Ballinger Group, Corpay, Moneybase, Shift4, amnis, ESTO Group, Saxo, OKX y Payfuture**.
- ATS soportados: Greenhouse, Lever (global/EU), Ashby, SmartRecruiters, Workable, Personio, Workday, Recruitee y Breezy; además de fallback sobre career pages oficiales.
- **Personio reforzado**: intenta XML y, si la empresa no lo ha habilitado, recorre la career page pública y las páginas de las vacantes. Esto cubre casos como Peratera.
- Fallback de career pages mejorado: en enlaces claramente KYC/AML/Compliance/Risk intenta leer la página de detalle y su `JobPosting` JSON-LD para recuperar descripción, ubicación y fecha.
- Agregadores automatizados: **Jobicy, Remotive, Arbeitnow, Remote OK, Himalayas y We Work Remotely**.
- Jobicy hace búsqueda amplia + queries específicas KYC/KYB/AML/Compliance/Financial Crime/TM/Sanctions/Onboarding; Arbeitnow recorre más páginas que v1.0.
- El radar sigue ejecutándose cada hora, pero Remotive/Himalayas se consultan con menor frecuencia para respetar su cadencia recomendada.
- Dashboard: `Rol | Empresa | Fintech/Banca/Payments | Encaje | Skills que comprarías | Lugar | Salario | Fecha | Link | Acción`.
- Ocultar/restaurar ofertas en el navegador mediante `localStorage`.
- Registro `seen` persistente: una oferta ya presentada no vuelve a aparecer aunque desaparezca y reaparezca.
- Preferencia fuerte por ofertas de **0–7 días**; se admiten hasta **14 días** para no perder oportunidades buenas.

## Geografía v1.2

- **Presencial o híbrido:** España (incluida Barcelona), Luxemburgo, Suiza, Estonia, Chequia y Malta.
- **Remoto:** cualquier país del mundo, incluido remoto limitado a un país concreto, siempre sujeto al resto del scoring y requisitos del puesto.

## Privacidad

El proyecto **no contiene el CV original, teléfono, email ni nombre**. `config/profile.yaml` contiene únicamente un perfil de scoring resumido.

## Arranque rápido en Windows

En PowerShell, dentro de esta carpeta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

El script reutiliza `.venv` si ya existe, instala/actualiza dependencias, ejecuta tests, hace una búsqueda y abre `public/index.html`.

Búsqueda manual posterior:

```powershell
.\run_once_windows.bat
```

O:

```powershell
.\.venv\Scripts\python.exe radar.py scan
.\.venv\Scripts\python.exe radar.py health
```

## Automatización horaria

El workflow `.github/workflows/hourly.yml` ejecuta el radar en `:17` y `:47`; Cloudflare puede lanzar `workflow_dispatch` como respaldo cuando GitHub se retrasa. Las careers/ATS se revisan en cada pasada; algunos agregadores tienen una cadencia interna más baja según sus propias recomendaciones.

Consulta `DEPLOYMENT.md` para el despliegue.

## Limitaciones intencionadas

No hace login ni automatiza LinkedIn/Indeed/EURES. No intenta saltarse CAPTCHA, paywalls ni controles anti-bot. Una career page puede cambiar de ATS o HTML; `radar.py health` identifica las fuentes que requieren ajuste.

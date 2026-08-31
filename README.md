# KYC / KYB / AML Job Radar v1.3

Radar personal de ofertas orientado a KYC/KYB/AML/FinCrime/Payments. Combina targets directos, career pages/ATS oficiales y un modo **open-universe** que busca puestos relevantes fuera de la lista fija de empresas. Puntúa cada vacante contra un perfil profesional sin datos personales, deduplica de forma persistente y genera un dashboard HTML interactivo.

## Qué incluye

- **174 targets directos de empresas**: las **81 entradas del PDF original**, **83 targets de ampliación web** y **10 targets adicionales** en `config/extra_companies.json`.
- Entre las ampliaciones recientes: **Ballinger Group, Corpay, Moneybase, Shift4, amnis, ESTO Group, Saxo, OKX, Payfuture y American Express**.
- **Open-universe discovery**: no depende sólo de esas 174 empresas. Consulta una fuente employer-direct con millones de vacantes y más de 200k empleadores, filtrando específicamente KYC/KYB/AML/CDD/EDD/FinCrime/Compliance/Sanctions/TM/Screening/Onboarding y frases de descripción como SoF, SoW, beneficial ownership, adverse media y PEP screening.
- El open-universe se divide según la geografía real del perfil: **remoto mundial** + **presencial/híbrido ES/LU/CH/EE/CZ/MT**.
- Fuente adicional **Remote Landers**, con vacantes remotas enlazadas directamente al ATS del empleador.
- ATS soportados: Greenhouse, Lever (global/EU), Ashby, SmartRecruiters, Workable, Personio, Workday, Recruitee, Breezy y **Oracle HCM Candidate Experience**; además de fallback sobre career pages oficiales.
- **Personio reforzado**: intenta XML y, si la empresa no lo ha habilitado, recorre la career page pública y las páginas de las vacantes.
- Fallback de career pages: en enlaces claramente KYC/AML/Compliance/Risk intenta leer la página de detalle y su `JobPosting` JSON-LD para recuperar descripción, ubicación y fecha.
- Agregadores automatizados adicionales: **Jobicy, Remotive, Arbeitnow, Remote OK, Himalayas y We Work Remotely**.
- Dashboard: `Rol | Empresa | Fintech/Banca/Payments | Encaje | Skills que comprarías | Lugar | Salario | Fecha | Link | Acción`.
- Ocultar/restaurar ofertas en el navegador mediante `localStorage`.
- Registro `seen` persistente: una oferta ya presentada no vuelve a aparecer aunque desaparezca y reaparezca.
- Preferencia fuerte por ofertas de **0–7 días**; se admiten hasta **14 días** para no perder oportunidades buenas.
- El scoring distingue entre **skills transferibles** y **gaps obligatorios**. SoF/SoW, Transaction Monitoring, AML investigations, SAR/STR drafting, regulatory reporting y sanctions investigations no se atribuyen como experiencia hands-on cuando no corresponde.

## Geografía v1.3

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

## Automatización

El workflow `.github/workflows/hourly.yml` ejecuta el radar en `:17` y `:47`; Cloudflare puede lanzar `workflow_dispatch` como respaldo cuando GitHub se retrasa. Las careers/ATS directas se revisan en cada pasada; algunos feeds respetan una cadencia interna más baja.

Consulta `DEPLOYMENT.md` para el despliegue.

## Limitaciones intencionadas

No hace login ni automatiza LinkedIn/Indeed/EURES. No intenta saltarse CAPTCHA, paywalls ni controles anti-bot. Ningún sistema puede garantizar literalmente el 100% de todas las vacantes mundiales: una empresa puede ocultar su career site, bloquear acceso automatizado o usar un ATS no soportado. El diseño v1.3 reduce mucho el problema de la lista cerrada al añadir descubrimiento sobre un universo de empleadores muy superior a los targets manuales.

# KYC / KYB / AML Job Radar v1.1

Radar personal de ofertas orientado a KYC/KYB/AML/FinCrime/Payments. Busca en career pages oficiales y ATS públicos, añade agregadores con feed/API pública, puntúa cada vacante contra un perfil profesional sin datos personales, deduplica de forma persistente y genera un dashboard HTML interactivo.

## Qué incluye

- **164 targets de empresas** en `config/companies.json`: las **81 entradas del PDF original** más **83 targets de ampliación web**.
- Nuevos targets v1.1 de alto valor: **Peratera, BVNK, Nium, Unlimit, PayDo, Copper.co, Upvest, Griffin, payabl., Monavate, Railsr, PaySet, BCB Group, Form3, Fireblocks y Chainalysis**.
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

## Geografía v1.1

- **Presencial o híbrido:** solo **España, Luxemburgo o Suiza**.
- **Remoto:** cualquier país europeo, y ofertas explícitamente `Europe`, `EU`, `EMEA`, `Worldwide` o `Global` siempre que no indiquen una restricción incompatible.
- Un remoto explícitamente limitado a India/Canadá/EE. UU./Sudáfrica/etc. se descarta.

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

El workflow `.github/workflows/hourly.yml` ejecuta el radar cada hora en el minuto `:17`. Las careers/ATS se revisan cada hora; algunos agregadores tienen una cadencia interna más baja según sus propias recomendaciones.

Consulta `DEPLOYMENT.md` para el despliegue.

## Limitaciones intencionadas

No hace login ni automatiza LinkedIn/Indeed/EURES. No intenta saltarse CAPTCHA, paywalls ni controles anti-bot. Una career page puede cambiar de ATS o HTML; `radar.py health` identifica las fuentes que requieren ajuste.

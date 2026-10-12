# KYC / KYB / AML Job Radar

## Radar v2 — strict quality (experimental branch; NOT yet deployed)

The existing **main** branch and production dashboard remain unchanged until
this branch has passed both automated tests and a full live-data smoke scan.

### Four non-negotiable admission rules

1. **Original publication within 96 hours**: an unknown date, an ATS
   `updated_at` timestamp, or an aggregator's repost/first-seen time does not
   count. Greenhouse's `updated_at` has deliberately been replaced with
   `first_published` when the feed actually provides it. If ATS feeds omit the date, v2 checks for the exact job's
   schema.org `JobPosting.datePosted` on the official application page.
   Records without any reliable original date are withheld; the oldest
   credible date wins when sources conflict. Lever uses `createdAt` instead of no date.
2. **The vacancy is genuinely open**: it must occur in a live official ATS feed
   and the job-specific application page must be reachable and show a form or
   recognizable Apply action. 403/404/errors/blocked pages are withheld,
   *not* asserted open. This is an automated check, **not** an end-to-end
   test of submitting a real application.
3. **Never repeat a presented requisition**: existing persistent
   `data/state.json → seen` entries survive migration. New results compare
   company/title and official job ID with historical entries even when the URL
   or location shifts. Separate verified job IDs permit genuinely distinct
   requisitions. Conservative dedup may occasionally suppress a new role.
4. **Location**: priority 1 is genuinely 100% remote from **Spain / Canary
   Islands**. A bare Europe/EMEA/Worldwide label is not proof of Spain hiring.
   Relocation-only hybrid/onsite is eligible in Spain **outside Barcelona**,
   Estonia, Lithuania, Luxembourg, and Switzerland.

Older persisted dashboard rows are removed on the first v2 scan, *without*
clearing the seen ledger. The HTML shows original dates and timestamps of the
application-page verification. No matching vacancies = an empty report, not
filler.

### What the numbers mean

- The v1.3 repository listed **174 direct employer targets**. This v2 branch adds **17 verified official employer career pages/ATS boards**, bringing the configured target list to **191** (not 191 fully successful feeds). That covers **38 of the 39 named fintech watchlist companies** directly; Due is currently discoverable on the Speedinvest portfolio board but does not yet have a separately verified direct company ATS in this repository.
- The open-universe API searches a potentially huge employer dataset but does
  **not** mean every employer has been checked at its official careers page.
  **New v2 ATS bridge:** discover ATS URLs embedded in aggregator job links,
  independently re-fetch those employers' official ATS feeds (up to 40 new
  boards/hour), and persist successfully reached boards for up to 200
  recurring checks/hour. Aggregator listings are discovery hints only,
  never treated as verified-open job postings.
- The European Commission fintech map presently lists **4,291 firms**. It is
  a **discovery directory**, not 4,291 individually verified job feeds.
- The v2 importer/rotation can stage thousands of firms from a permitted CSV
  export. Only rows with usable HTTPS websites enter *candidate* rotation.
  Only firms where the radar discovers a working ATS become recurring ATS
  targets; actual ATS jobs must still pass all four gates.
- No CSV export is bundled or claimed to have been imported in this branch.

Import a permitted CSV with company/website/sector/country columns:

```bash
python scripts/import_fintech_directory.py ./fintech_directory.csv
```

This writes `data/fintech_directory.json`; commit it to the v2 branch only
after reviewing provenance and duplicates. By default, the scanner tries
**50 new directory companies per hour**, plus up to **200 previously discovered
ATS targets per hour**. It rotates batches rather than contacting 4,291
sites at once. Without an imported directory, this new layer is dormant.
The existing direct ATS/company sources are still checked normally.

Quality tests (the pull-request workflow only runs tests and never deploys):

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The dashboard's existing `seen` state is JSON persisted in the repository.
SQLite or PostgreSQL may be an appropriate later step for concurrency and
cross-service alerts, but **a SQL database is not needed to preserve the
existing 278 historical seen records**.

---

## Legacy v1.3 reference (main is unchanged)


Radar personal de ofertas orientado a KYC/KYB/AML/FinCrime/Payments. Combina targets directos, career pages/ATS oficiales y un modo **open-universe** que busca puestos relevantes fuera de la lista fija de empresas. Puntúa cada vacante contra un perfil profesional sin datos personales, deduplica de forma persistente y genera un dashboard HTML interactivo.

## Qué incluye

- **174 targets directos de empresas**: las **81 entradas del PDF original**, **83 targets de ampliación web** y **10 targets adicionales** en `config/extra_companies.json`.
- Entre las ampliaciones recientes: **Ballinger Group, Corpay, Moneybase, Shift4, amnis, ESTO Group, Saxo, OKX, Payfuture y American Express**.
- **Open-universe discovery**: no depende sólo de esas 174 empresas. Consulta una fuente employer-direct con millones de vacantes y más de 200k empleadores, buscando dentro de las JDs KYC/KYB/AML/CDD/EDD/FinCrime/Compliance/Sanctions/TM/Screening y señales como SoF, SoW, beneficial ownership, adverse media y PEP screening.
- El open-universe aplica geografía desde origen: **remoto sólo con país europeo** + **presencial/híbrido ES/LU/CH/EE/CZ/MT**.
- Fuente adicional **Remote Landers**, con vacantes remotas enlazadas directamente al ATS del empleador; el filtro central descarta las que no tengan elegibilidad europea verificable.
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
- **Remoto:** Europa. Se admiten vacantes marcadas Europe/EMEA/global/worldwide cuando permiten trabajar desde Europa, y vacantes country-only de países europeos. Se rechazan US, México, Canadá, LATAM y cualquier otro país no europeo. Un simple `Remote` sin región verificable se descarta.

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

No hace login ni automatiza LinkedIn/Indeed/EURES. No intenta saltarse CAPTCHA, paywalls ni controles anti-bot. Ningún sistema puede garantizar literalmente el 100% de todas las vacantes: una empresa puede ocultar su career site, bloquear acceso automatizado o usar un ATS no soportado. El diseño v1.3 reduce mucho el problema de la lista cerrada al añadir descubrimiento sobre un universo de empleadores muy superior a los targets manuales.

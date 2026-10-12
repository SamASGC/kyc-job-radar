# KYC / KYB / AML Job Radar

## Radar v2 — production (deployed 12 October 2026)

This version is merged into **main** after unit tests and isolated live-data smoke scans. GitHub Actions publishes the verified vacancy dashboard, optional review page and source-health status.

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

### Separate verified alerts, pending review and heartbeat

- `public/index.html` and `public/feed.xml` contain **only** opportunities
  that pass all strict checks. The default HTML order is 100% remote from Spain
  first, then hybrid, then on-site, with best fit first within each mode.
- `public/review.html` is a separate manual-review diagnostics page for
  potentially relevant, geographically verified employer listings with
  ambiguous original dates or an inaccessible/unrecognized apply action.
  It explicitly warns that these are **not confirmed open, recent vacancies**,
  excludes old/closed ads, and never sends RSS entries or notifications.
- `public/status.html` / `public/status.json` always show the last successful
  scan and the count of reachable, unavailable and disabled sources.
- The link-normalizer preserves **job-identifying query parameters** such as
  `gh_jid` while removing tracking, preventing accidental loss of application
  pages.
- A first-party job-specific employer career page can be eligible even without
  a supported ATS, but must expose a defensible original date and visible
  apply/form evidence. A merely indexed/generic careers home page does not count.

### Radar v2.2 — hourly evidence-based website enrichment (12 October 2026)

The existing hourly direct-employer + licensed-register sweeps continue unchanged.
This branch adds **five verified employer ATS boards** for **Finary** (Ashby),
**Solidgate** (Ashby), **Smartbroker AG** (Personio), **Strike** (Greenhouse)
and **BitGo** (Greenhouse), and upgrades **Scalable Capital** to its working
SmartRecruiters board. Direct employer target coverage grows from **203 to 208**.
It is still not 208 proven job-relevant, continuously reachable feeds.

A separate scheduled enrichment job at **:05 UTC every hour** examines up to
**20 distinct licensed financial-company legal names** whose regulator
register entry has no website. The website can be activated for ATS discovery
ONLY when all independent conditions hold:

- Wikidata's public entity search supplies an exact normalized legal name or
  alias, country P17/P495 matching the register country code, and an explicit
  P856 official website; multiple conflicting matches are held back.
- That HTTPS company homepage responds and displays a matching company brand
  in the title or identifiable company branding. External redirects, unsafe
  URLs and insufficient evidence are withheld.
- Companies already in the direct-employer watchlist and websites already in
  the attributed registry are skipped. The original CC BY 4.0 register is never
  edited. A separate checked ledger and verified website overlay are committed
  to main for reuse by the two existing career scans.

**Reality check:** a live pilot of 60 previously unmonitored legal entities
found **zero** strict matches. A targeted Qonto (already directly monitored)
check **did** confirm a correct site. This is a conservative supplementary
enrichment source, NOT proof that the remaining ~2,255 entities will all be
discoverable. Source outages are saved as a status, not falsely counted as
successful discoveries or spammy hourly workflow failures.

**Investor portfolio safety:** older auto-discovery could pick up other firms'
ATS boards on Due's Speedinvest page (e.g. Bitpanda, Dialpad). Unrelated boards
are now filtered by company identity; investor-hosted listings are aggregator
leads only, not verified official company job listings. The historical
notified-requisition ledger remains intact, and alerts still need original
posting age <=96h and active application confirmation.

### Radar v2.1 — hourly source coverage (12 October 2026)

- **203 directly configured financial-service/fintech employers**, including 11 additional
  verified public ATS boards (Binance, Yuno, FYST, Affirm, Glia, bunch, Invopop,
  Checker, Hopper, OnHires and Pragmatike). Existing Paymentology, SwissBorg,
  MoonPay and WeTravel entries now fetch their public ATS directly.
- **322 additional company URLs** in the attributed 2,593-company register
  after removing the overlap with the 203 configured employers.
  Two independent scheduled sweeps at **:17 and :47 UTC** check 180 URLs
  per run. The half-hour rotation makes their combined union include all
  322 **once per scheduled hour**, rather than repeating the same 50 websites
  twice within an hour. Actual scheduling is subject to GitHub Actions delays.
- That is **525 distinct target companies with a usable web/ATS entry**, NOT
  525 functioning independent ATS feeds. Others in the licensed register
  (**2,255 with no usable URL**) cannot be claimed as monitored job sources.
- Company homepage discovery now follows **at most one** high-confidence
  same-company careers link or recognized public ATS link. No general-purpose
  web crawling; final alerts still require the exact original date ≤96h and
  an open official application page.
- [Isolated 12 Oct 2026 benchmark](https://github.com/SamASGC/kyc-job-radar/actions/runs/38302046202):
  383 employer targets attempted in one run; 392 source checks including feeds,
  of which 345 succeeded, with 242 yielding jobs. Collected 6,568 raw postings;
  after strict filters, zero *new* eligible notifications. The end-to-end scan
  finished in approximately 2m10s and generated verified dashboard, manual
  review, status and RSS. A successful technical scan is not a guarantee
  of exhaustive coverage or real-time provider posting dates.

### What the numbers mean

- The v1.3 repository listed **174 direct employer targets**. This v2 branch adds **17 additional employer career pages/ATS boards** and **Due's investor-maintained Speedinvest page**, bringing the configured employer target list to **192** (not 192 independently verified functional ATS feeds). All **39 of 39** named fintech watchlist companies have an explicit entry, but Due's Getro/Speedinvest site has no unauthenticated official ATS API and Ondato links to LinkedIn only. Those two require alternative verification rather than claiming full ATS monitoring.
- The external open-universe API has a potentially huge employer dataset, but
  **is presently disabled without `JOB_OPPORTUNITIES_API_KEY`** (verified 401).
  It does **not** mean every employer has been checked at its careers page.
  **New v2 ATS bridge:** discover ATS URLs embedded in aggregator job links,
  independently re-fetch those employers' official ATS feeds (up to 40 new
  boards/hour), and persist successfully reached boards for up to 200
  recurring checks/hour. Aggregator listings are discovery hints only,
  never treated as verified-open job postings.
- The European Commission fintech map presently lists **4,291 firms**. It is
  a **discovery directory**, not 4,291 individually verified job feeds.
- The v2 importer/rotation now stages thousands of attributed firm records. Only rows with usable HTTPS websites enter *candidate* rotation.
  Only firms where the radar discovers a working ATS become recurring ATS
  targets; actual ATS jobs must still pass all four gates.
- **Licensed directory imported on 12 October 2026**: 2,654 source rows, 2,593 unique firm-country entries, 338 with a website in the supplied register. The included `data/fintech_directory.json` file is an attributed CC BY 4.0 snapshot from [Fintechnologica](https://fintechnologica.com/data), compiled from regulatory sources. **Only 338 entries have usable website fields**; the other 2,255 names are for future enrichment, not job feeds. After excluding companies already configured directly, 322 website-bearing entries are available for rotation.

Import a permitted CSV with company/website/sector/country columns:

```bash
python scripts/import_fintech_directory.py ./fintech_directory.csv
```

This writes `data/fintech_directory.json`; validate provenance, update cadence and duplicates before adding a new third-party dataset. By default, the scanner tries
**50 new directory companies per hour**, plus up to **200 previously discovered
ATS targets per hour**. It rotates batches rather than contacting 4,291
sites at once. The attributed Fintechnologica directory is already included in main.
The existing direct ATS/company sources are still checked normally.

The original EU Digital Finance Platform map lists 4,291 fintech firms, but it is separate crowdsourced/Dealroom-derived data; **the 2,593 imported firms come from Fintechnologica, not a claimed export of the EU map**. A company without a website or compatible ATS does **not** count as an active source. The scanner also discovers ATS boards from eligible public aggregator apply links, verifies the ATS independently and stores successful boards in the persistent state.

### Additional discovery from licensed employer domains

The employer-search provider advertises a **company_domain** filter
([parameter documentation](https://jobopportunitiesapi.org/docs/api/parameters)).
**IMPORTANT (verified 12 October 2026): listing endpoints `/public/jobs`
and `/v1/jobs` now return HTTP 401 without an API key.** Therefore the
entire employer-search API, including the 80-domains/hour option, is
**automatically disabled in normal scans until** a user obtains a key and
stores it securely as the GitHub Actions repository secret
`JOB_OPPORTUNITIES_API_KEY`. The authenticated code uses `/v1/jobs`
and `Authorization`, but paid/free-plan limits and the domain filter
must be validated with the user's actual key before declaring them active.
This integration is NOT currently one of the operational discovery sources.
When enabled, results are discovery leads only and must still be confirmed
at the original ATS.

Country discovery for hybrid/on-site now includes **Lithuania** and does
**not** treat Malta/Czechia as eligible relocation countries.

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

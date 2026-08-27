# Fuentes y criterio de automatización — v1.1

## Fuentes estructuradas

El radar usa endpoints públicos de empleo cuando están disponibles: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Personio, Workday, Recruitee y Breezy.

- **Greenhouse**: Job Board API pública.
- **Lever**: Postings API pública.
- **Ashby**: Public Job Postings API, incluyendo compensation cuando se publica.
- **SmartRecruiters**: postings públicos de compañía.
- **Personio**: XML público cuando está habilitado; si no, fallback a la career page pública y páginas de detalle.
- **Workday**: endpoint público usado por el career site cuando puede detectarse.
- **Career pages custom**: extracción prudente de enlaces y enriquecimiento de páginas claramente relevantes mediante HTML/JSON-LD.

## Agregadores automatizados

- **Jobicy** — API pública. Búsqueda Europe general + queries específicas KYC/KYB/AML/Compliance/Financial Crime/Transaction Monitoring/Sanctions/Onboarding.
- **Arbeitnow** — API pública europea; v1.1 recorre hasta 10 páginas por scan.
- **We Work Remotely** — RSS público de Management & Finance, Customer Support y All Other.
- **Remote OK** — feed JSON público.
- **Remotive** — API pública; se consulta con menor frecuencia porque recomienda solo unas pocas peticiones diarias.
- **Himalayas** — API pública de remote jobs; se consulta diariamente porque su dataset público se refresca cada 24 h.

El dashboard muestra la fuente debajo del nombre de empresa y mantiene atribución visible para agregadores que la solicitan.

## Portales manuales / alertas

No se automatizan por login, términos o ausencia de una API pública estable apropiada:

- LinkedIn Jobs
- Indeed
- EURES
- Welcome to the Jungle
- eFinancialCareers

## Geografía

- Presencial/híbrido: España, Luxemburgo, Suiza.
- Remoto: Europa completa / EU / EMEA / Global, excluyendo restricciones explícitas incompatibles.

## Proveniencia de targets

`config/companies.json` mantiene `origin`:

- `PDF target list`: 81 targets originales.
- `Web expansion 2026-08-27`: 67 targets de la primera ampliación.
- `Web expansion v3 2026-08-27`: 16 targets adicionales incorporados al aumentar el caudal.

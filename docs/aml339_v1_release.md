# AML339 V1 – production status and 100 additional regulated-company leads

## Definitions
- 97 sources are configured for live employer audits (including 2 new, independently canary-verified official ATS boards from the 100-company research queue); the current published summary still reports only 34, until a larger production scan is successfully deployed.
- 100 additional legal-entity leads were saved from a secondary Licensed EMIs dataset (CC BY 4.0), across 15 European countries, on top of the earlier 50-entity discovery round.
- At initial discovery, all 100 leads were unverified and had live_monitoring_enabled=false. Subsequently, 2 separately audited official sources (Paynovate Breezy, PingPong official careers) were promoted to the LIVE manifest, without rewriting the original research snapshot. The other 98 are not operational. Neither source has a verified newly eligible vacancy in the initial canary.
- Original 339 source ZIP, existing 3 historical records, stable RSS role IDs and all user-private applicant exclusions remain unchanged.

## Important data distinction
- Regulator/company research is not the same as a live official jobs board.
- A licensed parent is not evidence its subsidiary has the same licence; a passport is not direct home-state authorisation.
- An indexed job URL does not prove the original listing is open or newly published.
- First audit of a new employer seeds a baseline. Only official job identities newly observed later and independently confirmed as relevant may generate eligible new-job notifications.

## V1 release gate
- Execute python3 scripts/aml339_v1_status.py for a truthful status report.
- Execute python3 scripts/aml339_v1_status.py --require-live to fail if the published V1 is not yet verified.
- The read-only workflow .github/workflows/aml339_v1_health.yml checks daily after the AML339 scan and records a status artifact.
- V1 status requires a fresh (under 36 h) published report, complete 18 mandatory sources, active true-novelty protection, and the current 97-source configuration represented in the live summary.

## GitHub Pages reliability
- A first deploy-pages failure can occur after artifact upload acknowledgement. The main radar, AML339 and recovery workflow now include a single deployment retry after a 35-second metadata-propagation window.
- The retry NEVER repeats HTTP employment scans, applies for jobs, rewrites prior alert history, or silently marks failure as success; if it too fails, the workflow fails.

## Official employer/ATS leads from the 100-company round
- Paynovate, Belgian EMI: official careers https://paynovate.breezy.hr/ . Not yet fully audited or in the live source count.
- UAB Monavate, Lithuanian EMI: official careers https://www.monavate.com/careers (currently no openings per their page). Not yet in the live source count.
- OUTPAYCE S.A., Spanish EMI: https://outpayce.com/en/company/careers redirects applicants to Amadeus Workday. Company-specific jobs not yet independently audited.
- BENKER UAB, Lithuanian EMI: official register https://www.lb.lt/en/sfi-financial-market-participants/benker-uab . ATS not yet verified.

## How sources graduate from research to production
1. Independently confirm current licence in the national supervisor/EBA register and match exact employer entity.
2. Verify official employer homepage, own careers board or employer-managed ATS, and current open job listing with pagination.
3. Audit every geographically plausible AML title's full duties, language/permit constraints, and actual apply URL.
4. Prioritize hands-on PEP/sanctions/adverse media screening, plus SoF/SoW; generic KYC and job-title keyword matches are insufficient.
5. Preserve all first-seen job identities, mark the source optional, and include it in the daily live count only after production verification.

Researching 100 companies is a usable discovery milestone. It is NOT proof that 100 extra employer job sources are live.

## Regulator100 live promotion (24 November 2026)
- Paynovate: full Breezy ATS audit extracted 5 published listings and verified 3 title-matched AML/risk job details and application routes; 0 eligible jobs after location/seniority checks (Belgium and France outside target geographies). Provider job-list minimum 5, enforced every new run.
- PingPong Europe: original company careers board extracted 4 job listings, with no target AML title matches on the initial run. Provider job-list minimum 4, enforced every new run.
- Currenxie and AllUnity prototype adapters returned only 1 listing each, below observed actual board coverage; PayFuture, Monavate and Outpayce did not have complete parsed listings. None of those five is promoted.
- Stability gate asks for 90 or more actual verified sources (of 97 configured), a healthy core 18, true novelty and fresh data. Configuration alone does not satisfy the launch threshold.

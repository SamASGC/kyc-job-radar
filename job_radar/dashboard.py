from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from job_radar.config import ROOT


def build_dashboard(jobs: list[dict], stats: dict, out_path: str = "public/index.html", generated_at: str = "") -> None:
    p = ROOT / out_path
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(jobs, ensure_ascii=False).replace("</", "<\\/")
    generated = generated_at or "sin cambios todavía"
    stats_payload = json.dumps(stats, ensure_ascii=False)
    doc = f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KYC/KYB Job Radar</title>
<style>
:root {{ color-scheme: light dark; --bg:#f5f7fb; --card:#fff; --text:#182230; --muted:#667085; --line:#e4e7ec; --accent:#155eef; --good:#067647; --warn:#b54708; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#101828; --card:#1d2939; --text:#f2f4f7; --muted:#98a2b3; --line:#344054; --accent:#84adff; --good:#75e0a7; --warn:#fec84b; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; background:var(--bg); color:var(--text); }}
.wrap {{ max-width:1600px; margin:0 auto; padding:24px; }}
h1 {{ margin:0 0 6px; font-size:28px; }}
.sub {{ color:var(--muted); margin-bottom:18px; }}
.cards {{ display:grid; grid-template-columns:repeat(4,minmax(140px,1fr)); gap:12px; margin:16px 0; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 16px; }}
.card b {{ font-size:22px; display:block; }}
.card span {{ color:var(--muted); font-size:12px; }}
.controls {{ display:grid; grid-template-columns:2fr repeat(5,minmax(120px,1fr)); gap:10px; margin:14px 0; }}
input,select,button {{ font:inherit; color:inherit; background:var(--card); border:1px solid var(--line); border-radius:9px; padding:9px 10px; }}
button {{ cursor:pointer; }} button:hover {{ border-color:var(--accent); }}
.tabs {{ display:flex; gap:8px; margin:8px 0 14px; }}
.tab.active {{ border-color:var(--accent); box-shadow:0 0 0 1px var(--accent) inset; }}
.tablebox {{ overflow:auto; background:var(--card); border:1px solid var(--line); border-radius:14px; }}
table {{ width:100%; border-collapse:collapse; min-width:1450px; }}
th,td {{ border-bottom:1px solid var(--line); text-align:left; vertical-align:top; padding:11px 10px; font-size:13px; }}
th {{ position:sticky; top:0; background:var(--card); z-index:2; white-space:nowrap; cursor:pointer; }}
tr:last-child td {{ border-bottom:0; }}
.role {{ font-weight:700; max-width:250px; }}
.company {{ font-weight:600; }}
.score {{ font-weight:800; font-variant-numeric:tabular-nums; }}
.score.hi {{ color:var(--good); }} .score.mid {{ color:var(--warn); }}
.skills {{ max-width:260px; }} .muted {{ color:var(--muted); }}
a {{ color:var(--accent); text-decoration:none; font-weight:700; }} a:hover {{ text-decoration:underline; }}
.badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 7px; margin:1px 3px 1px 0; font-size:11px; white-space:nowrap; }}
.small {{ font-size:11px; color:var(--muted); margin-top:4px; max-width:300px; }}
.empty {{ padding:30px; text-align:center; color:var(--muted); }}
.footer {{ color:var(--muted); font-size:12px; margin:14px 2px; line-height:1.5; }}
@media(max-width:900px) {{ .cards{{grid-template-columns:repeat(2,1fr)}} .controls{{grid-template-columns:1fr 1fr}} .wrap{{padding:14px}} }}
</style>
</head>
<body><div class="wrap">
<h1>KYC / KYB / AML Job Radar</h1>
<div class="sub">Radar determinista, sin IA de pago. Deduplicación persistente por empresa + rol + ubicación.</div>
<div class="cards">
  <div class="card"><b id="cVisible">0</b><span>ofertas visibles</span></div>
  <div class="card"><b id="c90">0</b><span>encaje ≥ 90%</span></div>
  <div class="card"><b id="c7">0</b><span>detectadas/publicadas ≤ 7 días</span></div>
  <div class="card"><b id="cHidden">0</b><span>ocultas por ti</span></div>
</div>
<div class="controls">
  <input id="q" placeholder="Buscar rol, empresa, skill, lugar…">
  <select id="minScore"><option value="0">Score: todos</option><option value="70">≥70%</option><option value="80">≥80%</option><option value="90">≥90%</option></select>
  <select id="sector"><option value="">Sector: todos</option><option>Fintech</option><option>Banca</option><option>Payments</option></select>
  <select id="mode"><option value="">Modalidad: todas</option><option>Remoto</option><option>Híbrido</option><option>Presencial</option><option>No indicado</option></select>
  <select id="country"><option value="">País: todos</option></select>
  <select id="source"><option value="">Fuente: todas</option></select>
</div>
<div class="tabs"><button id="tabActive" class="tab active">Ofertas</button><button id="tabHidden" class="tab">Ocultas</button><button id="resetHidden">Restaurar todas las ocultas</button></div>
<div class="tablebox"><table>
<thead><tr>
<th data-sort="title">Rol</th><th data-sort="company">Empresa</th><th data-sort="sector">Fintech / Banca / Payments</th>
<th data-sort="score">Encaje</th><th>Skills que comprarías</th><th data-sort="location_mode">Lugar</th><th data-sort="salary_display">Salario esperable</th>
<th data-sort="posted_at">Fecha</th><th>Link</th><th>Acción</th>
</tr></thead><tbody id="tbody"></tbody></table><div id="empty" class="empty" hidden>No hay ofertas con esos filtros.</div></div>
<div class="footer">Generado: {html.escape(generated)} · Los salarios marcados “estimado” son bandas orientativas, no salarios publicados por la empresa. “Fecha no publicada” significa que el radar detectó una vacante activa pero la fuente no expuso una fecha fiable. LinkedIn/Indeed no se scrapean.<br>Fuentes agregadas: <a href="https://jobicy.com/" target="_blank" rel="noopener">Jobicy</a>, <a href="https://remotive.com/" target="_blank" rel="noopener">Remotive</a>, <a href="https://www.arbeitnow.com/" target="_blank" rel="noopener">Arbeitnow</a>, <a href="https://remoteok.com/" target="_blank" rel="noopener">Remote OK</a>, <a href="https://himalayas.app/" target="_blank" rel="noopener">Himalayas</a> y <a href="https://weworkremotely.com/" target="_blank" rel="noopener">We Work Remotely</a>. La fuente concreta aparece debajo de cada empresa.</div>
</div>
<script>
const JOBS = {payload};
const RUN_STATS = {stats_payload};
const hiddenKey='kycRadar.hidden.v1';
let hidden=new Set(JSON.parse(localStorage.getItem(hiddenKey)||'[]'));
let showHidden=false, sortKey='score', sortDir=-1;
const $=id=>document.getElementById(id);
function esc(s){{return String(s??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));}}
function ageDays(j){{
 const s=j.posted_at||j.discovered_at; if(!s)return null; const d=new Date(s); if(Number.isNaN(d.getTime()))return null; return (Date.now()-d.getTime())/86400000;
}}
function selectedJobs(){{
 const q=$('q').value.trim().toLowerCase(), min=+$('minScore').value, sector=$('sector').value, mode=$('mode').value, country=$('country').value, source=$('source').value;
 let arr=JOBS.filter(j=>hidden.has(j.fingerprint)===showHidden);
 arr=arr.filter(j=>j.score>=min && (!sector||j.sector===sector) && (!mode||j.location_mode===mode) && (!country||j.country===country) && (!source||j.source===source));
 if(q)arr=arr.filter(j=>[j.title,j.company,j.sector,j.location,j.location_mode,j.country,j.salary_display,j.score_reason,(j.skills_to_buy||[]).join(' ')].join(' ').toLowerCase().includes(q));
 arr.sort((a,b)=>{{let x=a[sortKey]??'', y=b[sortKey]??''; if(sortKey==='score')return (x-y)*sortDir; return String(x).localeCompare(String(y))*sortDir;}});
 return arr;
}}
function render(){{
 const arr=selectedJobs(), tb=$('tbody'); tb.innerHTML='';
 for(const j of arr){{
   const tr=document.createElement('tr'); const cls=j.score>=90?'hi':(j.score>=80?'mid':'');
   const skills=(j.skills_to_buy||[]).length?(j.skills_to_buy||[]).map(x=>`<span class="badge">${{esc(x)}}</span>`).join(''):'<span class="muted">Consolida skills actuales</span>';
   const date=j.posted_at?esc(j.posted_at):`<span class="muted">Detectada ${{esc((j.discovered_at||'').slice(0,10))}}</span>`;
   tr.innerHTML=`<td class="role">${{esc(j.title)}}<div class="small">${{esc(j.score_reason)}}</div></td><td class="company">${{esc(j.company)}}<div class="small">${{esc(j.source)}}</div></td><td>${{esc(j.sector)}}</td><td class="score ${{cls}}">${{j.score}}%</td><td class="skills">${{skills}}</td><td><b>${{esc(j.location_mode)}}</b><div>${{esc(j.location||'No indicada')}}</div></td><td>${{esc(j.salary_display)}}</td><td>${{date}}</td><td><a href="${{esc(j.apply_url)}}" target="_blank" rel="noopener">Aplicar ↗</a></td><td><button data-id="${{esc(j.fingerprint)}}">${{showHidden?'Restaurar':'Ocultar'}}</button></td>`;
   tr.querySelector('button').onclick=()=>{{ if(showHidden)hidden.delete(j.fingerprint); else hidden.add(j.fingerprint); localStorage.setItem(hiddenKey,JSON.stringify([...hidden])); render(); }};
   tb.appendChild(tr);
 }}
 $('empty').hidden=arr.length>0;
 $('cVisible').textContent=JOBS.filter(j=>!hidden.has(j.fingerprint)).length;
 $('cHidden').textContent=hidden.size;
 $('c90').textContent=JOBS.filter(j=>!hidden.has(j.fingerprint)&&j.score>=90).length;
 $('c7').textContent=JOBS.filter(j=>!hidden.has(j.fingerprint)&&((ageDays(j)??999)<=7)).length;
}}
for(const id of ['q','minScore','sector','mode','country','source']) $(id).addEventListener(id==='q'?'input':'change',render);
$('tabActive').onclick=()=>{{showHidden=false;$('tabActive').classList.add('active');$('tabHidden').classList.remove('active');render();}};
$('tabHidden').onclick=()=>{{showHidden=true;$('tabHidden').classList.add('active');$('tabActive').classList.remove('active');render();}};
$('resetHidden').onclick=()=>{{hidden.clear();localStorage.setItem(hiddenKey,'[]');render();}};
document.querySelectorAll('th[data-sort]').forEach(th=>th.onclick=()=>{{const k=th.dataset.sort;if(sortKey===k)sortDir*=-1;else{{sortKey=k;sortDir=(k==='score'?-1:1)}}render();}});
[...new Set(JOBS.map(j=>j.country).filter(Boolean))].sort().forEach(v=>$('country').insertAdjacentHTML('beforeend',`<option>${{esc(v)}}</option>`));
[...new Set(JOBS.map(j=>j.source).filter(Boolean))].sort().forEach(v=>$('source').insertAdjacentHTML('beforeend',`<option>${{esc(v)}}</option>`));
render();
</script></body></html>'''
    p.write_text(doc, encoding="utf-8")

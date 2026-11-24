import concurrent.futures
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
OFF_LIMITS = ('workable.com', 'workablemail.com')
def honor_cooldown(event, args):
    if event == 'urllib.Request':
        host = (urlsplit(args[0]).hostname or '').lower()
        if any(host == suffix or host.endswith('.' + suffix) for suffix in OFF_LIMITS):
            raise RuntimeError('Host in published retry interval')
sys.addaudithook(honor_cooldown)
from live_e2e18_full import audit_one
rows = {r['id']:r for r in json.loads(Path('fuentes.json').read_text())['sources']}
ids = """artea avarda-bank citadele-banka-lt aps-bank fimbank-malta banque-de-luxembourg jtc-luxembourg caceis-europe lt-b4b-employmenthero lt-paystrax-official-external lt-nikulipe-official lt-paynt-direct-employer lt-finci-inline-careers lt-nayax-global-legal-compliance vialet vivid-money avega-luxembourg dm-financial ufundservices cafico-international riverbank seb solidgate payhawk payoneer planet qonto upvest remitly dlocal boku raisin xtb trading212 etoroltd ofx sumup checkout-com dojo adyen alantra apex-group alter-domus ocorian flywire brown-brothers-harriman dws moneybase moss mercuryo western-union state-street northern-trust bbva ing santander""".split()
ids=[i for i in ids if i in rows][int(os.environ['SHARD'])::6]
def run(i):
    r=audit_one(rows[i],minutes=3)
    Path('evidence').mkdir(exist_ok=True)
    Path('evidence',i+'.json').write_text(json.dumps(r,ensure_ascii=False))
    print('CHECKED',i,r.get('total_listed'),r.get('relevant_leads'),r.get('unverified_in_scope'),r.get('state'),r.get('list_complete'),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(run,ids))

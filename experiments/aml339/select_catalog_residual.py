#!/usr/bin/env python3
"""Select exactly 50 previously unmonitored original-catalog sources.
Never enroll them. Reproducible selection with audited-source and ATS deduplication.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.aml339_source_manifest import CORE,OPTIONAL

ARCHIVE=ROOT/"experiments/aml339/full_original_339_sources.zip"
PREVIOUS_HOLD={"melio","gohenry","nexo","visa-currencycloud","capimoney","lt-paystrax-official-external","lt-nayax-global-legal-compliance"}
PREVIOUS_HOLD.update(["banque-de-luxembourg","caceis-europe","forvis-mazars","infront","lnds","veriff","hhhub","tsys-global-payments","affirm","arq","clera","consensys","crypto-com","deutsche-bank","fin","flourish","gate","nomad","nubank","onhires","paypal","paytm","pennylane","rbc","riskified","synctera","truebill","21shares","aavelabs","alantra","alpaca","amadeus-fincrime","apex-group","atdomco","augustus","b2spin","bbva","betsson","binance","bitpanda-enterprise","bjak","blackrock","blockchain-com","booming-games","brown-brothers-harriman","bunch","capco","carlyle","carta","coinbase"])
PREVIOUS_HOLD.update(["coingecko","column","dinotech","dourolabs","dws","eneba","ether-fi","experian","fdj-united","finary","fis","fiserv","flowtraders","forter","freetrade","fundingcircle","gam","getground","guidehouse","hifi","hopae","imc","ing","julius-baer","jumio","justmarkets","kaiko","kraken","ledger","lemon-markets","lendable","leovegasgroup","lombard-odier","loyens-loeff","mastercard","morpho","nasdaq","nelly","northern-trust","novacredit","ocrolusinc","okx","paddle","pathward","persona","playson","polymarket","primexbt","privacy","pwc-campus"])
BLOCKED=("workable","sage.hr","linkedin.com")
def signature(row):
    u=urlsplit(row.get("careers_url") or "")
    return (u.hostname or "",u.path.rstrip("/").casefold()) if u.hostname else None

def route_signature(row):
    route=row.get("route")
    if not isinstance(route,list) or len(route)<2:return None
    # The full tenant/path tuple, not just the ATS provider hostname.
    return tuple(str(x).casefold().rstrip("/") for x in route)
def score(row):
    s=json.dumps(row,ensure_ascii=False).casefold()
    priority=0
    for word in ("lithuania","vilnius","latvia","riga","estonia","tallinn","malta","luxembourg","madrid","spain","lt-","ee-","(lt","(ee","(mt","(lu","(es","lituania","estonia","luxemburgo"):
        if word in s:priority+=5
    for word in ("payment","pagos","fintech","bank","money","remit","wallet","crypto","exchange","pay","capital","financial","finance","asset","aml","compliance","risk"):
        if word in s:priority+=2
    return priority
def choose(rows,active):
    assert len(rows)==len({x["id"] for x in rows})==339
    seen_routes={route_signature(x) for x in rows if x["id"] in active}
    seen_urls={signature(x) for x in rows if x["id"] in active}
    result=[]
    for x in sorted(rows,key=lambda x:(-score(x),x["id"])):
        sid=x["id"];route=route_signature(x);url=signature(x)
        if sid in active or sid in PREVIOUS_HOLD or not route or not url:continue
        if any(b in str(x.get("route",[])).casefold() or b in str(x.get("careers_url","")).casefold() for b in BLOCKED):continue
        if route in seen_routes or url in seen_urls:continue
        seen_routes.add(route);seen_urls.add(url)
        result.append({"id":sid,"name":x.get("name",sid),"careers_url":x["careers_url"],"route":x["route"],"priority_score":score(x)})
        if len(result)==50:break
    if not result:raise ValueError("No distinct eligible remaining sources")
    return result
def main():
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()=="e8a08263115c4bbbaf02d4a4ae59431a7e4b16a0a7c79e339ff2f53ef9aadc02"
    with ZipFile(ARCHIVE) as z:rows=json.loads(z.read("fuentes.json"))["sources"]
    active=set(CORE+OPTIONAL)
    selected=choose(rows,active)
    out={"batch_size":len(selected),"already_configured":len(active),"candidates":selected}
    Path("catalog_residual.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("CATALOG_RESIDUAL_SELECTION",json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()

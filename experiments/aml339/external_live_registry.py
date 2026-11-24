#!/usr/bin/env python3
"""Single source of truth for audited external employers; research never enrolls itself."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REGISTRY=ROOT/"external_live_registry.json"
DRIVERS={"wave02","next","generic"}
def load_registry(path=REGISTRY):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema")!="aml339_external_live_registry_v1":raise ValueError("Unexpected external registry schema")
    rows=d.get("sources")
    if not isinstance(rows,list) or not rows or len(rows)>200:raise ValueError("Invalid external source inventory")
    seen=set()
    for row in rows:
        sid=row.get("id")
        if not isinstance(sid,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}",sid) or sid in seen:raise ValueError("Duplicate or invalid external ID")
        if row.get("driver") not in DRIVERS or type(row.get("audit_run")) is not int or row["audit_run"]<=0:raise ValueError("Missing audited driver or run")
        seen.add(sid)
    return rows
def ids(path=REGISTRY):return tuple(row["id"] for row in load_registry(path))
def matrix(path=REGISTRY):
    return {"include":[{"source":row["id"],"driver":row["driver"]} for row in load_registry(path)]}
if __name__=="__main__":print(json.dumps(matrix(),separators=(",",":")))

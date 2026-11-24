"""Second 50-portal employer wave: target new practical FinCrime competencies.

Unlike the previous 50 wave, these are currently not in the active AML339
monitor, even though their employers were already in the immutable 339-company
catalog. An employer's place in this list is NOT independent proof of a PI/EMI
licence; several are banking or financial-infrastructure / RegTech providers.

Most IDs have already passed a live full source audit in an earlier 24 Nov
pilot. Others are new canary targets; a failed or incomplete source is never
reported as a working monitor. 50 scanned != 50 successful.
"""
WAVE50_B = (
    "lt-b4b-employmenthero",
    "citadele-banka-lt",
    "vialet",
    "riverbank",
    "qonto",
    "dojo",
    "xtb",
    "jtc-luxembourg",
    "lt-finci-inline-careers",
    "ufundservices",
    "payoneer",
    "boku",
    "sumup",
    "artea",
    "mercuryo",
    "alter-domus",
    "aps-bank",
    "vivid-money",
    "upvest",
    "trading212",
    "seb",
    "adyen",
    "fimbank-malta",
    "lt-nikulipe-official",
    "avega-luxembourg",
    "solidgate",
    "etoroltd",
    "remitly",
    "avarda-bank",
    "cafico-international",
    "raisin",
    "checkout-com",
    "ocorian",
    "lt-paynt-direct-employer",
    "dm-financial",
    "payhawk",
    "dlocal",
    "ofx",
    "moss",
    "lhv-uk",
    "solarisbank",
    "tide",
    "finoa",
    "tuum",
    "lynxtech",
    "fireblocks",
    "chainalysis",
    "flagright",
    "fyst",
    "xapo-bank",
)
assert len(WAVE50_B)==len(set(WAVE50_B))==50

# Prior independent evidence from run 45421207429; still must scan again before
# publication because websites, application URLs and provider HTTP limits change.
ALREADY_AUDITED_EARLIER = ["lt-b4b-employmenthero","citadele-banka-lt","vialet","riverbank","qonto","dojo","xtb","jtc-luxembourg","lt-finci-inline-careers","ufundservices","payoneer","boku","sumup","artea","mercuryo","alter-domus","aps-bank","vivid-money","upvest","trading212","seb","adyen","fimbank-malta","lt-nikulipe-official","avega-luxembourg","solidgate","etoroltd","remitly","avarda-bank","cafico-international","raisin","checkout-com","ocorian","lt-paynt-direct-employer","dm-financial","payhawk","dlocal","ofx","moss"]
UNPROVEN_BULK_CANDIDATES = ["lhv-uk","solarisbank","tide","finoa","tuum","lynxtech","fireblocks","chainalysis","flagright","fyst","xapo-bank"]

"""Exactly 50 under-monitored official careers boards for the first bulk AML bridge wave.

All IDs are already part of the immutable original 339-employer archive.
These are NEW TO AML339 LIVE MONITORING, not falsely claimed newly discovered
legal entities or new licences. Payment infrastructure and RegTech firms are
also included, and being in this list does not itself establish direct EMI status.

Actual live eligibility is decided per source on each complete HTTP audit;
an inaccessible board is never counted as verified or advertised as hiring.
"""
BATCH50=(
    "bondora","brite","enfuce","eupago","finom","fipto",
    "gocardless","inbank","juni","lightyear","lunar","mangopay",
    "monei","montonio","mypos","northmill","paymentology","payset",
    "pleo","pliant","ppro","sardine","satispay","scalapay",
    "spendesk","sumsub","swan","teya","thunes","trustly",
    "unlimit","unzer","verto","vitesse","wamo","zero-hash",
    "esto","ipf-digital","mintos","delfingroup","bigbank","lightspark",
    "lhv-ee","walletto","mano-bank","bankera","payswix",
    "salv-technologies","ibanfirst","finteqhub",
)
assert len(BATCH50)==len(set(BATCH50))==50
# This is not a list of 50 newly licensed EMIs: it includes providers of
# regulated financial services, payments infrastructure, and FinCrime tooling.
FOCUS={
    "regulated_financial_and_payment_firms": 42,
    "technical_payment_and_fincrime_service_providers": 8,
}

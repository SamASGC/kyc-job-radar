from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from job_radar.website_enrichment import (
    acceptable_official_url, normalized_business_name, entity_candidates,
    homepage_identity_matches, overlay_directory, registry_key,
)
from job_radar.directory import load_directory_batch
from scripts.enrich_missing_websites import candidates_to_research, enrich, verify_site


class LicensedWebsiteEnrichmentTests(unittest.TestCase):
    def test_normalized_legal_names(self):
        self.assertEqual(normalized_business_name("ACE Money Transfer Limited"),"ace money transfer")
        self.assertEqual(normalized_business_name("ACE MONEY TRANSFER LTD"),"ace money transfer")
        self.assertNotEqual(normalized_business_name("Ace Money Transfer"),
                            normalized_business_name("Ace Insurance"))

    def test_block_unsafe_websites(self):
        for url in ("http://a.com", "https://127.0.0.1/a",
                    "https://10.0.0.2/a", "https://localhost/a",
                    "https://company.local", "ftp://bank.example.com",
                    "https://x:y@realbank.com", "https://evil.example"):
            self.assertFalse(acceptable_official_url(url),url)
        self.assertEqual(acceptable_official_url("https://www.legit-bank.co.uk/?utm=ad"),
                         "https://www.legit-bank.co.uk/")

    def test_strict_country_plus_identity_plus_website(self):
        search={"search":[{"id":"Q111"},{"id":"Q222"}]}
        entity=lambda country,name,site:{
            "labels":{"en":{"value":name}}, "aliases":{},
            "claims":{
                "P17":[{"mainsnak":{"datavalue":{"value":{"id":country}}}}],
                "P856":[{"mainsnak":{"datavalue":{"value":site}}}],
            }
        }
        details={"entities":{
            "Q111":entity("Q29","ACE Money Transfer Limited","https://acetransfer.com"),
            "Q222":entity("Q145","ACE Money Transfer Limited","https://uk-ace.com"),
        }}
        matches=entity_candidates(search,details,"ACE MONEY TRANSFER LTD","ES")
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]["website"],"https://acetransfer.com")
        self.assertEqual(entity_candidates(search,details,"ACE MONEY TRANSFER LTD","LT"),[])
        self.assertEqual(entity_candidates(search,details,"Different Firm","ES"),[])

    def test_homepage_must_corroborate_brand(self):
        self.assertTrue(homepage_identity_matches(
            '<html><head><title>ACE Money Transfer — Home</title></head></html>',
            "ACE Money Transfer Ltd"))
        self.assertFalse(homepage_identity_matches(
            '<html><head><title>Some other company</title></head></html>',
            "ACE Money Transfer Ltd"))

    def test_overlay_preserves_unverified_and_upstream(self):
        data=[
            {"name":"ACE MONEY TRANSFER LIMITED","country":"GB","website":"","enabled":False},
            {"name":"Other","country":"ES","website":"","enabled":False},
        ]
        verified=[
            {"name":"ACE Money Transfer Ltd","country":"GB",
             "website":"https://acetransfer.com","verified":True,
             "verified_at":"2026-10-12T12:00:00+00:00"},
            {"name":"Other","country":"ES","website":"https://other.com","verified":False},
        ]
        result=overlay_directory(data,verified)
        self.assertEqual(result[0]["website"],"https://acetransfer.com")
        self.assertTrue(result[0]["enabled"])
        self.assertEqual(result[1]["website"],"")
        self.assertEqual(data[0]["website"],"")

    def test_hourly_scan_consumes_overlay_but_original_registry_unmodified(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/"fintech_directory.json"
            rows=[{"name":"ACE Money Transfer Ltd","country":"GB",
                   "website":"","sector":"Payments","priority":1,"enabled":False}]
            directory.write_text(json.dumps(rows),encoding="utf-8")
            overlay=directory.parent/"verified_company_websites.json"
            overlay.write_text(json.dumps([
                {"name":"ACE MONEY TRANSFER LIMITED","country":"GB",
                 "website":"https://acetransfer.com","verified":True}
            ]),encoding="utf-8")
            batch,stats=load_directory_batch(directory,{},set(),cold_per_hour=5,
                                             now=datetime(2026,10,12,tzinfo=timezone.utc))
            self.assertEqual(len(batch),1)
            self.assertEqual(batch[0]["careers_url"],"https://acetransfer.com")
            self.assertEqual(json.loads(directory.read_text()),rows)

    def test_selection_skips_recently_attempted(self):
        now=datetime(2026,10,12,tzinfo=timezone.utc)
        rows=[{"name":"ACE Ltd","country":"GB","website":""},
              {"name":"EuroPay Ltd","country":"LT","website":""}]
        attempted={registry_key("ACE Ltd","GB"):{"checked_at":now.isoformat()}}
        sample=candidates_to_research(rows,attempted,25,now)
        self.assertEqual([r["name"] for r in sample],["EuroPay Ltd"])


class HTTPWebsiteVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_different_domain_redirect_is_rejected(self):
        class Response:
            status_code=301
            headers={"location":"https://evil-bank.example.org"}
        class Http:
            async def get(self,*args,**kwargs):
                return Response()
        status,reason=await verify_site(Http(),"https://genuine-bank.com","Genuine Bank")
        self.assertFalse(status)
        self.assertEqual(reason,"redirects_to_different_domain")


if __name__=="__main__":
    unittest.main()

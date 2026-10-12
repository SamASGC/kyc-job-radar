from __future__ import annotations

import unittest

from job_radar.discovery import candidate_careers_links
from job_radar.sources.generic import fetch_generic


class HomepageToCareersTests(unittest.TestCase):
    def test_rank_company_careers_and_reject_untrusted_domains(self):
        html = """
        <a href="/blog/kyc">KYC Blog</a>
        <a href="https://jobs.ashbyhq.com/realbank">Careers</a>
        <a href="https://careers.realbank.example/jobs">Jobs</a>
        <a href="http://127.0.0.1/secret">Careers</a>
        <a href="https://bad.example/jobs">Careers</a>
        <a href="file:///etc/passwd">Careers</a>
        """
        actual = candidate_careers_links(html, "https://www.realbank.example", 2)
        self.assertEqual(len(actual), 2)
        self.assertTrue(any("jobs.ashbyhq.com/realbank" in u for u in actual))
        self.assertTrue(any("careers.realbank.example/jobs" in u for u in actual))
        self.assertFalse(any("bad.example" in u or "127.0.0.1" in u for u in actual))

    def test_homepage_careers_discovered_with_at_most_one_hop(self):
        class Response:
            def __init__(self,url,html):
                self.url=url
                self.text=html
            def raise_for_status(self):
                return None
        class FakeHttp:
            def __init__(self):
                self.urls=[]
            async def get(self,url):
                self.urls.append(url)
                if url=="https://realbank.example":
                    return Response(url,'<a href="/careers">Careers</a>')
                if url=="https://realbank.example/careers":
                    return Response(url,'<h1>Open positions</h1><a href="https://jobs.ashbyhq.com/realbank">See jobs</a>')
                raise AssertionError("Unexpected crawl: "+url)
        import asyncio
        http=FakeHttp()
        company={"name":"RealBank","sector":"Payments","careers_url":"https://realbank.example"}
        _, ats, final_url=asyncio.run(fetch_generic(http,company))
        self.assertEqual(http.urls,[
            "https://realbank.example",
            "https://realbank.example/careers",
        ])
        self.assertEqual(ats,[{"kind":"ashby","slug":"realbank"}])
        self.assertEqual(final_url,"https://realbank.example/careers")

    def test_no_crawl_of_external_non_ats_careers(self):
        self.assertEqual(
            candidate_careers_links(
                '<a href="https://random-company.example/careers">Careers</a>',
                "https://realbank.example",
            ),[]
        )


if __name__=="__main__":
    unittest.main()

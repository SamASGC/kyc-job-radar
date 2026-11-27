"""Pure contract tests, independent of the pinned parser's runtime."""
import ast,copy,re,unittest
from pathlib import Path
from urllib.parse import urlsplit

class MangopayDetailGeographyTests(unittest.TestCase):
    def setUp(self):
        path=Path("experiments/aml339/live_e2e18_full.py")
        node=next(x for x in ast.parse(path.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=="mangopay_detail_outside")
        scope={"re":re,"urlsplit":urlsplit,"clean":lambda x:str(x or "").strip(),
               "role_geography":lambda x:"outside_scope" if "France" in str(x) and "Madrid" not in str(x) else "target"}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),"exec"),scope)
        self.check=scope["mangopay_detail_outside"]
        self.source={"id":"mangopay","route":["teamtailor","career.mangopay.com","/jobs"]}
        self.title="Legal Intern - Privacy"
        self.url="https://career.mangopay.com/jobs/123-privacy"
        self.post={"title":self.title,"jobLocation":{"address":{"addressCountry":"FR","addressLocality":"Paris"}}}
        self.job={"title":self.title,"url":self.url,"location":"Paris, France","_page":{"final_url":self.url}}
    def call(self,post=None,changes=None,source=None,listed_title=None):
        job=dict(self.job,**(changes or {}))
        posts=[self.post if post is None else post]
        job["_parser"]=type("P",(),{"posts":lambda self:posts})()
        return self.check(source or self.source,listed_title or self.title,self.url,job)
    def test_explicit_same_job_france(self):
        self.assertTrue(self.call())
    def test_real_card_metadata_not_part_of_title(self):
        suffix="\n \nLegal, Risk and Compliance\n ·\n Mangopay France - Paris\n ·\n Hybrid"
        self.assertTrue(self.call(listed_title=self.title+suffix))
        self.assertFalse(self.call(listed_title=self.title+suffix.replace("Paris","Madrid")))
        self.assertFalse(self.call(listed_title=self.title+suffix.replace("Hybrid","Fully Remote")))
        self.assertFalse(self.call(listed_title=self.title+" Other job"))
    def test_other_sources_and_wrong_redirect_fail(self):
        self.assertFalse(self.call(source={"id":"other"}))
        self.assertFalse(self.call(changes={"_page":{"final_url":"https://career.mangopay.com/jobs/999-other"}}))
    def test_unknown_remote_mixed_or_target_country_never_excluded(self):
        for changed in ({"location":"Madrid, Spain"},{"location":""},{"remote":True}):
            self.assertFalse(self.call(changes=changed))
        for changed in ({"jobLocationType":"TELECOMMUTE"},{"applicantLocationRequirements":{"name":"Spain"}},
                        {"jobLocation":[self.post["jobLocation"],{"address":{"addressCountry":"ES","addressLocality":"Madrid"}}]},
                        {"jobLocation":{"address":{"addressLocality":"Paris"}}},{"title":"Another role"}):
            self.assertFalse(self.call(post=dict(self.post,**changed)))

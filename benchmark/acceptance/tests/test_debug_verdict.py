import contextlib,io,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import cli
from acceptance.common import atomic,seal,read

class DebugVerdict(unittest.TestCase):
    def run_verdict(self,mode,scope,decision,tamper=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/'run'
            envelope={'executionMode':mode,'group':'all','qualitySummary':{'scope':scope,'releaseDecision':decision}}
            atomic(run/'run.json',envelope);seal(run)
            if tamper:atomic(run/'extra.json',{})
            with contextlib.redirect_stdout(io.StringIO()):
                try:cli.main(['--home',str(root/'home'),'verdict','--run',str(run)]);code=0
                except SystemExit as e:code=e.code
            self.assertEqual(read(run/'run.json'),envelope)
            self.assertFalse((root/'home/last-completed.json').exists())
            return code
    def test_debug_findings_do_not_fail_workflow(self):
        for decision in ['FAIL','INCOMPLETE']:
            self.assertEqual(self.run_verdict('debug','partial:debug',decision),0)
    def test_formal_failure_and_incompletion_still_fail(self):
        for decision in ['FAIL','INCOMPLETE']:
            self.assertNotEqual(self.run_verdict('formal','complete',decision),0)
    def test_debug_cannot_claim_pass_or_complete_scope(self):
        self.assertNotEqual(self.run_verdict('debug','partial:debug','PASS'),0)
        self.assertNotEqual(self.run_verdict('debug','complete','FAIL'),0)
    def test_integrity_failure_still_fails_debug(self):
        self.assertNotEqual(self.run_verdict('debug','partial:debug','FAIL',tamper=True),0)

if __name__=='__main__':unittest.main()

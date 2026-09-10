import json,sys,unittest,os,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import isolation

class Isolation(unittest.TestCase):
    @unittest.skipUnless(os.getenv('REN_TEST_NETNS')=='1','Requires disposable Linux CI runner')
    def test_real_runner_namespace_and_network_trace(self):
        health=isolation.probe()
        self.assertEqual(health['exitCode'],0,health)
        with tempfile.TemporaryDirectory() as d:
            trace=Path(d)/'network.trace'
            code="import socket,errno; s=socket.socket(); s.bind(('127.0.0.1',0)); result=s.connect_ex(('192.0.2.1',9)); assert result==errno.ENETUNREACH,result"
            result=isolation.run(health,['strace','-f','-e','trace=network','-o',str(trace),sys.executable,'-I','-c',code],{'HOME':d,'PATH':os.environ['PATH']},timeout=10)
            self.assertEqual(result['exitCode'],0,result)
            self.assertIn('ENETUNREACH',trace.read_text())

    def test_fallback_requires_verified_uid_and_isolated_network(self):
        bad={'exitCode':1,'stdout':'','stderr':'uid_map denied'}
        good={'exitCode':0,'stdout':json.dumps({'uid':1001,'netns':'net:[2]','interfaces':['lo']}),'stderr':''}
        with patch.object(isolation,'candidates',return_value=[('user',['unshare']),('sudo',['sudo'])]),patch.object(isolation.platform,'system',return_value='Linux'),patch.object(isolation.os,'readlink',return_value='net:[1]'),patch.object(isolation.os,'getuid',return_value=1001),patch.object(isolation,'process',side_effect=[bad,good]):
            result=isolation.probe()
        self.assertEqual(result['mode'],'sudo');self.assertEqual(len(result['attempts']),2)
    def test_root_host_namespace_and_external_interfaces_rejected(self):
        for uid,netns,interfaces in [(0,'net:[2]',['lo']),(1001,'net:[1]',['lo']),(1001,'net:[2]',['lo','eth0'])]:
            with self.subTest(uid=uid,netns=netns),patch.object(isolation,'candidates',return_value=[('test',['unshare'])]),patch.object(isolation.platform,'system',return_value='Linux'),patch.object(isolation.os,'readlink',return_value='net:[1]'),patch.object(isolation.os,'getuid',return_value=1001),patch.object(isolation,'process',return_value={'exitCode':0,'stdout':json.dumps({'uid':uid,'netns':netns,'interfaces':interfaces})}):
                self.assertIsNone(isolation.probe()['exitCode'])
    def test_environment_restored_after_prefix_without_values_in_argv(self):
        env={'HOME':'/isolated','NODE_OPTIONS':'--require=probe','DECKRENDER_API_KEY':'synthetic-sentinel'}
        def inspect(command,**kwargs):
            self.assertEqual(command[0],'prefix')
            self.assertNotIn('synthetic-sentinel',' '.join(command))
            file=Path(command[-3]);self.assertEqual(json.loads(file.read_text()),env)
            self.assertEqual(file.stat().st_mode & 0o777,0o600)
            self.assertEqual(command[-2:],['node','test.js'])
            return {'exitCode':0}
        with patch.object(isolation,'process',side_effect=inspect):
            self.assertEqual(isolation.run({'prefix':['prefix']},['node','test.js'],env)['exitCode'],0)

if __name__=='__main__':unittest.main()

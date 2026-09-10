import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import start

class StartupTests(unittest.TestCase):
 def test_prepare_creates_environment_then_installs_and_remembers_requirements(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'requirements.txt').write_text('PyYAML>=6,<7\n')
   def run(args,**kwargs):
    if 'venv' in args:
     python=root/'.venv'/('Scripts/python.exe' if start.os.name=='nt' else 'bin/python')
     python.parent.mkdir(parents=True);python.touch()
    return Mock(returncode=0)
   with patch.object(start,'ROOT',root),patch.object(start.subprocess,'run',side_effect=run) as calls:
    first=start.prepare()
    self.assertTrue(first.exists())
    self.assertEqual(sum('pip' in c.args[0] for c in calls.call_args_list),1)
    calls.reset_mock();self.assertEqual(start.prepare(),first)
    self.assertFalse(any('pip' in c.args[0] for c in calls.call_args_list))

 def test_launcher_uses_same_database_for_initialization_viewer_and_recorder(self):
  viewer=Mock();viewer.poll.side_effect=[None,0,0,0];viewer.returncode=0
  recorder=Mock();recorder.poll.return_value=0;recorder.returncode=0
  with patch.object(start,'prepare',return_value=Path('python.exe')),patch.object(start.subprocess,'run') as run,patch.object(start.subprocess,'Popen',side_effect=[viewer,recorder]) as popen,patch.object(start.urllib.request,'urlopen'),patch.object(start.sys,'argv',['start.py','all','--database','local.sqlite3','--no-browser']):
   start.main()
  expected=str(Path('local.sqlite3').resolve())
  self.assertIn(expected,run.call_args.args[0])
  self.assertTrue(all(expected in call.args[0] for call in popen.call_args_list))

if __name__=='__main__':unittest.main()

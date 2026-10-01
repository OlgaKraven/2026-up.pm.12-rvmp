import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build import source_fingerprint, load_course

class ReleaseInputsTest(unittest.TestCase):
    def test_fingerprint_detects_code_snippet_and_asset_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('content/course.json','scripts/build.py','scripts/check.py','assets/style.css','tutorial/first.cs','unity-project/Assets/Scripts/Logic.cs'):
                p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('first')
            previous=source_fingerprint(root)
            for name in ('unity-project/Assets/Scripts/Logic.cs','tutorial/first.cs','assets/style.css'):
                (root/name).write_text('changed')
                current=source_fingerprint(root)
                self.assertNotEqual(current,previous,name)
                previous=current
            private=root/'unity-project/Library/cache';private.parent.mkdir();private.write_text('cache')
            self.assertEqual(previous,source_fingerprint(root))

    def test_each_card_starts_with_its_downloads(self):
        course=load_course()
        self.assertEqual(len(course['areas']),30)
        for card in course['areas']:
            self.assertEqual([b['kind'] for b in card['blocks'][:3]],['link']*3,card['title'])
            self.assertEqual({b['href'].rsplit('/',1)[-1] for b in card['blocks'][:3]},
                             {'CrystalRoute-UnityProject.zip','guide.pdf','report-template.md'})

if __name__=='__main__': unittest.main()

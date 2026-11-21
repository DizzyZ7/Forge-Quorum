"""Profile, routing and manifest-security regression tests."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from forgequorum.cli import InstallError, check, install, load_manifest, main, plan_install, status, uninstall
from forgequorum.profiles import profile_names, selections
from forgequorum.registry import AGENTS, SKILLS, payload
from forgequorum.routing import recommend


class Version02Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_profiles_install_doctor_and_uninstall(self):
        for profile in profile_names():
            with self.subTest(profile=profile):
                target = self.root / profile
                target.mkdir()
                count, _ = install(target, profile=profile)
                selected_agents, selected_skills = selections(profile,
                    tuple(a.name for a in AGENTS), tuple(s.name for s in SKILLS))
                self.assertEqual(count, len(selected_agents) + len(selected_skills) + 3)
                result = status(target)
                self.assertTrue(result['ok'])
                self.assertEqual((result['agents'], result['skills']),
                                 (len(selected_agents), len(selected_skills)))
                self.assertEqual(result['profile'], profile)
                self.assertEqual(install(target)[0], 0)
                self.assertGreater(uninstall(target)[0], 0)
                self.assertFalse((target / '.forgequorum/manifest.json').exists())

    def test_profile_switch_requires_explicit_uninstall_and_never_writes(self):
        install(self.root, profile='python')
        before = (self.root / '.forgequorum/manifest.json').read_bytes()
        with self.assertRaisesRegex(InstallError, 'uninstall before changing'):
            install(self.root, profile='security')
        self.assertEqual((self.root / '.forgequorum/manifest.json').read_bytes(), before)
        self.assertTrue((self.root / '.codex/agents/python-backend.toml').exists())

    def test_legacy_manifest_can_upgrade_without_dropping_ownership(self):
        install(self.root)
        path = self.root / '.forgequorum/manifest.json'
        old = json.loads(path.read_text())
        old['format'] = 1
        old['version'] = '0.1.0'
        old.pop('profile')
        path.write_text(json.dumps(old))
        self.assertEqual(load_manifest(self.root).get('profile', 'full'), 'full')
        install(self.root)
        result = status(self.root)
        self.assertTrue(result['ok'])
        self.assertEqual(result['profile'], 'full')
        self.assertEqual(json.loads(path.read_text())['format'], 2)

    def test_manifest_path_injection_refused_before_delete(self):
        (self.root / 'important.txt').write_text('must remain', encoding='utf8')
        install(self.root)
        manifest = self.root / '.forgequorum/manifest.json'
        data = json.loads(manifest.read_text())
        import hashlib
        data['managed_files']['important.txt'] = hashlib.sha256(b'must remain').hexdigest()
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(InstallError, 'unrecognized managed path'):
            uninstall(self.root)
        with self.assertRaisesRegex(InstallError, 'unrecognized managed path'):
            install(self.root)
        self.assertEqual((self.root / 'important.txt').read_text(), 'must remain')
        self.assertTrue((self.root / '.codex/agents/architect.toml').exists())

    def test_invalid_sha_is_refused(self):
        install(self.root)
        manifest = self.root / '.forgequorum/manifest.json'
        data = json.loads(manifest.read_text())
        key = next(iter(data['managed_files']))
        data['managed_files'][key] = 'X' * 64
        manifest.write_text(json.dumps(data))
        with self.assertRaises(InstallError):
            plan_install(self.root)

    def test_symlink_in_manifest_path_rejected_before_uninstall(self):
        install(self.root)
        out = self.root / 'outside'
        out.mkdir()
        target = self.root / '.codex/agents/architect.toml'
        target.unlink()
        external = out / 'architect.toml'
        external.write_text('do not touch', encoding='utf8')
        try:
            target.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(InstallError, 'symlink'):
            uninstall(self.root)
        self.assertEqual(external.read_text(), 'do not touch')

    def test_status_json_and_doctor_json(self):
        install(self.root, profile='web')
        for command in ('status', 'doctor'):
            with self.subTest(command=command):
                out = StringIO()
                with contextlib.redirect_stdout(out):
                    code = main([command, '--target', str(self.root), '--json'])
                self.assertEqual(code, 0)
                report = json.loads(out.getvalue())
                self.assertTrue(report['installed'])
                self.assertEqual(report['profile'], 'web')
                self.assertTrue(report['ok'])

    def test_recommend_english_and_russian(self):
        db = recommend('Миграция таблиц PostgreSQL и SQL запросов')
        self.assertEqual(db['skill'], 'data-migration')
        self.assertEqual(db['agents'][0], 'database-engineer')
        sec = recommend('Audit authorization and security boundaries', profile='security')
        self.assertEqual(sec['skill'], 'security-gate')
        self.assertTrue(set(sec['agents']).issubset(selections('security',
            tuple(a.name for a in AGENTS), tuple(s.name for s in SKILLS))[0]))
        front = recommend('Сделай адаптивный React интерфейс', profile='web')
        self.assertEqual(front['skill'], 'build-feature')
        self.assertEqual(front['agents'][0], 'frontend-engineer')
        self.assertEqual(recommend('Unrecognized engineering work')['skill'], 'route-task')

    def test_recommend_is_bounded_and_deterministic(self):
        a = recommend('FastAPI endpoint for a webhook')
        b = recommend('FastAPI endpoint for a webhook')
        self.assertEqual(a, b)
        self.assertLessEqual(len(a['agents']), 3)
        with self.assertRaises(ValueError):
            recommend('   ')
        with self.assertRaises(ValueError):
            recommend('task', max_agents=100)

    def test_profiles_select_only_valid_names(self):
        self.assertEqual(len(payload('full')), len(AGENTS) + len(SKILLS))
        with self.assertRaises(ValueError):
            payload('invalid-profile')


if __name__ == '__main__':
    unittest.main()

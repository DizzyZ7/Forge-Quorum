import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from forgequorum.cli import InstallError, check, install, plan_install, uninstall
from forgequorum.registry import AGENTS, AGENTS_BLOCK, CONFIG, SKILLS, payload


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_full_install_and_doctor(self):
        changed, _ = install(self.root)
        self.assertEqual(changed, len(AGENTS) + len(SKILLS) + 3)
        errors, warnings = check(self.root)
        self.assertFalse(errors, errors)
        self.assertTrue((self.root / '.codex/config.toml').exists())
        self.assertIn('forge-quorum', (self.root / 'AGENTS.md').read_text())
        self.assertIsInstance(warnings, list)

    def test_install_twice_is_idempotent(self):
        install(self.root)
        changed, _ = install(self.root)
        self.assertEqual(changed, 0)

    def test_dry_run_is_read_only(self):
        changed, output = install(self.root, dry_run=True)
        self.assertGreater(changed, 0)
        self.assertTrue(output[0].startswith('WOULD WRITE'))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_agents_md_is_restored_byte_for_byte(self):
        original = '# Existing project guidance\nDo not delete me.'
        (self.root / 'AGENTS.md').write_text(original, encoding='utf8')
        install(self.root)
        self.assertTrue((self.root / 'AGENTS.md').read_text().startswith(original))
        uninstall(self.root)
        self.assertEqual((self.root / 'AGENTS.md').read_text(), original)

    def test_existing_agents_md_with_trailing_newline_restored(self):
        original = '# Existing guidance\n\n'
        (self.root / 'AGENTS.md').write_text(original, encoding='utf8')
        install(self.root)
        uninstall(self.root)
        self.assertEqual((self.root / 'AGENTS.md').read_text(), original)

    def test_crlf_project_instructions_preserve_original_bytes(self):
        original = b'# Rules\r\nKeep existing text.\r\n'
        (self.root / 'AGENTS.md').write_bytes(original)
        install(self.root)
        uninstall(self.root)
        self.assertEqual((self.root / 'AGENTS.md').read_bytes(), original)

    def test_existing_config_is_preserved(self):
        (self.root / '.codex').mkdir()
        config = self.root / '.codex/config.toml'
        original = '[agents]\nmax_concurrent_threads_per_session = 2\n'
        config.write_text(original, encoding='utf8')
        install(self.root)
        self.assertEqual(config.read_text(), original)
        self.assertEqual((self.root / '.forgequorum/config.example.toml').read_text(), CONFIG)
        uninstall(self.root)
        self.assertEqual(config.read_text(), original)

    def test_refuse_unmanaged_conflict_before_any_write(self):
        (self.root / '.codex/agents').mkdir(parents=True)
        path = self.root / '.codex/agents/architect.toml'
        path.write_text('my settings', encoding='utf8')
        with self.assertRaises(InstallError):
            install(self.root)
        self.assertEqual(path.read_text(), 'my settings')
        self.assertFalse((self.root / '.forgequorum').exists())

    def test_refuse_edited_managed_file_on_reinstall(self):
        install(self.root)
        path = self.root / '.codex/agents/architect.toml'
        path.write_text(path.read_text() + '\n# my edit', encoding='utf8')
        with self.assertRaisesRegex(InstallError, 'was edited'):
            install(self.root)
        self.assertTrue(path.exists())

    def test_partial_uninstall_preserves_user_modified_file(self):
        install(self.root)
        path = self.root / '.codex/agents/architect.toml'
        path.write_text(path.read_text() + '\n# my edit', encoding='utf8')
        count, output = uninstall(self.root)
        self.assertGreater(count, 0)
        self.assertTrue(path.exists())
        self.assertTrue(any('KEEP (modified)' in line for line in output))
        manifest = json.loads((self.root / '.forgequorum/manifest.json').read_text())
        self.assertEqual(list(manifest['managed_files']), ['.codex/agents/architect.toml'])

    def test_uninstall_only_own_files(self):
        (self.root / 'KEEP.txt').write_text('untouched', encoding='utf8')
        install(self.root)
        uninstall(self.root)
        self.assertEqual((self.root / 'KEEP.txt').read_text(), 'untouched')
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertFalse((self.root / '.forgequorum/manifest.json').exists())
        self.assertFalse((self.root / '.codex/config.toml').exists())

    def test_toml_all_agents_are_valid(self):
        self.assertGreaterEqual(len(AGENTS), 50)
        self.assertGreaterEqual(len(SKILLS), 30)
        self.assertEqual(len(set(a.name for a in AGENTS)), len(AGENTS))
        self.assertEqual(len(set(s.name for s in SKILLS)), len(SKILLS))
        for name, content in payload().items():
            if name.endswith('.toml'):
                parsed = tomllib.loads(content)
                self.assertEqual(parsed['name'], Path(name).stem)
                self.assertGreater(len(parsed['developer_instructions']), 150)
            if name.endswith('SKILL.md'):
                self.assertTrue(content.startswith('---\nname: '))
                self.assertIn('## Done when', content)

    def test_invalid_marker_not_overwritten(self):
        (self.root / 'AGENTS.md').write_text(AGENTS_BLOCK.replace('Never reveal', 'Always reveal'), encoding='utf8')
        with self.assertRaises(InstallError):
            plan_install(self.root)

    def test_symlink_is_not_followed(self):
        out = self.root / 'outside'
        out.mkdir()
        try:
            (self.root / '.codex').symlink_to(out, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Creating symlinks is not permitted on this platform')
        with self.assertRaises(InstallError):
            install(self.root)
        self.assertEqual(list(out.iterdir()), [])


if __name__ == '__main__':
    unittest.main()

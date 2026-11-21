"""Plugin distribution, deterministic verification and privacy checkpoint tests."""
from __future__ import annotations

import contextlib
from io import StringIO
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from forgequorum.cli import main
from forgequorum.quality import verification_plan, run_verification
from forgequorum.registry import AGENTS, SKILLS, VERSION, skill_markdown
from forgequorum.session import context_summary, create_checkpoint

REPO = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def test_portable_plugin_manifest(self):
        plugin = json.loads((REPO / 'plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(plugin['name'], 'forgequorum')
        self.assertEqual(plugin['version'], VERSION)
        self.assertIn('agent-plugins.org', plugin['$schema'])
        self.assertNotIn('hooks', plugin)
        self.assertNotIn('hooks', plugin.get('extensions', {}).get('com.openai', {}))
        self.assertEqual(plugin['license'], 'MIT')

    def test_marketplace_and_package_roots(self):
        catalog = json.loads((REPO / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog['plugins'][0]['name'], 'forgequorum')
        self.assertEqual(catalog['plugins'][0]['source']['path'], './')
        self.assertTrue((REPO/'README.md').is_file())

    def test_exported_skills_are_current_and_unique(self):
        self.assertEqual(len(AGENTS), 52)
        self.assertEqual(len(SKILLS), 39)
        paths = {REPO / 'skills' / s.name / 'SKILL.md' for s in SKILLS}
        self.assertEqual(len(paths), len(SKILLS))
        for skill in SKILLS:
            with self.subTest(name=skill.name):
                content = (REPO/'skills'/skill.name/'SKILL.md').read_text(encoding='utf-8')
                self.assertEqual(content, skill_markdown(skill))
                self.assertIn('## Done when', content)

    def test_public_docs_only_link_to_our_own_github_repository(self):
        """Public docs describe our product without advertising other projects."""
        docs = [REPO / name for name in ('README.md', 'README.en.md', 'CHANGELOG.md', 'ROADMAP.md')]
        docs.extend((REPO / 'docs').rglob('*.md'))
        for path in docs:
            with self.subTest(path=str(path.relative_to(REPO))):
                body = path.read_text(encoding='utf-8')
                refs = re.findall(r'https?://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)', body)
                for owner, repo in refs:
                    self.assertEqual((owner.lower(), repo.lower().removesuffix('.git')),
                                     ('dizzyz7', 'forge-quorum'))
        self.assertTrue((REPO / 'docs/CAPABILITIES.md').exists())

    def test_codex_ui_metadata(self):
        for name in ('route-task','verification-loop','context-checkpoint','test-driven-loop'):
            content = (REPO/'skills'/name/'agents/openai.yaml').read_text(encoding='utf-8')
            self.assertIn('interface:', content)
            self.assertIn('short_description:', content)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def touch(self, name: str, content: str = ''):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def test_read_only_verification_plan(self):
        self.touch('go.mod', 'module example.com/test')
        plan = verification_plan(self.root)
        self.assertFalse(plan['executed'])
        self.assertEqual(plan['gates'][0]['argv'], ['go','test','./...'])
        self.assertFalse((self.root/'.forgequorum').exists())
        with patch('forgequorum.quality.subprocess.run') as run:
            run_verification(self.root)
            run.assert_not_called()

    def test_run_verification_is_explicit(self):
        self.touch('go.mod')
        fake = type('Response', (), {'returncode': 0})()
        with patch('forgequorum.quality.shutil.which', return_value='/bin/go'):
            with patch('forgequorum.quality.subprocess.run', return_value=fake) as run:
                report = run_verification(self.root, run=True, timeout=12)
        self.assertTrue(report['ok'])
        self.assertEqual(run.call_args.kwargs['timeout'], 12)
        self.assertEqual(run.call_args.args[0], ['go','test','./...'])
        self.assertFalse(run.call_args.kwargs.get('shell', False))

    def test_json_scripts_are_not_executed_during_discovery(self):
        self.touch('package.json', json.dumps({'scripts':{'test':'echo do_not_run'}}))
        self.touch('pnpm-lock.yaml')
        with patch('forgequorum.quality.subprocess.run') as run:
            plan = verification_plan(self.root)
            run.assert_not_called()
        self.assertIn(['pnpm','run','test'], [g['argv'] for g in plan['gates']])

    def test_malformed_or_symlinked_package_json_ignored(self):
        self.touch('package.json', '{broken')
        self.assertEqual(verification_plan(self.root)['planned'], 0)
        (self.root/'package.json').unlink()
        outside = self.root/'other.json'
        outside.write_text('{"scripts":{"test":"yes"}}')
        try:
            (self.root/'package.json').symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink unavailable')
        self.assertEqual(verification_plan(self.root)['planned'], 0)

    def test_exit_code_for_no_gates_and_failure(self):
        self.assertFalse(run_verification(self.root, run=True)['ok'])
        self.touch('Cargo.toml')
        with patch('forgequorum.quality.shutil.which', return_value='/bin/cargo'):
            with patch('forgequorum.quality.subprocess.run', return_value=type('Proc',(),{'returncode':1})()):
                self.assertEqual(run_verification(self.root, run=True)['results'][0]['status'], 'failed')

    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            run_verification(self.root, timeout=0)
        with self.assertRaises(ValueError):
            run_verification(self.root, timeout=1801)

    def test_context_is_filename_only(self):
        self.touch('go.mod', 'secret-access-token=NEVER_LOG_THIS')
        ctx = context_summary(self.root)
        self.assertNotIn('NEVER_LOG_THIS', str(ctx))
        self.assertEqual(ctx['recommended_profile'], 'go')
        self.assertFalse((self.root/'.forgequorum').exists())

    def test_checkpoint_opt_in_and_ignored(self):
        self.touch('go.mod')
        checkpoint = create_checkpoint(self.root, 'finished routing tests')
        content = json.loads(checkpoint.read_text())
        self.assertEqual(content['note'], 'finished routing tests')
        self.assertNotIn('secret', str(content))
        self.assertEqual((self.root/'.forgequorum/.gitignore').read_text(), '*\n!/.gitignore\n')
        self.assertNotEqual(checkpoint, create_checkpoint(self.root))

    def test_checkpoint_refuses_symlink(self):
        try:
            (self.root/'.forgequorum').symlink_to(self.root)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink unavailable')
        with self.assertRaises(ValueError):
            create_checkpoint(self.root)

    def test_cli_verify_json_and_context(self):
        self.touch('go.mod')
        for command in ('verify','context'):
            output = StringIO()
            with contextlib.redirect_stdout(output):
                rc = main([command, '--target', str(self.root), '--json'])
            self.assertEqual(rc,0)
            self.assertTrue(json.loads(output.getvalue()))

    def test_cli_hook_context_no_transcript(self):
        self.touch('Cargo.toml')
        fake_input = StringIO(json.dumps({'cwd':str(self.root), 'transcript_path':'secret-path', 'prompt':'secret-prompt'}))
        output = StringIO()
        with patch('forgequorum.cli.sys.stdin', fake_input), contextlib.redirect_stdout(output):
            self.assertEqual(main(['hook-context']), 0)
        result = json.loads(output.getvalue())
        message = result['hookSpecificOutput']['additionalContext']
        self.assertIn('rust', message)
        self.assertNotIn('secret-path', message)
        self.assertNotIn('secret-prompt', message)

    def test_cli_bad_hook_gracefully_degrades(self):
        with patch('forgequorum.cli.sys.stdin', StringIO('{bad')):
            with contextlib.redirect_stderr(StringIO()):
                self.assertEqual(main(['hook-context']), 0)

if __name__ == '__main__':
    unittest.main()

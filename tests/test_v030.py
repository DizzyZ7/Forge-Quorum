"""Polyglot stack inspection, routing, and safe installation regression tests."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from forgequorum.cli import check, install, load_manifest, main, status, uninstall
from forgequorum.profiles import profile_names, selections
from forgequorum.registry import AGENTS, SKILLS, payload
from forgequorum.routing import recommend
from forgequorum.stack import detect_stack


class PolyglotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def touch(self, name: str, content: str = ''):
        f = self.root / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding='utf8')

    def test_catalog_uniqueness_and_validity(self):
        self.assertEqual(len(AGENTS), 52)
        self.assertEqual(len(SKILLS), 34)
        self.assertEqual(len(set(a.name for a in AGENTS)), 52)
        self.assertEqual(len(set(s.name for s in SKILLS)), 34)
        self.assertIn('go-engineer', {a.name for a in AGENTS})
        self.assertIn('build-mobile', {s.name for s in SKILLS})
        self.assertEqual(len(payload()), 86)

    def test_supported_profiles_only_reference_existing_catalog(self):
        for name in profile_names():
            with self.subTest(profile=name):
                agents, skills = selections(name, tuple(a.name for a in AGENTS), tuple(s.name for s in SKILLS))
                self.assertTrue(agents)
                self.assertIn('route-task', skills)
                self.assertTrue(skills)

    def test_stack_heuristics(self):
        fixtures = (
            ('pyproject.toml','python'), ('go.mod','go'), ('Cargo.toml','rust'),
            ('pom.xml','java'), ('build.gradle.kts','kotlin'), ('demo.csproj','dotnet'),
            ('composer.json','php'), ('Gemfile','ruby'), ('Package.swift','mobile'),
            ('pubspec.yaml','mobile'), ('project.godot','games'),
            ('main.tf','cloud'), ('project.R','scientific'), ('app.ex','functional'),
            ('CMakeLists.txt','systems'), ('main.cpp','systems'), ('src/main.go','go'),
        )
        for filename, expected in fixtures:
            with self.subTest(filename=filename):
                isolated = self.root / str(len(list(self.root.iterdir())))
                isolated.mkdir()
                file = isolated / filename
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('', encoding='utf8')
                self.assertEqual(detect_stack(isolated)['recommended_profile'], expected)

    def test_web_tsx_and_node_without_ui(self):
        self.touch('package.json')
        self.touch('src/api.ts')
        self.assertEqual(detect_stack(self.root)['recommended_profile'], 'node')
        self.touch('src/App.tsx')
        self.assertEqual(detect_stack(self.root)['recommended_profile'], 'web')

    def test_multiple_backend_languages(self):
        self.touch('go.mod')
        self.touch('pyproject.toml')
        self.assertEqual(detect_stack(self.root)['recommended_profile'], 'backend')

    def test_ignored_generated_and_symlink_files(self):
        self.touch('node_modules/hidden.rs')
        self.touch('.venv/hidden.go')
        self.touch('app.py')
        report = detect_stack(self.root)
        self.assertEqual([l['name'] for l in report['languages']], ['python'])
        out_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(out_tmp.cleanup)
        external = Path(out_tmp.name)
        (external/'skip.rs').write_text('')
        link = self.root / 'vendor-link'
        try:
            link.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        report2 = detect_stack(self.root)
        self.assertNotIn('rust', [l['name'] for l in report2['languages']])

    def test_scan_is_bounded_and_never_reads_source(self):
        self.touch('passwords.ts', 'SENSITIVE TOP SECRET')
        self.touch('another.py')
        report = detect_stack(self.root, max_files=1)
        self.assertTrue(report['scan_truncated'])
        self.assertEqual(report['files_inspected'], 1)
        self.assertNotIn('SENSITIVE', json.dumps(report))
        with self.assertRaises(ValueError):
            detect_stack(self.root, max_files=0)

    def test_auto_install_and_manifest_resolve(self):
        self.touch('Cargo.toml')
        changed, _ = install(self.root, profile='auto')
        self.assertGreater(changed, 0)
        m = load_manifest(self.root)
        self.assertEqual(m['profile'], 'rust')
        self.assertTrue(status(self.root)['ok'])
        self.assertEqual(install(self.root, profile='auto')[0], 0)
        count, _ = uninstall(self.root)
        self.assertGreater(count, 0)
        self.assertTrue((self.root/'Cargo.toml').exists())

    def test_compatibility_v02_profile_update(self):
        install(self.root, profile='java')
        first = load_manifest(self.root)
        first['version'] = '0.2.1'
        (self.root/'.forgequorum/manifest.json').write_text(json.dumps(first))
        self.assertTrue(status(self.root)['ok'])
        install(self.root)
        self.assertTrue(status(self.root)['ok'])

    def test_explicit_stack_routing(self):
        scenarios = (
            ('Implement a Kotlin Ktor API','ship-jvm-service','kotlin-engineer'),
            ('Build a Java Spring Boot service','ship-jvm-service','java-engineer'),
            ('Build a Golang gRPC service','ship-go-service','go-engineer'),
            ('Build a Rust Tokio service','ship-rust-crate','rust-engineer'),
            ('Create an ASP.NET Core API','ship-dotnet','dotnet-engineer'),
            ('Сделай Flutter мобильное приложение','build-mobile','flutter-engineer'),
            ('Develop Android Jetpack Compose UI','build-mobile','android-engineer'),
            ('Develop SwiftUI for iOS','build-mobile','swift-engineer'),
            ('Build an Electron desktop app','build-desktop','desktop-engineer'),
            ('Create gameplay in Unity','gameplay-iteration','game-engineer'),
            ('Create a data pipeline with Airflow','data-pipeline','data-engineer'),
            ('Prepare a Terraform infrastructure plan','infrastructure-plan','terraform-engineer'),
            ('Build an ML RAG evaluation pipeline','ml-lifecycle','ml-engineer'),
        )
        for task, skill, agent in scenarios:
            with self.subTest(task=task):
                decision = recommend(task)
                self.assertEqual(decision['skill'], skill)
                self.assertEqual(decision['agents'][0], agent)
                self.assertLessEqual(len(decision['agents']), 3)

    def test_generic_api_uses_explicit_language(self):
        decision = recommend('Create PHP Laravel API endpoint')
        self.assertIn('php-engineer', decision['agents'])
        self.assertNotIn('python-backend', decision['agents'])
        decision = recommend('Create a Node.js backend API endpoint')
        self.assertIn('node-backend', decision['agents'])
        self.assertNotIn('python-backend', decision['agents'])

    def test_detected_stack_used_in_generic_route(self):
        self.touch('go.mod')
        decision = recommend('Add an API endpoint', stack_report=detect_stack(self.root))
        self.assertIn('go-engineer', decision['agents'])
        self.assertNotIn('python-backend', decision['agents'])

    def test_cli_inspect_and_auto_recommend(self):
        self.touch('Cargo.toml')
        for argv in (["inspect", "--target", str(self.root), "--json"],
                     ["recommend", "Fix error", "--target", str(self.root), "--profile", "auto", "--json"]):
            out = StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(argv)
            self.assertEqual(rc, 0)
            report = json.loads(out.getvalue())
            self.assertTrue(report)
        self.assertEqual(report['profile'], 'rust')
        self.assertIn('stack', report)

    def test_auto_profile_needs_target_for_recommend(self):
        with contextlib.redirect_stderr(StringIO()):
            self.assertEqual(main(['recommend','Test me','--profile','auto']), 1)

    def test_non_python_install_roundtrip(self):
        self.touch('index.html')
        self.touch('src/App.tsx')
        self.touch('package.json')
        with contextlib.redirect_stdout(StringIO()):
            self.assertEqual(main(['init','--target',str(self.root),'--profile','auto','--dry-run']),0)
        self.assertFalse((self.root/'.forgequorum').exists())
        with contextlib.redirect_stdout(StringIO()):
            self.assertEqual(main(['init','--target',str(self.root),'--profile','auto']),0)
        self.assertEqual(status(self.root)['profile'],'web')
        self.assertTrue((self.root/'src/App.tsx').exists())
        with contextlib.redirect_stdout(StringIO()):
            self.assertEqual(main(['uninstall','--target',str(self.root)]),0)
        self.assertTrue((self.root/'package.json').exists())

if __name__ == '__main__':
    unittest.main()

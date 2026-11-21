"""Bounded, offline stack detection using filenames only (never executes project code)."""
from __future__ import annotations

from collections import Counter, defaultdict
import os
from pathlib import Path

IGNORED_DIRS = frozenset({'.forgequorum', '.git', '.hg', '.svn', '.venv', 'venv', 'node_modules', 'vendor',
                          'dist', 'build', 'target', '__pycache__', '.next', '.nuxt',
                          '.tox', '.mypy_cache', '.pytest_cache', 'coverage', '.gradle',
                          '.dart_tool', '.idea', '.vscode', 'Pods', 'DerivedData', '.turbo'})
EXTENSIONS: dict[str, str] = {
    '.py':'python', '.pyi':'python', '.ts':'typescript', '.tsx':'typescript',
    '.js':'javascript', '.jsx':'javascript', '.mjs':'javascript', '.cjs':'javascript',
    '.java':'java', '.kt':'kotlin', '.kts':'kotlin', '.go':'go', '.rs':'rust',
    '.cs':'csharp', '.fs':'fsharp', '.c':'c', '.h':'c', '.cpp':'cpp', '.cc':'cpp',
    '.cxx':'cpp', '.hpp':'cpp', '.php':'php', '.rb':'ruby', '.swift':'swift',
    '.dart':'dart', '.scala':'scala', '.ex':'elixir', '.exs':'elixir',
    '.erl':'erlang', '.hs':'haskell', '.r':'r', '.jl':'julia', '.m':'matlab',
    '.gd':'gdscript', '.sh':'shell', '.ps1':'powershell', '.sql':'sql',
    '.tf':'terraform', '.tfvars':'terraform', '.ipynb':'notebooks',
}
MARKERS: dict[str, str] = {
    'pyproject.toml':'python', 'requirements.txt':'python', 'poetry.lock':'python',
    'pipfile':'python', 'uv.lock':'python', 'go.mod':'go', 'cargo.toml':'rust',
    'pom.xml':'java', 'build.gradle':'java', 'build.gradle.kts':'kotlin',
    'settings.gradle.kts':'kotlin', 'package.json':'javascript', 'pnpm-lock.yaml':'javascript',
    'package-lock.json':'javascript', 'yarn.lock':'javascript', 'composer.json':'php',
    'gemfile':'ruby', 'gemfile.lock':'ruby', 'pubspec.yaml':'dart',
    'package.swift':'swift', 'cmakelists.txt':'cpp', 'makefile':'c',
    'mix.exs':'elixir', 'rebar.config':'erlang', 'stack.yaml':'haskell',
    'project.toml':'julia', 'renv.lock':'r', 'project.godot':'gdscript',
    'terraform.lock.hcl':'terraform',
}
FRONTEND_MARKERS = ('vite.config.', 'next.config.', 'nuxt.config.', 'angular.json',
                    'svelte.config.', 'astro.config.', 'index.html')
MOBILE_MARKERS = ('androidmanifest.xml', 'pubspec.yaml', '.xcodeproj', '.xcworkspace')
GAME_MARKERS = ('project.godot', '.uproject', '.unity')


def detect_stack(root: Path, max_files: int = 5000) -> dict:
    """Read directory entries only; skip symlinks and build artifacts; make no guesses about executability."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f'Target must be a non-symlink directory: {root}')
    if not 1 <= max_files <= 50000:
        raise ValueError('max_files must be between 1 and 50000')
    scores: Counter[str] = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)
    seen, truncated = 0, False
    flags = {'frontend':False, 'mobile':False, 'game':False, 'kubernetes':False}
    root = root.resolve()
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS and not (Path(base) / d).is_symlink())
        for filename in sorted(files):
            path = Path(base) / filename
            if path.is_symlink():
                continue
            if seen >= max_files:
                truncated = True
                break
            seen += 1
            relative = path.relative_to(root).as_posix()
            low = filename.casefold()
            suffix = path.suffix.casefold()
            language = MARKERS.get(low) or EXTENSIONS.get(suffix)
            if suffix == '.csproj' or suffix == '.sln':
                language = 'csharp'
            if suffix in ('.xcodeproj', '.xcworkspace') or low.endswith('androidmanifest.xml'):
                flags['mobile'] = True
            if suffix in ('.uproject', '.unity') or low == 'project.godot':
                flags['game'] = True
            if low.startswith(FRONTEND_MARKERS) or low in ('index.html', 'angular.json') or suffix in ('.tsx', '.jsx'):
                flags['frontend'] = True
            if low in ('chart.yaml', 'kustomization.yaml', 'kustomization.yml'):
                flags['kubernetes'] = True
            if language:
                scores[language] += 6 if low in MARKERS or suffix in ('.csproj', '.sln') else 1
                if len(evidence[language]) < 4:
                    evidence[language].append(relative)
        if truncated:
            break
    ordered = sorted(scores, key=lambda n: (-scores[n], n))
    set_lang = set(scores)
    if flags['game']:
        profile = 'games'
    elif flags['mobile'] or 'dart' in set_lang:
        profile = 'mobile'
    elif flags['kubernetes'] and not set_lang:
        profile = 'cloud'
    elif 'terraform' in set_lang and len(set_lang) == 1:
        profile = 'cloud'
    elif flags['frontend'] and set_lang.intersection({'typescript','javascript','python','php','ruby'}):
        profile = 'web'
    elif {'javascript','typescript'} & set_lang and len(set_lang - {'javascript','typescript','sql','shell'}) == 0:
        profile = 'node'
    elif len(set_lang - {'sql','shell','powershell'}) >= 2:
        profile = 'backend' if set_lang <= {'python','go','java','kotlin','csharp','javascript','typescript','sql','shell','powershell'} else 'full'
    else:
        names = {'python':'python','java':'java','kotlin':'kotlin','go':'go','rust':'rust',
                 'csharp':'dotnet','c':'systems','cpp':'systems','php':'php','ruby':'ruby',
                 'swift':'mobile','dart':'mobile','gdscript':'games','r':'scientific',
                 'julia':'scientific','matlab':'scientific','scala':'functional',
                 'fsharp':'functional','elixir':'functional','erlang':'functional',
                 'haskell':'functional','terraform':'cloud','sql':'data',
                 'notebooks':'ml','powershell':'infra','shell':'infra'}
        profile = names.get(ordered[0], 'full') if ordered else 'full'
    return {
        'recommended_profile': profile,
        'languages': [{'name': name, 'score': scores[name], 'evidence': evidence[name]} for name in ordered],
        'markers': flags,
        'files_inspected': seen,
        'scan_truncated': truncated,
        'note': 'Filename-only heuristics; no source content was read and no commands were executed.',
    }

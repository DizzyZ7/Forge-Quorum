"""Deterministic, offline task recommendations; no model or agent execution."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .profiles import selections
from .registry import AGENTS, SKILLS


@dataclass(frozen=True)
class Rule:
    skill: str
    agents: tuple[str, ...]
    signals: tuple[str, ...]
    rationale: str


# Specific domain rules precede generic API/feature rules when intent overlaps.
RULES: tuple[Rule, ...] = (
    Rule('build-mobile', ('android-engineer','swift-engineer','flutter-engineer','mobile-qa'),
         ('android','ios','swiftui','jetpack','flutter','мобильн','андроид','айфон','apk','ipa'), 'Mobile lifecycle and device coverage'),
    Rule('build-desktop', ('desktop-engineer','systems-engineer','qa-automation'),
         ('electron','tauri','pyqt','qml','qt widgets','win32','wpf','winui','desktop app','десктоп','настольн','windows overlay'), 'Desktop integrations and packaging'),
    Rule('gameplay-iteration', ('game-engineer','qa-automation','performance-engineer'),
         ('unity','unreal','godot','gameplay','game loop','геймплей','игровой движок','игру на движке'), 'Game runtime and iteration'),
    Rule('ml-lifecycle', ('ml-engineer','mlops-engineer','data-engineer'),
         ('pytorch','tensorflow','machine learning','rag','embedding','модель машинного','машинное обучение','нейросет','fine-tun','инференс','llm'), 'Evaluation-first ML delivery'),
    Rule('data-pipeline', ('data-engineer','database-engineer','integration-engineer'),
         ('etl','elt','airflow','spark','dbt','data pipeline','kafka stream','датапайплайн','поток данн'), 'Reliable data ingestion and replay'),
    Rule('infrastructure-plan', ('terraform-engineer','cloud-architect','security-auditor'),
         ('terraform','opentofu','pulumi','infrastructure as code','iac','инфраструктуру как код'), 'Infrastructure plan before apply'),
    Rule('kubernetes-operations', ('kubernetes-engineer','sre-engineer','devops-engineer'),
         ('kubernetes','k8s','helm chart','kustomize','кубернетес','kubeconfig'), 'Safe cluster configuration and rollout'),
    Rule('ship-jvm-service', ('java-engineer','kotlin-engineer','database-engineer'),
         ('spring boot','spring framework','ktor','quarkus','micronaut','maven','gradle','спринг'), 'JVM application contracts and concurrency'),
    Rule('ship-go-service', ('go-engineer','api-designer','test-engineer'),
         ('golang','go.mod','go service','go microservice','go grpc','на go ','на golang'), 'Go cancellation and resource ownership'),
    Rule('ship-rust-crate', ('rust-engineer','systems-engineer','reviewer'),
         ('rust','cargo','tokio','axum','actix','ржавый язык'), 'Rust ownership and soundness'),
    Rule('ship-dotnet', ('dotnet-engineer','api-designer','test-engineer'),
         ('asp.net','dotnet','.net','c#','blazor','nuget','ef core'), '.NET lifetimes and contracts'),
    Rule('systems-safety', ('cpp-engineer','embedded-engineer','reviewer'),
         ('c++','cmake','firmware','rtos','embedded','прошивк','микроконтроллер','driver','драйвер'), 'Native memory and timing safety'),
    Rule('concurrency-review', ('systems-engineer','debugger','reviewer'),
         ('deadlock','race condition','data race','thread safety','гонк потоков','дедлок','взаимоблокировк'), 'Parallel safety and ordering'),
    Rule('cross-platform-release', ('desktop-engineer','release-manager','qa-automation'),
         ('msix','appimage','dmg','msi','app store','play store','cross-platform release','кроссплатформенн релиз'), 'Cross-platform delivery checks'),
    Rule('privacy-review', ('privacy-engineer','security-auditor','reviewer'),
         ('gdpr','consent','personal data','data retention','персональн данн','удаление данных пользователя'), 'Privacy obligations and data flows'),
    Rule('accessibility-audit', ('accessibility-engineer','frontend-engineer','qa-automation'),
         ('accessibility','wcag','screen reader','aria-','a11y','доступност интерфейс','скринридер'), 'Accessible interaction verification'),
    Rule('security-gate', ('security-auditor','threat-modeler','reviewer'),
         ('security','vulnerab','auth','xss','csrf','injection','secret','audit',
          'безопас','уязвим','авторизац','пентест','инъекц'), 'Security boundaries and abuse cases'),
    Rule('incident-triage', ('debugger','devops-engineer','observability-engineer'),
         ('incident','outage','production down','downtime','crash','инцидент',
          'авария','недоступ','падает прод','сбой'), 'Operational incident response'),
    Rule('data-migration', ('database-engineer','python-backend','reviewer'),
         ('migration','migrate','schema','backfill','postgres','sql',
          'миграц','схем','таблиц','баз данн'), 'Database correctness and migrations'),
    Rule('performance-lab', ('performance-engineer','repo-explorer','test-engineer'),
         ('performance','latency','slow','throughput','optimiz','memory leak',
          'ускор','оптимиз','медлен','производительн','нагрузк'), 'Measured performance tuning'),
    Rule('automation-hardening', ('integration-engineer','python-backend','test-engineer'),
         ('telegram','redis','webhook','queue','retry','worker','bot','идемпотент',
          'очеред','бот','вебхук','воркер','повторн'), 'Reliable asynchronous automation'),
    Rule('ship-api', ('api-designer','python-backend','test-engineer'),
         ('fastapi','endpoint','rest','openapi','graphql','backend','api',
          'апи','эндпоинт','бэкенд','интеграц'), 'Stable API and integration contracts'),
    Rule('repair-bug', ('debugger','test-engineer','reviewer'),
         ('bug','fix','broken','regression','error','exception','ошибк','баг',
          'почин','исправ','сломал','не работает'), 'Root cause and regression protection'),
    Rule('release-ready', ('release-manager','devops-engineer','reviewer'),
         ('release','deploy','publish','rollback','ci/cd','релиз','деплой',
          'публикац','выкат','откат'), 'Release gates and rollback readiness'),
    Rule('deep-review', ('reviewer','security-auditor','test-engineer'),
         ('review','pull request','code review','ревью','провер','аудит кода'), 'Independent review and verified findings'),
    Rule('repo-onboarding', ('repo-explorer','architect','docs-writer'),
         ('onboarding','understand repo','new repo','architecture map',
          'изучи репо','разберись в репо','структур проект'), 'Repository discovery and context'),
    Rule('build-feature', ('frontend-engineer','product-analyst','test-engineer'),
         ('frontend','react','vue','typescript','css','ui','ux','responsive',
          'интерфейс','верстк','дизайн','адаптив'), 'Client-side UI, UX and accessibility'),
    Rule('polyglot-feature', ('architect','node-backend','test-engineer'),
         ('monorepo','polyglot','multiple languages','microservices','монорепо','несколько языков','мультистек'), 'Cross-language consistency'),
    Rule('build-feature', ('planner','architect','test-engineer'),
         ('feature','implement','build','create','develop','add','фич',
          'разработ','созда','добав','реализ'), 'Feature delivery and verification'),
)

# Whole tokens or precise ecosystem phrases. A substring of "javascript" must not count as "java".
LANGUAGE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('node-backend', (r'\bnode(?:\.js|js)?\b',r'\bnestjs\b',r'\bexpressjs\b',r'\btypescript\b',r'\bjavascript\b',r'\bnextjs\b')),
    ('java-engineer', (r'\bjava\b',r'\bspring\b',r'\bquarkus\b',r'\bmaven\b')),
    ('kotlin-engineer', (r'\bkotlin\b',r'\bktor\b',r'\bкорутин\w*')),
    ('go-engineer', (r'\bgolang\b',r'\bgo\.mod\b',r'\bon go\b',r'\bна go\b')),
    ('rust-engineer', (r'\brust\b',r'\bcargo\b',r'\btokio\b')),
    ('dotnet-engineer', (r'\basp\.net\b',r'(?<!\w)\.net\b',r'\bc#',r'\bblazor\b',r'\bnuget\b')),
    ('cpp-engineer', (r'\bc\+\+',r'\bcmake\b',r'\bclang\b',r'\bmsvc\b')),
    ('php-engineer', (r'\bphp\b',r'\blaravel\b',r'\bsymfony\b')),
    ('ruby-engineer', (r'\bruby\b',r'\brails\b',r'\bbundler\b')),
    ('swift-engineer', (r'\bswift\b',r'\bswiftui\b',r'\bxcode\b')),
    ('android-engineer', (r'\bandroid\b',r'\bjetpack\b',r'\bандроид\b')),
    ('flutter-engineer', (r'\bflutter\b',r'\bdart\b')),
    ('game-engineer', (r'\bunity\b',r'\bunreal\b',r'\bgodot\b')),
    ('python-backend', (r'\bpython\b',r'\bfastapi\b',r'\bdjango\b',r'\bпитон\b')),
    ('data-engineer', (r'\bspark\b',r'\bairflow\b',r'\bdbt\b')),
)

STACK_TO_AGENT = {
    'python':'python-backend','typescript':'node-backend','javascript':'node-backend',
    'java':'java-engineer','kotlin':'kotlin-engineer','go':'go-engineer','rust':'rust-engineer',
    'csharp':'dotnet-engineer','c':'cpp-engineer','cpp':'cpp-engineer',
    'php':'php-engineer','ruby':'ruby-engineer','swift':'swift-engineer',
    'dart':'flutter-engineer','scala':'functional-engineer','elixir':'functional-engineer',
    'haskell':'functional-engineer','r':'scientific-engineer','julia':'scientific-engineer',
    'matlab':'scientific-engineer','gdscript':'game-engineer',
}


def inferred_specialist(task: str, stack_report: dict | None) -> str | None:
    for name, patterns in LANGUAGE_PATTERNS:
        if any(re.search(pat, task, re.IGNORECASE) for pat in patterns):
            return name
    if stack_report:
        for lang in stack_report.get('languages', []):
            name = STACK_TO_AGENT.get(lang['name'])
            if name:
                return name
    return None


def recommend(task: str, profile: str = 'full', max_agents: int = 3, stack_report: dict | None = None) -> dict:
    """Return reproducible suggestions, optionally informed by filename-only project evidence."""
    if not task.strip():
        raise ValueError('Task description cannot be empty')
    if not 1 <= max_agents <= 6:
        raise ValueError('max_agents must be between 1 and 6')
    available_agents, available_skills = selections(
        profile, tuple(a.name for a in AGENTS), tuple(s.name for s in SKILLS))
    normalized = re.sub(r'\s+', ' ', task.casefold())
    ranked = []
    for index, rule in enumerate(RULES):
        if rule.skill not in available_skills:
            continue
        signals = sorted({s for s in rule.signals if s in normalized}, key=lambda s: (-len(s), s))
        if signals:
            ranked.append((-len(signals), index, rule, signals))
    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1]))
        _, _, rule, signals = ranked[0]
        skill, rationale = rule.skill, rule.rationale
        candidates = list(rule.agents)
    else:
        skill, rationale = 'route-task', 'General task routing (no specific keyword match)'
        signals, candidates = [], ['planner','repo-explorer','reviewer']
    specialist = inferred_specialist(normalized, stack_report)
    if specialist in available_agents:
        if skill == 'build-mobile' and specialist in ('android-engineer','swift-engineer','flutter-engineer'):
            candidates = [specialist, 'mobile-qa', 'accessibility-engineer']
        elif skill == 'ship-jvm-service' and specialist in ('java-engineer','kotlin-engineer'):
            candidates = [specialist, 'api-designer', 'test-engineer']
        elif skill in ('ship-api','automation-hardening','data-migration','build-feature','polyglot-feature','repair-bug'):
            if specialist not in candidates:
                if skill == 'build-feature':
                    candidates = ['planner', specialist, 'test-engineer']
                elif skill == 'repair-bug':
                    candidates = ['debugger', specialist, 'test-engineer']
                else:
                    candidates = [name if name != 'python-backend' else specialist for name in candidates]
                    if specialist not in candidates:
                        candidates.insert(1, specialist)
    team = [name for name in dict.fromkeys(candidates) if name in available_agents][:max_agents]
    if not team:
        team = [a.name for a in AGENTS if a.name in available_agents][:max_agents]
    prompt = f'${skill} {task.strip()}'
    return {
        'profile': profile, 'skill': skill, 'agents': team,
        'rationale': rationale, 'matched_signals': signals,
        'stack_specialist': specialist if specialist in available_agents else None,
        'prompt': prompt,
        'note': 'Offline heuristic suggestion; no agents were run. Codex owns actual delegation.',
    }

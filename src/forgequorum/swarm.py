"""Opt-in Codex runs in isolated, reviewable Git worktrees.

This is a local orchestration foundation, not an autonomous deployment or merge
engine. No project code or AI service is executed by planning/creating a job.
"""
from __future__ import annotations

import json
import os
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from time import monotonic
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from .routing import recommend
from .stack import detect_stack
from .profiles import profile_names

ID = re.compile(r"^[0-9a-f]{12}$")
MAX_TASK = 4000
JOB_FORMAT = 1
MAX_BATCH = 12
MAX_PARALLEL = 4


class SwarmError(ValueError):
    """Recoverable orchestration error with no automatic destructive cleanup."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(directory: Path, *args: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *args], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SwarmError(f"Git is unavailable or timed out: {error}") from error
    if result.returncode:
        # Git errors may include private URLs; do not print raw stderr to CLI.
        raise SwarmError(f"Git operation failed ({args[0]}; exit={result.returncode}). Check repository state with git status.")
    return result.stdout.strip()


def _repo(target: Path) -> tuple[Path, Path]:
    if not target.is_dir():
        raise SwarmError("Target directory does not exist")
    root = Path(_git(target, "rev-parse", "--show-toplevel")).resolve()
    common = Path(_git(root, "rev-parse", "--git-common-dir"))
    common = (root / common).resolve() if not common.is_absolute() else common.resolve()
    if not common.is_dir():
        raise SwarmError("Cannot locate repository metadata directory")
    return root, common


def _job_dir(common: Path) -> Path:
    directory = common / "forgequorum" / "jobs"
    if directory.is_symlink() or directory.parent.is_symlink():
        raise SwarmError("Refusing symlink in job metadata path")
    return directory


def _workspace_path(root: Path, job_id: str) -> Path:
    if not ID.fullmatch(job_id):
        raise SwarmError("Invalid job ID")
    parent = root.parent / ".forgequorum-worktrees"
    base = parent / root.name
    if parent.is_symlink() or base.is_symlink():
        raise SwarmError("Refusing symlinked workspace storage")
    return base / job_id


def _write_job(common: Path, info: dict) -> None:
    directory = _job_dir(common)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{info['id']}.json"
    if path.is_symlink():
        raise SwarmError("Refusing symlinked job metadata")
    fd, tmp = tempfile.mkstemp(prefix=".fq-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.chmod(tmp, 0o600)
            json.dump(info, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _load_job(root: Path, common: Path, job_id: str) -> dict:
    workspace = _workspace_path(root, job_id)
    file = _job_dir(common) / f"{job_id}.json"
    if file.is_symlink() or not file.is_file():
        raise SwarmError(f"Unknown job: {job_id}")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SwarmError("Damaged job metadata") from error
    if not isinstance(data, dict) or data.get("format") != JOB_FORMAT or data.get("id") != job_id:
        raise SwarmError("Unrecognized job metadata format")
    if data.get("repository") != str(root) or data.get("workspace") != str(workspace):
        raise SwarmError("Job metadata does not match the selected repository")
    if data.get("branch") != f"forgequorum/{job_id}":
        raise SwarmError("Unexpected managed branch")
    return data



@contextmanager
def _exclusive_run(common: Path, job_id: str):
    """Cross-process exclusive job claim; never break abandoned locks automatically."""
    if not ID.fullmatch(job_id):
        raise SwarmError("Invalid job ID")
    directory = _job_dir(common)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / f"{job_id}.lock"
    if lock.is_symlink():
        raise SwarmError("Refusing symlinked run lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise SwarmError(
            "Job is already claimed or has an abandoned run lock; "
            "inspect running processes before manual recovery"
        ) from error
    token = uuid4().hex
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"job_id": job_id, "pid": os.getpid(), "started_at": _now(),
                       "token": token}, handle)
        yield
    finally:
        # Do not delete a lock replaced by another process.
        try:
            if not lock.is_symlink() and json.loads(lock.read_text(encoding="utf-8")).get("token") == token:
                lock.unlink()
        except (OSError, ValueError, AttributeError):
            pass


def _check_runnable(root: Path, common: Path, job_id: str) -> dict:
    job = _load_job(root, common, job_id)
    workspace = Path(job["workspace"])
    if not _registered_workspace(root, workspace) or workspace.is_symlink() or not workspace.is_dir():
        raise SwarmError("Worktree is missing or no longer managed by Git")
    if _git(workspace, "branch", "--show-current") != job["branch"]:
        raise SwarmError("Worktree branch no longer matches the recorded job")
    if job["state"] not in ("prepared", "failed", "timed_out"):
        raise SwarmError("Job is not runnable; completed and running jobs cannot be rerun automatically")
    return job


def run_batch(target: Path, job_ids: list[str], timeout: int = 900,
              max_parallel: int = 2, execute: bool = False,
              reserve_tokens: int = 0, wait_seconds: int = 120) -> dict:
    """Run *independent prepared jobs* with bounded per-invocation concurrency.

    Does not enforce a global token or process budget across different CLI runs.
    """
    if not 30 <= timeout <= 3600:
        raise SwarmError("timeout must be between 30 and 3600 seconds")
    if not 1 <= max_parallel <= MAX_PARALLEL:
        raise SwarmError(f"max_parallel must be between 1 and {MAX_PARALLEL}")
    if not job_ids or len(job_ids) > MAX_BATCH or len(set(job_ids)) != len(job_ids):
        raise SwarmError(f"Specify 1 to {MAX_BATCH} unique job IDs")
    root, common = _repo(target)
    # Validate all jobs before a single model call is permitted.
    for job_id in job_ids:
        if not ID.fullmatch(job_id):
            raise SwarmError(f"Invalid job ID: {job_id}")
        _check_runnable(root, common, job_id)
        if (_job_dir(common) / f"{job_id}.lock").exists():
            raise SwarmError(f"Job is already claimed: {job_id}")

    if not execute:
        return {
            "state": "dry-run", "job_ids": job_ids, "max_parallel": max_parallel,
            "timeout_seconds_per_job": timeout, "execution_authorized": False,
            "notice": "Pass --execute to invoke Codex once for each job. No token or monetary quota is enforced.",
        }

    def _one(job_id: str) -> dict:
        try:
            outcome = execute_job(root, job_id, timeout=timeout, execute=True,
                                  reserve_tokens=reserve_tokens, wait_seconds=wait_seconds)
            return {"id": job_id, "state": outcome["state"],
                    "last_execution": outcome.get("last_execution")}
        except (SwarmError, OSError, ValueError) as exc:
            return {"id": job_id, "state": "error", "error": str(exc)}
        except Exception as exc:
            # A failing worker must not make the batch lose other job results;
            # do not print potentially sensitive exception arguments.
            return {"id": job_id, "state": "error", "error": f"Worker failed: {type(exc).__name__}"}

    results = {}
    with ThreadPoolExecutor(max_workers=min(max_parallel, len(job_ids)),
                            thread_name_prefix="forgequorum") as pool:
        futures = {pool.submit(_one, job_id): job_id for job_id in job_ids}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    ordered = [results[job_id] for job_id in job_ids]
    return {
        "state": "completed" if all(item["state"] == "completed" for item in ordered) else "partial-failure",
        "execution_authorized": True,
        "max_parallel": max_parallel, "jobs": ordered,
        "completed": sum(x["state"] == "completed" for x in ordered),
        "total": len(ordered),
        "notice": "Review every worktree manually; no results have been merged or deployed.",
    }


def review_job(target: Path, job_id: str) -> dict:
    """Read-only evidence summary from Git, not a claim of passing tests."""
    job = inspect_job(target, job_id)
    if not job["registered"] or job["head_sha"] is None:
        raise SwarmError("Cannot review a missing or detached worktree")
    workspace = Path(job["workspace"])
    root, common = _repo(target)
    if _git(workspace, "branch", "--show-current") != job["branch"]:
        raise SwarmError("Unexpected branch; review manually")
    raw = _git(workspace, "diff", "--stat", job["base_sha"], "--")
    return {
        "id": job_id, "branch": job["branch"], "workspace": str(workspace),
        "state": job["state"], "base_sha": job["base_sha"],
        "head_sha": job["head_sha"], "files": job["changes"],
        "modified_entries": len(job["changes"]),
        "tracked_diff_summary": raw[:16000],
        "last_execution": job.get("last_execution"),
        "verification": "unverified",
        "notice": "Includes tracked diff summary and untracked status; does not run tests, inspect every file, or merge changes.",
    }

def plan(root: Path, task: str, profile: str = "auto", max_agents: int = 3) -> dict:
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK:
        raise SwarmError(f"Task must contain between 1 and {MAX_TASK} characters")
    if profile != "auto" and profile not in profile_names():
        raise SwarmError("Unknown profile")
    try:
        stack = detect_stack(root)
    except (ValueError, OSError) as error:
        raise SwarmError(str(error)) from error
    selected = stack["recommended_profile"] if profile == "auto" else profile
    try:
        suggestion = recommend(task, selected, max_agents, stack)
    except ValueError as error:
        raise SwarmError(str(error)) from error
    return {
        "task": task.strip(), "profile": selected,
        "skill": suggestion["skill"], "agents": suggestion["agents"],
        "stack_languages": [item["name"] for item in stack["languages"][:6]],
        "stages": ["scope", "implement", "independent-review", "verification"],
        "execution": "planned-only",
        "notice": "No model calls or repository writes during planning. The proposed agents are guidance; actual delegation depends on Codex.",
    }


def create_job(target: Path, task: str, profile: str = "auto", max_agents: int = 3) -> dict:
    root, common = _repo(target)
    idea = plan(root, task, profile, max_agents)
    # Creates a fresh branch from the recorded commit, never from an implicit
    # uncommitted working tree. User modifications are never stashed or reset.
    base_sha = _git(root, "rev-parse", "HEAD")
    dirty = bool(_git(root, "status", "--porcelain"))
    job_id = uuid4().hex[:12]
    workspace = _workspace_path(root, job_id)
    if workspace.exists() or workspace.is_symlink():
        raise SwarmError("Generated worktree path already exists")
    branch = f"forgequorum/{job_id}"
    workspace.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "worktree", "add", "-b", branch, str(workspace), base_sha, timeout=90)
    job = {
        "format": JOB_FORMAT, "id": job_id, "repository": str(root),
        "workspace": str(workspace), "branch": branch, "base_sha": base_sha,
        "created_at": _now(), "state": "prepared", "plan": idea,
        "last_execution": None,
        "notice": "Workspace starts from committed HEAD. Existing uncommitted changes are not copied." if dirty else "No Codex execution occurred.",
    }
    try:
        _write_job(common, job)
    except Exception:
        # Never destroy a newly created workspace on metadata failure: the
        # developer may have been editing it from another process.
        raise SwarmError(f"Worktree created at {workspace}, but metadata could not be saved. Inspect it manually.")
    return job


def _registered_workspace(root: Path, workspace: Path) -> bool:
    return any(Path(line[len("worktree "):]).resolve() == workspace.resolve()
               for line in _git(root, "worktree", "list", "--porcelain").splitlines()
               if line.startswith("worktree "))


def inspect_job(target: Path, job_id: str) -> dict:
    root, common = _repo(target)
    job = _load_job(root, common, job_id)
    workspace = Path(job["workspace"])
    registered = _registered_workspace(root, workspace)
    if registered and not workspace.is_symlink() and workspace.is_dir():
        job["changes"] = _git(workspace, "status", "--short").splitlines()
        job["head_sha"] = _git(workspace, "rev-parse", "HEAD")
    else:
        job["changes"] = []
        job["head_sha"] = None
    job["registered"] = registered
    return job


def list_jobs(target: Path) -> list[dict]:
    root, common = _repo(target)
    directory = _job_dir(common)
    if not directory.exists():
        return []
    results = []
    for path in sorted(directory.glob("*.json")):
        if ID.fullmatch(path.stem):
            try:
                results.append(inspect_job(root, path.stem))
            except SwarmError as error:
                results.append({"id": path.stem, "state": "invalid", "error": str(error)})
    return results


def _prompt(job: dict) -> str:
    idea = job["plan"]
    team = ", ".join(idea["agents"])
    return (
        "You are working in an isolated Git worktree managed by ForgeQuorum. "
        "Respect AGENTS.md and local Codex configuration if present. "
        "Do not commit, merge, push, deploy, modify other worktrees, or perform destructive actions. "
        "Do not disclose secrets. Keep all changes inside this worktree. "
        "Use available native Codex subagents only if they are configured and genuinely useful; "
        "do not claim delegation that did not occur. "
        f"Suggested workflow: ${idea['skill']}. Suggested specialist roles: {team}. "
        "First inspect and scope the task, then implement, review, and run relevant tests. "
        "Report actual changes, test commands and outcomes, and unresolved risks.\n\n"
        "Task:\n" + idea["task"]
    )


def _stop_codex(proc: subprocess.Popen) -> None:
    """Best-effort child cancellation; do not signal any unrelated process."""
    if proc.poll() is not None:
        return
    try:
        if os.name == 'nt':
            proc.terminate()
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        try:
            proc.terminate()
        except OSError:
            pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            if os.name == 'nt':
                proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


def _codex_exec(workspace: Path, prompt: str, timeout: int) -> tuple[str, int, int, dict]:
    """Stream to private temporary files; retain only aggregated, reported usage."""
    binary = shutil.which('codex')
    if not binary:
        raise SwarmError('Codex CLI is missing from PATH. Install and authenticate it first.')
    argv = [binary, 'exec', '--json', '--sandbox', 'workspace-write', '-']
    # Cancellation is job-scoped: the workspace basename is the validated job ID.
    job_id = workspace.name
    if not ID.fullmatch(job_id):
        raise SwarmError('Invalid managed job worktree')
    _root, common = _repo(workspace)
    cancel_marker = _job_dir(common) / f'{job_id}.cancel'
    if cancel_marker.is_symlink():
        raise SwarmError('Refusing symlinked cancellation marker')
    reason = None
    started = monotonic()
    with tempfile.TemporaryFile(mode='w+t', encoding='utf-8') as output, \
         tempfile.TemporaryFile(mode='w+t', encoding='utf-8') as error:
        try:
            opts = {'start_new_session': True} if os.name != 'nt' else {
                'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
            with subprocess.Popen(argv, cwd=workspace, stdin=subprocess.PIPE,
                                  stdout=output, stderr=error, shell=False, **opts) as proc:
                # The prompt is passed via standard input, not exposed in OS process arguments.
                try:
                    proc.stdin.write(prompt.encode('utf-8'))
                except BrokenPipeError:
                    pass
                finally:
                    proc.stdin.close()
                while proc.poll() is None:
                    if cancel_marker.exists():
                        reason = 'cancelled'
                        _stop_codex(proc)
                        break
                    if monotonic() - started >= timeout:
                        reason = 'timed_out'
                        _stop_codex(proc)
                        break
                    try:
                        proc.wait(timeout=min(.2, max(.01, timeout - (monotonic() - started))))
                    except subprocess.TimeoutExpired:
                        pass
                code = proc.returncode
        except OSError as exc:
            raise SwarmError(f'Cannot launch Codex: {type(exc).__name__}') from exc
        # A cancellation sent at the end of a short task is still acknowledged.
        if cancel_marker.exists() and reason is None:
            reason = 'cancelled'
        if cancel_marker.exists() and not cancel_marker.is_symlink():
            cancel_marker.unlink(missing_ok=True)
        status = reason or ('completed' if code == 0 else 'failed')
        code = 130 if reason == 'cancelled' else 124 if reason == 'timed_out' else code
        output.seek(0)
        count = 0
        usage = {'source': 'not-reported', 'input_tokens': 0,
                 'cached_input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0,
                 'partial': status != 'completed'}
        for line in output:
            if len(line) > 1024 * 1024:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeError):
                continue
            if not isinstance(event, dict):
                continue
            count += 1
            # These are reported usage numbers, not a bill or a reliable cost estimate.
            if event.get('type') == 'turn.completed' and isinstance(event.get('usage'), dict):
                raw = event['usage']
                values = {}
                for key in ('input_tokens', 'cached_input_tokens', 'output_tokens'):
                    value = raw.get(key)
                    values[key] = value if type(value) is int and 0 <= value <= 10**12 else 0
                usage['source'] = 'codex-jsonl'
                for key, value in values.items():
                    usage[key] += value
        usage['total_tokens'] = usage['input_tokens'] + usage['output_tokens']
        return status, code, count, usage


def execute_job(target: Path, job_id: str, timeout: int = 900, execute: bool = False,
                reserve_tokens: int = 0, wait_seconds: int = 0) -> dict:
    if not 30 <= timeout <= 3600:
        raise SwarmError("timeout must be between 30 and 3600 seconds")
    root, common = _repo(target)
    job = _check_runnable(root, common, job_id)
    workspace = Path(job["workspace"])
    if not execute:
        return {"id": job_id, "state": "dry-run", "argv": ["codex", "exec", "--json", "--sandbox", "workspace-write", "-"],
                "workspace": str(workspace), "notice": "Pass --execute to authorize a real Codex invocation, which may consume tokens and edit this worktree."}
    with _exclusive_run(common, job_id):
        # Revalidate after claiming the lock: another process may have finished
        # the job between the first inspection and exclusive acquisition.
        job = _check_runnable(root, common, job_id)
        if not shutil.which("codex"):
            raise SwarmError("Codex CLI is missing from PATH. Install and authenticate it first.")
        from .scheduler import claim, settle
        ticket = claim(str(root), job_id, reserve_tokens=reserve_tokens,
                       wait_seconds=wait_seconds)
        started = monotonic()
        reported_tokens = None
        try:
            job["state"] = "running"
            _write_job(common, job)
            try:
                outcome = _codex_exec(workspace, _prompt(job), timeout)
                status, code, events = outcome[:3]
                usage = outcome[3] if len(outcome) > 3 else {
                    'source': 'not-reported', 'input_tokens': 0, 'cached_input_tokens': 0,
                    'output_tokens': 0, 'total_tokens': 0, 'partial': status != 'completed'}
                if (isinstance(usage, dict) and usage.get('source') == 'codex-jsonl'
                        and type(usage.get('total_tokens')) is int
                        and 0 <= usage['total_tokens'] <= 10**12):
                    reported_tokens = usage['total_tokens']
                job["state"] = status
                job["last_execution"] = {"at": _now(), "exit_code": code, "events_seen": events,
                                         "timeout_seconds": timeout, "usage": usage,
                                         "elapsed_seconds": round(monotonic() - started, 3)}
            except Exception:
                job["state"] = "failed"
                job["last_execution"] = {"at": _now(), "exit_code": None, "events_seen": 0,
                                         "elapsed_seconds": round(monotonic() - started, 3),
                                         "error": "Codex launch error"}
                _write_job(common, job)
                raise
            _write_job(common, job)
            marker = _job_dir(common) / f"{job_id}.cancel"
            if marker.exists() and not marker.is_symlink():
                marker.unlink(missing_ok=True)
        finally:
            # On missing usage charge the entire reserved amount. Even a failed
            # launch never silently frees reserved tokens.
            settle(ticket, reported_tokens=reported_tokens)
    return inspect_job(root, job_id)


def cleanup_job(target: Path, job_id: str, confirm: bool = False) -> dict:
    root, common = _repo(target)
    job = _load_job(root, common, job_id)
    workspace = Path(job["workspace"])
    if not confirm:
        return {"id": job_id, "state": "dry-run", "workspace": str(workspace),
                "notice": "Requires --confirm. Only clean, Git-registered worktrees can be removed. Branch is preserved."}
    if job["state"] in ("running", "cleaned") or (_job_dir(common) / f"{job_id}.lock").exists():
        raise SwarmError("Refusing cleanup of a running, locked, or already cleaned job")
    if workspace.is_symlink() or not workspace.is_dir() or not _registered_workspace(root, workspace):
        raise SwarmError("Worktree is missing or has changed; refusing cleanup")
    if _git(workspace, "status", "--porcelain"):
        raise SwarmError("Worktree has uncommitted or untracked changes; refusing cleanup")
    # Never force removal or delete branches. Git itself rejects unsafe cleanup.
    _git(root, "worktree", "remove", str(workspace), timeout=90)
    job["state"] = "cleaned"
    job["cleaned_at"] = _now()
    _write_job(common, job)
    return {"id": job_id, "state": "cleaned", "branch_preserved": job["branch"]}

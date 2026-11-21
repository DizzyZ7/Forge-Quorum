"""Opt-in Codex runs in isolated, reviewable Git worktrees.

This is a local orchestration foundation, not an autonomous deployment or merge
engine. No project code or AI service is executed by planning/creating a job.
"""
from __future__ import annotations

import json
import os
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


def _codex_exec(workspace: Path, prompt: str, timeout: int) -> tuple[str, int, int]:
    """Return status, exit code and event count; never retain model transcript."""
    binary = shutil.which("codex")
    if not binary:
        raise SwarmError("Codex CLI is missing from PATH. Install and authenticate it first.")
    argv = [binary, "exec", "--json", "--sandbox", "workspace-write", prompt]
    # Streaming to anonymous temp files bounds RAM and avoids writing traces
    # into the project. Raw prompts/transcripts are not persisted by this tool.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output, \
         tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as error:
        try:
            completed = subprocess.run(argv, cwd=workspace, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=error, timeout=timeout,
                                       check=False)
            status, code = ("completed", 0) if completed.returncode == 0 else ("failed", completed.returncode)
        except subprocess.TimeoutExpired:
            status, code = "timed_out", 124
        except OSError as exc:
            raise SwarmError(f"Cannot launch Codex: {type(exc).__name__}") from exc
        output.seek(0)
        count = 0
        for line in output:
            if len(line) <= 1024 * 1024:
                try:
                    if isinstance(json.loads(line), dict):
                        count += 1
                except json.JSONDecodeError:
                    pass
        return status, code, count


def execute_job(target: Path, job_id: str, timeout: int = 900, execute: bool = False) -> dict:
    if not 30 <= timeout <= 3600:
        raise SwarmError("timeout must be between 30 and 3600 seconds")
    root, common = _repo(target)
    job = _load_job(root, common, job_id)
    workspace = Path(job["workspace"])
    if not _registered_workspace(root, workspace) or workspace.is_symlink() or not workspace.is_dir():
        raise SwarmError("Worktree is missing or no longer managed by Git")
    if job["state"] not in ("prepared", "failed", "timed_out"):
        raise SwarmError("Job is not runnable; completed and running jobs cannot be rerun automatically")
    if not execute:
        return {"id": job_id, "state": "dry-run", "argv": ["codex", "exec", "--json", "--sandbox", "workspace-write", "<generated task prompt>"],
                "workspace": str(workspace), "notice": "Pass --execute to authorize a real Codex invocation, which may consume tokens and edit this worktree."}
    if not shutil.which("codex"):
        raise SwarmError("Codex CLI is missing from PATH. Install and authenticate it first.")
    job["state"] = "running"
    _write_job(common, job)
    try:
        status, code, events = _codex_exec(workspace, _prompt(job), timeout)
        job["state"] = status
        job["last_execution"] = {"at": _now(), "exit_code": code, "events_seen": events, "timeout_seconds": timeout}
    except Exception:
        job["state"] = "failed"
        job["last_execution"] = {"at": _now(), "exit_code": None, "events_seen": 0, "error": "Codex launch error"}
        _write_job(common, job)
        raise
    _write_job(common, job)
    return inspect_job(root, job_id)


def cleanup_job(target: Path, job_id: str, confirm: bool = False) -> dict:
    root, common = _repo(target)
    job = _load_job(root, common, job_id)
    workspace = Path(job["workspace"])
    if not confirm:
        return {"id": job_id, "state": "dry-run", "workspace": str(workspace),
                "notice": "Requires --confirm. Only clean, Git-registered worktrees can be removed. Branch is preserved."}
    if job["state"] in ("running", "cleaned"):
        raise SwarmError("Refusing cleanup of a running or already cleaned job")
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

"""Explicit, reviewable patch transfer between queued, isolated Git worktrees.

This is deliberately NOT a merge engine: it never writes the main branch,
commits, pushes or deploys. Source worktree changes must already be committed
and have a fresh, successful verification. Transfer is opt-in, index-only, and
fails closed on conflicts, untracked edits or unverifiable provenance.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any

from .swarm import SwarmError, ID, _repo, _load_job, _exclusive_run, _git
from .swarm_control import _validate_workspace, _git_paths

MAX_PATCH_BYTES = 4 * 1024 * 1024
MAX_PATCH_PATHS = 1000
_SHA = re.compile(r"^[0-9a-f]{40,64}$")


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _git_bytes(directory: Path, *args: str, input_data: bytes | None = None,
               accepted: tuple[int, ...] = (0,)) -> tuple[int, bytes]:
    """Use git argument arrays, never a shell; do not expose raw project output."""
    try:
        proc = subprocess.run(["git", "-C", str(directory), *args], input=input_data,
                              capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SwarmError(f"Git action {args[0]} could not be completed") from exc
    if proc.returncode not in accepted:
        raise SwarmError(f"Git action {args[0]} rejected the operation (exit {proc.returncode}); inspect the worktree")
    return proc.returncode, proc.stdout


def _index_digest(workspace: Path) -> str:
    _, body = _git_bytes(workspace, "diff", "--cached", "--binary", "--full-index",
                         "--no-ext-diff", "HEAD", "--")
    if len(body) > MAX_PATCH_BYTES:
        raise SwarmError("Worktree staged diff exceeds maximum safe transfer size")
    return _sha256(body)


def _verified_source(root: Path, common: Path, source_id: str, entries: dict) -> tuple[dict, Path, str]:
    """Validate verification freshness without building or inspecting a patch."""
    entry = entries.get(source_id)
    if entry is None or entry["state"] != "completed":
        raise SwarmError("Source dependency must have completed successfully in this queue")
    job = _load_job(root, common, source_id)
    workspace = _validate_workspace(root, job)
    if job["state"] != "completed":
        raise SwarmError("Source Codex job has not completed successfully")
    head = _git(workspace, "rev-parse", "HEAD")
    if not _SHA.fullmatch(head) or not _SHA.fullmatch(job["base_sha"]):
        raise SwarmError("Source has an invalid Git revision")
    verification = job.get("last_verification")
    if (not isinstance(verification, dict) or verification.get("ok") is not True
            or verification.get("commit_sha") != head or verification.get("dirty") is not False
            or not isinstance(verification.get("gates"), list) or not verification["gates"]):
        raise SwarmError("Source has no fresh, successful verification of a clean commit")
    if _git(workspace, "status", "--porcelain"):
        raise SwarmError("Source has uncommitted or untracked changes since verification")
    _git_bytes(workspace, "merge-base", "--is-ancestor", job["base_sha"], head)
    return job, workspace, head


def _source(root: Path, common: Path, source_id: str, entries: dict) -> tuple[dict, Path, str, list[str], bytes]:
    job, workspace, head = _verified_source(root, common, source_id, entries)
    paths = sorted(_git_paths(workspace, "diff", "--name-only", "-z", "--no-renames",
                              job["base_sha"], head, "--"))
    if len(paths) > MAX_PATCH_PATHS:
        raise SwarmError("Source patch changes too many files")
    for name in paths:
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or not name or "\\" in name
                or name in (".git", ".gitmodules") or path.parts[0] in (".git", ".forgequorum")):
            raise SwarmError("Source contains a path excluded from managed patch transfers")
    _, modes = _git_bytes(workspace, "diff", "--raw", "-z", "--no-renames",
                           job["base_sha"], head, "--")
    for record in modes.split(b"\0"):
        if record.startswith(b":"):
            tokens = record.split(b" ")
            if len(tokens) < 2 or tokens[0][1:] in (b"120000", b"160000") or tokens[1] in (b"120000", b"160000"):
                raise SwarmError("Symlink and submodule changes require manual transfer")
    _, patch = _git_bytes(workspace, "diff", "--binary", "--full-index", "--no-ext-diff",
                           "--no-textconv", "--no-renames", job["base_sha"], head, "--")
    if len(patch) > MAX_PATCH_BYTES:
        raise SwarmError("Source patch exceeds 4 MiB; transfer manually")
    return job, workspace, head, paths, patch


def _child(root: Path, common: Path, child_id: str, entry: dict) -> tuple[dict, Path, str]:
    if entry["state"] != "queued":
        raise SwarmError("Only queued dependent tasks accept a patch transfer")
    job = _load_job(root, common, child_id)
    if job["state"] != "prepared":
        raise SwarmError("Destination must be a prepared, not-yet-executed Codex worktree")
    workspace = _validate_workspace(root, job)
    head = _git(workspace, "rev-parse", "HEAD")
    if head != job["base_sha"]:
        raise SwarmError("Destination has extra commits; transfer manually")
    code, _ = _git_bytes(workspace, "diff", "--quiet", "--", accepted=(0, 1))
    if code == 1 or _git_paths(workspace, "ls-files", "--others", "--exclude-standard", "-z"):
        raise SwarmError("Destination has unstaged or untracked files; refusing to overwrite")
    handoffs = entry.get("handoffs", {})
    index_digest = _index_digest(workspace)
    if handoffs:
        last = max(handoffs.values(), key=lambda x: x["sequence"])
        if (index_digest != last["index_sha256"] or head != last["destination_sha"]):
            raise SwarmError("Transferred destination index was modified; inspect changes manually")
    elif index_digest != _sha256(b""):
        raise SwarmError("Destination has previously staged changes not owned by ForgeQuorum")
    return job, workspace, head


def _dependency_verified(root: Path, common: Path, dependency_id: str, entries: dict) -> bool:
    try:
        _verified_source(root, common, dependency_id, entries)
    except (SwarmError, OSError, ValueError):
        return False
    return True


def dependency_readiness(root: Path, common: Path, item: dict, entries: dict) -> str:
    """Fail closed when required verification or transfer evidence has gone stale."""
    policy = item.get("gate", "order")
    if policy == "order" or not item["after"]:
        return "ready"
    for dependency_id in item["after"]:
        if not _dependency_verified(root, common, dependency_id, entries):
            return "dependency-unverified"
    if policy == "verified":
        return "ready"
    evidence = item.get("handoffs", {})
    if not all(dependency_id in evidence for dependency_id in item["after"]):
        return "handoff-required"
    try:
        job = _load_job(root, common, item["id"])
        workspace = _validate_workspace(root, job)
        head = _git(workspace, "rev-parse", "HEAD")
        if job["state"] != "prepared" or head != job["base_sha"]:
            return "handoff-stale"
        last = max(evidence.values(), key=lambda x: x["sequence"])
        if head != last["destination_sha"] or _index_digest(workspace) != last["index_sha256"]:
            return "handoff-stale"
        code, _ = _git_bytes(workspace, "diff", "--quiet", "--", accepted=(0, 1))
        if code != 0 or _git_paths(workspace, "ls-files", "--others", "--exclude-standard", "-z"):
            return "handoff-stale"
        for source_id, record in evidence.items():
            source = _load_job(root, common, source_id)
            if _git(Path(source["workspace"]), "rev-parse", "HEAD") != record["source_sha"]:
                return "handoff-stale"
    except (SwarmError, OSError, ValueError):
        return "handoff-stale"
    return "ready"


def transfer(target: Path, destination_id: str, source_id: str, apply: bool = False) -> dict[str, Any]:
    """Preview or explicitly stage a source's verified committed diff into a child.

    A queue mutex ensures dispatch cannot claim the destination during transfer;
    the per-worktree lock ensures Codex cannot edit concurrently. No commit,
    checkout, reset or cleanup is performed.
    """
    if (not ID.fullmatch(destination_id) or not ID.fullmatch(source_id)
            or source_id == destination_id):
        raise SwarmError("Specify two different, valid queue job IDs")
    from .queue import _transaction, _write, _event

    root, common = _repo(target)
    # Use the queue mutex for both check and application, so a queue dispatcher
    # cannot claim the destination between the preview and the actual write.
    with _transaction(common) as (folder, data):
        entries = data["entries"]
        entry = entries.get(destination_id)
        if entry is None or source_id not in entry["after"]:
            raise SwarmError("Destination must list the source as a queue dependency")
        if source_id in entry.get("handoffs", {}):
            raise SwarmError("This source has already been transferred to the destination")
        parent, _, source_sha, paths, patch = _source(root, common, source_id, entries)
        child, workspace, destination_sha = _child(root, common, destination_id, entry)
        if parent["base_sha"] != child["base_sha"]:
            raise SwarmError("Dependency and destination were created from different base commits")
        prior = entry.get("handoffs", {})
        if any(set(paths) & set(record["paths"]) for record in prior.values()):
            raise SwarmError("Source overlaps files from an earlier transfer; resolve manually")
        # Apply must be possible without a merge engine or fuzzy overwrite.
        if patch:
            _git_bytes(workspace, "apply", "--check", "--index", "-", input_data=patch)
        overview = {"destination_id": destination_id, "source_id": source_id,
                    "source_sha": source_sha, "destination_sha": destination_sha,
                    "paths": paths, "path_count": len(paths), "patch_bytes": len(patch),
                    "patch_sha256": _sha256(patch), "state": "dry-run",
                    "notice": "A dry run does not modify files. --apply stages a patch only in the destination worktree; review staged changes before running Codex."}
        if not apply:
            return overview
        with _exclusive_run(common, destination_id):
            # Recheck important state after acquiring the per-job claim.
            _child(root, common, destination_id, entry)
            if patch:
                _git_bytes(workspace, "apply", "--index", "-", input_data=patch)
            digest = _index_digest(workspace)
            evidence = dict(prior)
            evidence[source_id] = {"source_sha": source_sha, "destination_sha": destination_sha,
                                   "patch_sha256": _sha256(patch), "index_sha256": digest,
                                   "paths": paths, "sequence": len(evidence) + 1}
            entry["handoffs"] = evidence
            _event(data, "transferred", destination_id)
            # If metadata cannot be persisted the staged changes are retained
            # for explicit operator inspection; do not reset arbitrary changes.
            _write(folder, data)
        overview.update(state="staged", index_sha256=digest,
                        notice="Source committed patch staged in destination only. No commit, merge, push or deploy. Verify changes and test before using the result.")
        return overview

#!/usr/bin/env python3
"""Install the specialist and selected upstream skills at reviewed, pinned commits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True,
                          capture_output=True, timeout=180).stdout.strip()


def install(source: Path, destination: Path):
    if source.is_symlink() or any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Skill symlinks are not accepted: " + source.name)
    if not (source / "SKILL.md").is_file():
        raise ValueError("Missing skill manifest: " + source.name)
    target = destination / source.name
    if target.exists():
        # The repository already contains its own specialist. Otherwise refuse
        # replacing a user's customizations; select a separate destination.
        if source.resolve() == target.resolve():
            return {"skill": source.name, "status": "already_in_place"}
        raise FileExistsError("Existing skill preserved; use a new destination: " + str(target))
    with tempfile.TemporaryDirectory(prefix=".skill-stage-", dir=destination) as tmp:
        staged = Path(tmp) / source.name
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for attempt in range(4):
            try:
                staged.rename(target)
                break
            except PermissionError:
                # Windows scanners/OneDrive can briefly hold a freshly copied
                # directory. Bounded retry; no deletion or overwrite fallback.
                if attempt == 3:
                    raise
                time.sleep(0.25 * (attempt + 1))
    digest = hashlib.sha256((target / "SKILL.md").read_bytes()).hexdigest()
    return {"skill": source.name, "status": "installed", "manifest_sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / ".agents" / "skills")
    parser.add_argument("--specialist-only", action="store_true", help="No network or upstream installation")
    args = parser.parse_args()
    destination = args.destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    receipt = {"schema_version": 1, "skills": [], "upstream": {}}
    try:
        # Avoid git hooks, user checkout smudge filters and shared cache races.
        receipt["skills"].append(install(ROOT / ".agents" / "skills" / "dynatrace-specialist", destination))
        if not args.specialist_only:
            lock = json.loads((ROOT / "upstream.lock.json").read_text(encoding="utf-8"))
            for name in ("dynatrace-for-ai", "dtctl"):
                spec = lock[name]
                with tempfile.TemporaryDirectory(prefix="dt-skills-") as tmp:
                    repo = Path(tmp) / "upstream"
                    git("init", str(repo))
                    git("remote", "add", "origin", spec["repository"], cwd=repo)
                    git("fetch", "--depth", "1", "origin", spec["commit"], cwd=repo)
                    git("-c", "core.hooksPath=" + str(Path(tmp) / "no-hooks"),
                        "-c", "filter.lfs.smudge=", "-c", "filter.lfs.required=false",
                        "checkout", "--detach", "FETCH_HEAD", cwd=repo)
                    if git("rev-parse", "HEAD", cwd=repo) != spec["commit"]:
                        raise ValueError("Upstream commit mismatch.")
                    receipt["upstream"][name] = {"commit": spec["commit"], "repository": spec["repository"]}
                    for skill in spec["skills"]:
                        receipt["skills"].append(install(repo / "skills" / skill, destination))
                    # Preserve upstream license notices alongside installed skills.
                    notices = destination / ".upstream-notices" / name
                    notices.mkdir(parents=True, exist_ok=True)
                    for filename in ("LICENSE", "NOTICE"):
                        if (repo / filename).is_file():
                            shutil.copyfile(repo / filename, notices / filename)
        receipt_path = destination / ("dynatrace-install-" + os.urandom(6).hex() + ".json")
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "ok", "receipt": str(receipt_path)}))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Already installed skills are kept. The operation never removes user data.
        print(json.dumps({"status": "error", "message": str(exc), "installed": receipt["skills"]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Offline package checks; this does not validate DQL against a tenant."""
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "dynatrace-specialist"


def main():
    for path in ROOT.rglob("*.py"):
        if ".git" not in path.parts:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in (ROOT / "upstream.lock.json", ROOT / ".codex-plugin" / "plugin.json",
                 ROOT / "config" / "services.example.json", SKILL / "queries" / "catalog.json"):
        json.loads(path.read_text(encoding="utf-8"))
    manifest = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert manifest.startswith("---\nname: dynatrace-specialist\ndescription: ")
    assert len(manifest.split("\n---\n")[1]) < 20000
    for path in SKILL.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if not re.match(r"^[a-z]+://", target):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
    catalog = json.loads((SKILL / "queries" / "catalog.json").read_text())
    for template in catalog:
        assert (SKILL / "queries" / (template + ".dql")).is_file()
    print("Package structure, Python syntax, JSON and skill references: OK (offline).")


if __name__ == "__main__":
    main()

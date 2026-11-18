"""Shared fixtures: a throwaway vault and projects dir, wired through PK_* env vars."""
import subprocess
from pathlib import Path

import pytest

INDEX_CODE = """---
type: project
topic: project
status: growing
state: active
kind: code
slug: demo-app
repo: arrowboy47/demo-app
visibility: public
description: "A demo code project."
tags: [project]
---
# Demo App

## Map of content

- [[Demo App Backlog]]
- [[Demo App Log]]

Listed in [[Projects Index]].
"""

INDEX_VAULT = """---
type: project
topic: project
status: seedling
state: paused
kind: vault
description: "A demo vault-only project."
tags: [project]
---
# Pond Build

- [[Pond Build Backlog]]
- [[Pond Build Log]]
"""


def _w(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "Notes"
    _w(v / "Projects/Projects Index.md",
       "---\ntype: project\n---\n# Projects Index\n\n## Active\n\n1. [[_Demo App Index|Demo App]]: demo\n\n## Paused\n\n1. [[_Pond Build Index|Pond Build]]: pond\n")
    _w(v / "Projects/Demo App/_Demo App Index.md", INDEX_CODE)
    _w(v / "Projects/Demo App/Demo App Backlog.md", "# Demo App Backlog\n\n- [ ] thing\n")
    _w(v / "Projects/Demo App/Demo App Log.md", "# Demo App Log\n\n## 2026-11-17\n\n- made\n")
    _w(v / "Projects/pondbuild/_Pond Build Index.md", INDEX_VAULT)
    _w(v / "Projects/pondbuild/Pond Build Backlog.md", "# Pond Build Backlog\n")
    _w(v / "Projects/pondbuild/Pond Build Log.md", "# Pond Build Log\n")
    _w(v / "Reference/Guides/Stack Log.md", "# Stack Log\n\n- Deployed Demo App on thebigbox\n")
    _w(v / "Reference/Guides/Agent Brief.md", "# Agent Brief\n\nDemo App code is in `~/Projects/demo-app`.\n")
    _w(v / "Daily/2020-01-01.md", "Worked on Demo App today.\n")
    _w(v / "Archive/old.md", "Demo App was mentioned here.\n")
    _w(v / "Reference/Note With History.md",
       "# Note With History\n\nWe use Demo App daily.\n\n## History\n\n- `[2026-01-01 10:00]` Demo App added\n")
    _w(v / ".obsidian/workspace.md", "Demo App\n")
    monkeypatch.setenv("PK_VAULT", str(v))
    return v


@pytest.fixture
def projects(tmp_path, monkeypatch):
    """A projects root containing a real git repo `demo-app` with origin set (no network)."""
    root = tmp_path / "projects"
    repo = root / "demo-app"
    repo.mkdir(parents=True)
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init")
    run("git", "remote", "add", "origin", "https://github.com/arrowboy47/demo-app.git")
    (repo / "AGENTS.md").write_text("# Demo App\n")
    (repo / "CLAUDE.md").write_text("@AGENTS.md\n")
    monkeypatch.setenv("PK_PROJECTS", str(root))
    return root

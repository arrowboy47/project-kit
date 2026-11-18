import subprocess
import sys
from pathlib import Path

import pytest

from projectkit import common as c
from projectkit import new


@pytest.fixture
def calls(monkeypatch):
    """Record every run() call. gh is faked (never executed); git runs for real in tmp dirs."""
    recorded = []
    real = new.run

    def fake(cmd, cwd=None, timeout=60):
        recorded.append(list(cmd))
        if cmd[0] == "gh":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(cmd, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(new, "run", fake)
    return recorded


def gh_calls(calls):
    return [cmd for cmd in calls if cmd[0] == "gh"]


def snapshot(*roots: Path) -> dict:
    out = {}
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file():
                out[str(p)] = (p.read_bytes(), p.stat().st_mtime_ns)
    return out


def test_vault_project_creates_notes_and_index_line(vault, calls, capsys):
    rc = new.main(["Garden Plan", "--kind", "vault", "--description", "A garden."])
    assert rc == 0
    folder = vault / "Projects" / "Garden Plan"
    assert (folder / "_Garden Plan Index.md").is_file()
    assert (folder / "Garden Plan Backlog.md").is_file()
    assert (folder / "Garden Plan Log.md").is_file()
    meta, _ = c.parse_frontmatter((folder / "_Garden Plan Index.md").read_text(encoding="utf-8"))
    assert meta["kind"] == "vault" and meta["state"] == "active"
    index_text = c.projects_index_path(vault).read_text(encoding="utf-8")
    assert "2. [[_Garden Plan Index|Garden Plan]]: A garden." in index_text
    assert gh_calls(calls) == []
    assert capsys.readouterr().out.rstrip().endswith("End each work session with a Garden Plan Log entry.")


def test_code_project_creates_repo_and_calls_gh_private(vault, projects, calls):
    rc = new.main(["Widget Shop", "--kind", "code", "--private", "--description", "A shop."])
    assert rc == 0
    d = projects / "widget-shop"
    assert (d / ".git").is_dir()
    assert "# Widget Shop" in (d / "AGENTS.md").read_text(encoding="utf-8")
    assert (d / "CLAUDE.md").is_file()
    assert gh_calls(calls) == [[
        "gh", "repo", "create", f"{c.gh_owner()}/widget-shop", "--private",
        "--source", str(d), "--remote", "origin",
    ]]
    meta, _ = c.parse_frontmatter(
        (vault / "Projects" / "Widget Shop" / "_Widget Shop Index.md").read_text(encoding="utf-8"))
    assert meta["kind"] == "code"
    assert meta["slug"] == "widget-shop"
    assert meta["visibility"] == "private"
    assert meta["repo"] == f"{c.gh_owner()}/widget-shop"


def test_code_project_with_commit_pushes(vault, projects, calls):
    d = projects / "widget"
    d.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                    "--allow-empty", "-m", "init"], cwd=d, check=True, capture_output=True)
    rc = new.main(["Widget", "--kind", "code", "--private", "--adopt", "--description", "w"])
    assert rc == 0
    [cmd] = gh_calls(calls)
    assert "--push" in cmd


def test_refuses_code_without_visibility(vault, projects, calls, capsys):
    rc = new.main(["Widget Shop", "--kind", "code", "--description", "d"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "Pick --private if" in err
    assert not (projects / "widget-shop").exists()
    assert gh_calls(calls) == []


def test_existing_dir_without_adopt_exits_1(vault, projects, calls, capsys):
    rc = new.main(["Demo App", "--kind", "code", "--private", "--description", "x"])
    assert rc == 1
    assert "use --adopt" in capsys.readouterr().err
    assert gh_calls(calls) == []


def test_adopt_on_demo_app_changes_no_file(vault, projects, calls, capsys):
    before = snapshot(vault, projects)
    rc = new.main(["Demo App", "--kind", "code", "--private", "--description", "x", "--adopt"])
    assert rc == 0
    assert snapshot(vault, projects) == before
    assert gh_calls(calls) == []
    out = capsys.readouterr().out
    assert "skip Projects Index line (exists)" in out


def test_from_note_renames_hub_keeps_body_and_rewrites_links(vault, calls):
    old = vault / "Reference" / "Old Hub.md"
    old.write_text("---\ntype: note\nstatus: growing\ntags: [hub]\n---\n# Garden Hub\n\nBody text here.\n",
                   encoding="utf-8")
    pointer = vault / "Reference" / "Pointer.md"
    pointer.write_text("See [[Old Hub]] for details.\n", encoding="utf-8")

    rc = new.main(["Garden", "--kind", "vault", "--description", "Garden stuff.",
                   "--from-note", "Reference/Old Hub.md"])
    assert rc == 0

    index = vault / "Projects" / "Garden" / "_Garden Index.md"
    assert index.is_file()
    assert not old.exists()
    meta, body = c.parse_frontmatter(index.read_text(encoding="utf-8"))
    assert meta["type"] == "project"       # an index is always type: project
    assert meta["status"] == "growing"
    assert meta["tags"] == ["hub"]
    assert meta["kind"] == "vault"         # added from template
    assert meta["state"] == "active"
    assert meta["description"] == "Garden stuff."
    assert meta["topic"] == "project"
    assert "# Garden Hub\n\nBody text here.\n" in body
    assert "[[Garden Backlog]]" in body and "[[Garden Log]]" in body
    assert "[[_Garden Index|Old Hub]]" in pointer.read_text(encoding="utf-8")


def test_dry_run_writes_nothing_and_runs_nothing(vault, projects, calls, capsys):
    before = snapshot(vault, projects)
    rc = new.main(["Widget Shop", "--kind", "code", "--public", "--description", "d", "--dry-run"])
    assert rc == 0
    assert snapshot(vault, projects) == before
    assert not (projects / "widget-shop").exists()
    assert not (vault / "Projects" / "Widget Shop").exists()
    assert calls == []
    out = capsys.readouterr().out
    assert f"create GitHub repo {c.gh_owner()}/widget-shop (public)" in out


def test_default_slug_from_name(vault, projects, calls, capsys):
    rc = new.main(["Garden Plan v2", "--kind", "code", "--public", "--description", "d", "--dry-run"])
    assert rc == 0
    assert f"create GitHub repo {c.gh_owner()}/garden-plan-v2 (public)" in capsys.readouterr().out
    assert new.default_slug("  Garden  Plan!! v2 ") == "garden-plan-v2"


def test_adopt_completes_a_partial_existing_index(vault, projects):
    idx = vault / "Projects/Demo App/_Demo App Index.md"
    idx.write_text("---\ntype: project\ntopic: project\nstatus: growing\ntags:\n  - project\n---\n# Demo App\n\nBody stays.\n")
    rc = new.main(["Demo App", "--kind", "code", "--public", "--slug", "demo-app", "--adopt",
                   "--no-github", "--description", "A demo."])
    assert rc == 0
    meta, body = c.parse_frontmatter(idx.read_text())
    assert meta["kind"] == "code" and meta["state"] == "active" and meta["slug"] == "demo-app"
    assert meta["tags"] == ["project"] and "Body stays." in body
    assert "[[Demo App Backlog" in body and "[[Demo App Log" in body

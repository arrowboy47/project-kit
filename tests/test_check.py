"""Tests for project-check. Uses only the vault and projects fixtures (no network, no real vault or ~/projects)."""
import shutil
import subprocess

import pytest

from projectkit import check, common


def _proj(name="Demo App"):
    p = common.get_project(name)
    assert p is not None
    return p


def _demo_index(vault):
    return vault / "Projects" / "Demo App" / "_Demo App Index.md"


def test_all_passes_with_fixtures(vault, projects, capsys):
    assert check.main(["--all"]) == 0
    out = capsys.readouterr().out
    assert "OK Demo App" in out
    assert "OK Pond Build" in out
    assert "FAIL" not in out


def test_name_or_slug_lookup(vault, projects):
    assert check.main(["demo-app"]) == 0
    assert check.main(["Nope Project"]) == 1


def test_invariant1_missing_key_bad_state_bad_visibility(vault, projects):
    idx = _demo_index(vault)
    idx.write_text(idx.read_text(encoding="utf-8")
                   .replace("tags: [project]\n", "")
                   .replace("state: active", "state: bogus")
                   .replace("visibility: public", "visibility: secret"), encoding="utf-8")
    probs = check.check_project(_proj(), vault)
    assert any("missing key: tags" in p for p in probs)
    assert any("bad state: bogus" in p for p in probs)
    assert any("bad visibility: secret" in p for p in probs)


def test_invariant2_missing_backlog(vault, projects):
    (vault / "Projects/Demo App/Demo App Backlog.md").unlink()
    probs = check.check_project(_proj(), vault)
    assert any("Demo App Backlog.md" in p for p in probs)


def test_invariant2_index_must_link_log(vault, projects):
    idx = _demo_index(vault)
    idx.write_text(idx.read_text(encoding="utf-8").replace("[[Demo App Log]]", ""), encoding="utf-8")
    probs = check.check_project(_proj(), vault)
    assert any("[[Demo App Log]]" in p for p in probs)


def test_invariant3_projects_index_must_link_project(vault, projects):
    pidx = common.projects_index_path(vault)
    pidx.write_text(pidx.read_text(encoding="utf-8").replace("[[_Demo App Index|Demo App]]", "Demo App"),
                    encoding="utf-8")
    probs = check.check_project(_proj(), vault)
    assert any("Projects Index does not link" in p for p in probs)


@pytest.mark.parametrize("breaker, needle", [
    (lambda root, repo: (repo / "AGENTS.md").unlink(), "AGENTS.md"),
    (lambda root, repo: subprocess.run(
        ["git", "-C", str(repo), "remote", "set-url", "origin", "https://github.com/other/thing.git"],
        check=True, capture_output=True), "origin"),
    (lambda root, repo: shutil.rmtree(repo / ".git"), "git repo"),
])
def test_invariant4_code_checks(vault, projects, breaker, needle):
    breaker(projects, projects / "demo-app")
    probs = check.check_project(_proj(), vault)
    assert any(needle in p for p in probs), probs


def test_vault_only_skips_code_checks(vault, projects):
    (projects / "demo-app" / "AGENTS.md").unlink()
    assert check.check_project(_proj(), vault) != []
    assert check.check_project(_proj(), vault, vault_only=True) == []


def test_runs_on_missing_guides_note_fails(vault, projects):
    idx = _demo_index(vault)
    idx.write_text(idx.read_text(encoding="utf-8").replace("tags: [project]\n", 'tags: [project]\nruns_on: ["thebigbox"]\n'),
                   encoding="utf-8")
    probs = check.check_project(_proj(), vault)
    assert any("Guides" in p and "Demo App.md" in p for p in probs), probs


def test_runs_on_with_linked_guides_note_passes(vault, projects):
    idx = _demo_index(vault)
    idx.write_text(idx.read_text(encoding="utf-8").replace("tags: [project]\n", 'tags: [project]\nruns_on: ["thebigbox"]\n')
                   + "\nSee [[Reference/Guides/Projects/Demo App]].\n", encoding="utf-8")
    guide = vault / "Reference" / "Guides" / "Projects" / "Demo App.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("# Demo App on thebigbox\n\nIndex: [[_Demo App Index]]\n", encoding="utf-8")
    assert check.check_project(_proj(), vault) == []


def test_layout_flags_unknown_dir_and_ignores_archive_hidden_symlink(vault, projects, tmp_path):
    (projects / "stray").mkdir()
    (projects / "_archive").mkdir()
    (projects / ".cache").mkdir()
    (projects / "linked").symlink_to(tmp_path)
    probs = check.check_layout(common.find_projects(vault), projects)
    assert probs == ["unknown dir in ~/projects: stray"]


def test_layout_cli_exit_code(vault, projects, capsys):
    assert check.main(["--layout"]) == 0
    (projects / "stray").mkdir()
    assert check.main(["--layout"]) == 1
    assert "FAIL layout: unknown dir in ~/projects: stray" in capsys.readouterr().out


@pytest.mark.parametrize("gh_stdout, expect_problem", [("PRIVATE\n", True), ("PUBLIC\n", False)])
def test_remote_visibility_uses_gh_monkeypatched(vault, projects, monkeypatch, gh_stdout, expect_problem):
    real_run = check.run
    gh_calls = []

    def fake_run(cmd, cwd=None, timeout=60):
        if cmd[0] != "gh":
            return real_run(cmd, cwd=cwd, timeout=timeout)
        gh_calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=gh_stdout, stderr="")

    monkeypatch.setattr(check, "run", fake_run)

    assert check.check_project(_proj(), vault) == []
    assert gh_calls == []

    probs = check.check_project(_proj(), vault, remote_visibility=True)
    assert gh_calls == [["gh", "repo", "view", "arrowboy47/demo-app", "--json", "visibility", "-q", ".visibility"]]
    assert any("remote visibility" in p for p in probs) == expect_problem


def test_usage_error_without_names_all_or_layout(vault, projects):
    assert check.main([]) == 2


def test_cli_exit_1_and_fail_line_on_broken_project(vault, projects, capsys):
    (projects / "demo-app" / "CLAUDE.md").unlink()
    assert check.main(["Demo App"]) == 1
    assert "FAIL Demo App: " in capsys.readouterr().out

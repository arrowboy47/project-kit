import subprocess

from projectkit import check, common as c, new, status


def _repo(path, origin=None):
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    if origin:
        subprocess.run(["git", "remote", "add", "origin", origin], cwd=path, check=True)


def _ws_vault(vault):
    d = vault / "Projects/Local Websites"
    d.mkdir(parents=True)
    (d / "_Local Websites Index.md").write_text(
        '---\ntype: project\ntopic: project\nstatus: seedling\nstate: active\nkind: workspace\n'
        'slug: Local_Websites\ndescription: "Sites for local businesses."\ntags: [project]\n---\n'
        "# Local Websites\n\n- [[Local Websites Backlog]]\n- [[Local Websites Log]]\n")
    (d / "Local Websites Backlog.md").write_text("# b\n")
    (d / "Local Websites Log.md").write_text("# l\n")
    pi = c.projects_index_path(vault)
    pi.write_text(pi.read_text() + "\n2. [[_Local Websites Index|Local Websites]]: x\n")


def test_workspace_check_passes_and_flags_problems(vault, projects):
    _ws_vault(vault)
    ws = projects / "Local_Websites"
    _repo(ws / "Connies", "https://github.com/arrowboy47/Connies.git")
    (ws / "AGENTS.md").write_text("x")
    (ws / "CLAUDE.md").write_text("@AGENTS.md\n")
    p = c.get_project("Local Websites", vault)
    assert check.check_project(p, vault) == []
    _repo(ws / "NoRemote")
    assert check.check_project(p, vault) == ["child repo NoRemote has no GitHub origin"]
    (ws / "AGENTS.md").unlink()
    assert any("missing AGENTS.md" in x for x in check.check_project(p, vault))


def test_workspace_layout_allowed(vault, projects):
    _ws_vault(vault)
    (projects / "Local_Websites").mkdir()
    assert check.check_layout(c.find_projects(vault), projects) == []


def test_status_workspace_not_a_problem_and_children_listed(projects):
    ws = projects / "Local_Websites"
    _repo(ws / "Connies", "https://github.com/arrowboy47/Connies.git")
    rows = {r["slug"]: r for r in status.scan(root=projects)}
    assert rows["Local_Websites"]["git"] is False
    assert status.local_problems(rows["Local_Websites"]) == []
    assert "Local_Websites/Connies" in rows


def test_plain_non_git_dir_still_a_problem(projects):
    (projects / "scratch").mkdir()
    row = {r["slug"]: r for r in status.scan(root=projects)}["scratch"]
    assert status.local_problems(row) == ["not a git repo"]


def test_new_project_workspace_creates_no_repo(vault, projects, monkeypatch):
    calls = []
    monkeypatch.setattr(new, "run", lambda cmd, cwd=None, timeout=60: calls.append(cmd) or
                        subprocess.CompletedProcess(cmd, 0, "", ""))
    rc = new.main(["Web Biz", "--kind", "workspace", "--slug", "Web_Biz",
                   "--description", "Websites for local businesses."])
    assert rc == 0 and calls == []
    assert (projects / "Web_Biz/AGENTS.md").is_file() and not (projects / "Web_Biz/.git").exists()
    idx = vault / "Projects/Web Biz/_Web Biz Index.md"
    meta, _ = c.parse_frontmatter(idx.read_text())
    assert meta["kind"] == "workspace" and meta["slug"] == "Web_Biz" and "repo" not in meta

import json
import subprocess

from projectkit import status

GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
KEYS = {"slug", "git", "branch", "head", "upstream", "ahead", "behind",
        "dirty", "origin", "last_commit"}


def _commit_all(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "snap"],
                   cwd=repo, check=True, capture_output=True)


def _json(capsys, argv):
    rc = status.main(["--json", *argv])
    return rc, json.loads(capsys.readouterr().out)


def _row(rows, slug):
    return next(r for r in rows if r["slug"] == slug)


def _full(slug, **kw):
    base = dict.fromkeys(KEYS)
    base.update(slug=slug, git=True, branch="main", head="abc1234", origin="x")
    base.update(kw)
    return base


def test_clean_repo_is_strict_clean(projects, capsys):
    _commit_all(projects / "demo-app")
    rc, rows = _json(capsys, ["--strict"])
    assert rc == 0
    demo = _row(rows, "demo-app")
    assert demo["git"] is True and demo["dirty"] == 0 and demo["origin"]


def test_dirty_file_makes_strict_fail(projects, capsys):
    repo = projects / "demo-app"
    _commit_all(repo)
    (repo / "scratch.txt").write_text("uncommitted\n")
    rc, rows = _json(capsys, ["--strict"])
    assert rc == 1
    assert _row(rows, "demo-app")["dirty"] == 1


def test_non_git_dir_reported_and_fails_strict(projects, capsys):
    _commit_all(projects / "demo-app")
    plain = projects / "scratch"
    plain.mkdir()
    (plain / "notes.txt").write_text("not a repo\n")
    rc, rows = _json(capsys, ["--strict"])
    assert rc == 1
    row = _row(rows, "scratch")
    assert row["git"] is False
    assert all(row[k] is None for k in KEYS - {"slug", "git"})


def test_archive_skipped_by_default_listed_with_all(projects, capsys):
    _commit_all(projects / "demo-app")
    archived = projects / "_archive" / "old-thing"
    archived.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=archived, check=True)
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "old"],
                   cwd=archived, check=True, capture_output=True)
    (projects / ".cache").mkdir()

    _, rows = _json(capsys, [])
    slugs = {r["slug"] for r in rows}
    assert "old-thing" not in slugs and "_archive" not in slugs and ".cache" not in slugs

    _, rows = _json(capsys, ["--all"])
    slugs = {r["slug"] for r in rows}
    assert "old-thing" in slugs and "demo-app" in slugs
    assert ".cache" not in slugs and "_archive" not in slugs


def test_json_has_exact_keys(projects, capsys):
    _commit_all(projects / "demo-app")
    rc, rows = _json(capsys, [])
    assert rc == 0 and rows
    for r in rows:
        assert set(r) == KEYS


def test_compare_covers_all_five_issues():
    local = [
        _full("both-same"),
        _full("branch-off", branch="dev"),
        _full("head-off", head="ffff"),
        _full("only-local"),
    ]
    remote = [
        _full("both-same"),
        _full("branch-off", branch="main"),
        _full("head-off", head="0000"),
        _full("only-remote"),
    ]
    rows = status.compare(local, remote)
    got = {r["slug"]: r["issue"] for r in rows}
    assert got == {
        "both-same": "",
        "branch-off": "branch-differs",
        "head-off": "head-differs",
        "only-local": "only-here",
        "only-remote": "only-there",
    }
    assert set(got.values()) == {"", "branch-differs", "head-differs", "only-here", "only-there"}
    for r in rows:
        assert set(r) == {"slug", "here", "there", "issue"}
    only_local = next(r for r in rows if r["slug"] == "only-local")
    assert only_local["here"] is True and only_local["there"] is False


def test_remote_uses_ssh_and_fails_strict_on_issue(projects, capsys, monkeypatch):
    _commit_all(projects / "demo-app")
    monkeypatch.delenv("PK_REMOTE_CMD", raising=False)
    remote_rows = [_full("demo-app", head="0000000"), _full("other-box")]
    real = status.run
    calls = []

    def fake(cmd, cwd=None, timeout=60):
        if cmd[0] == "ssh":
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(remote_rows), "")
        return real(cmd, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(status, "run", fake)
    rc, rows = _json(capsys, ["--remote", "jadu", "--strict"])
    assert len(calls) == 1
    assert calls[0] == ["ssh", "-o", "BatchMode=yes", "jadu", "projects-status --json"]
    assert rc == 1
    assert all(set(r) == {"slug", "here", "there", "issue"} for r in rows)
    assert _row(rows, "demo-app")["issue"] == "head-differs"
    assert _row(rows, "other-box")["issue"] == "only-there"


def test_fetch_failure_warns_and_continues(projects, capsys, monkeypatch):
    _commit_all(projects / "demo-app")
    real = status.run
    fetch_timeouts = []

    def fake(cmd, cwd=None, timeout=60):
        if cmd[:2] == ["git", "fetch"]:
            fetch_timeouts.append(timeout)
            return subprocess.CompletedProcess(cmd, 128, "", "could not resolve host\n")
        return real(cmd, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(status, "run", fake)
    rc = status.main(["--fetch", "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    assert fetch_timeouts == [30]
    rows = json.loads(captured.out)
    assert _row(rows, "demo-app")["git"] is True
    assert "warning" in captured.err and "demo-app" in captured.err

from projectkit import common as c


def test_parse_frontmatter_lists_and_quotes():
    meta, body = c.parse_frontmatter('---\na: 1\nb: "x: y"\nc: [p, "q r"]\nd:\n  - one\n  - two\n---\nBody\n')
    assert meta == {"a": "1", "b": "x: y", "c": ["p", "q r"], "d": ["one", "two"]}
    assert body == "Body\n"


def test_no_frontmatter():
    assert c.parse_frontmatter("hello") == ({}, "hello")


def test_dump_roundtrip():
    data = {"type": "project", "description": "Has: colon", "tags": ["project", "web"]}
    meta, _ = c.parse_frontmatter(c.dump_frontmatter(data) + "x")
    assert meta == data


def test_find_projects(vault):
    names = {p.name: p for p in c.find_projects(vault)}
    assert set(names) == {"Demo App", "Pond Build"}
    assert names["Demo App"].kind == "code" and names["Demo App"].slug == "demo-app"
    assert names["Pond Build"].folder.name == "pondbuild"
    assert names["Pond Build"].backlog.name == "Pond Build Backlog.md"
    assert c.get_project("demo-app", vault).name == "Demo App"
    assert c.get_project("pond build", vault).name == "Pond Build"


def test_render_template():
    out = c.render_template("backlog.md", name="X")
    assert "# X Backlog" in out and "{{" not in out


def test_rename_note_fixes_links(vault):
    old = vault / "Projects/Demo App/Demo App Log.md"
    (vault / "Ref.md").write_text("see [[Demo App Log]] and [[Demo App Log#2026|the log]] and [[Other]]\n")
    new = old.with_name("Demo App Journal.md")
    changed = c.rename_note(old, new, vault)
    assert new.exists() and not old.exists()
    assert (vault / "Ref.md").read_text() == (
        "see [[Demo App Journal|Demo App Log]] and [[Demo App Journal#2026|the log]] and [[Other]]\n")
    assert vault / "Ref.md" in changed


def test_rename_refuses_case_only(vault):
    import pytest
    old = vault / "Projects/Demo App/Demo App Log.md"
    with pytest.raises(ValueError):
        c.rename_note(old, old.with_name("demo app log.md"), vault)


def test_ambiguous_basename_only_same_folder(vault):
    a = vault / "A/Log.md"; b = vault / "B/Log.md"
    for p in (a, b):
        p.parent.mkdir(parents=True); p.write_text("x")
    (vault / "A/ref.md").write_text("[[Log]]")
    (vault / "B/ref.md").write_text("[[Log]]")
    c.rename_note(a, vault / "A/A Log.md", vault)
    assert (vault / "A/ref.md").read_text() == "[[A Log|Log]]"
    assert (vault / "B/ref.md").read_text() == "[[Log]]"


def test_add_to_projects_index(vault):
    assert c.add_to_projects_index("New One", "fresh", vault=vault)
    text = c.projects_index_path(vault).read_text()
    assert "2. [[_New One Index|New One]]: fresh" in text
    assert text.index("New One") < text.index("## Paused")
    assert not c.add_to_projects_index("New One", "fresh", vault=vault)

from datetime import date
from pathlib import Path

from projectkit import common, link

TODAY = date(2026, 11, 17)


def _projects(vault):
    return [p for p in common.find_projects(vault) if p.state != "archived"]


def _changes(vault):
    return {c.rel: c for c in link.plan(vault, _projects(vault), TODAY)}


def _transform(vault, text, rel="Reference/Guides/Scratch.md"):
    return link.transform(text, rel, _projects(vault), TODAY)


def test_agent_brief_gets_link_and_path_fix(vault):
    c = _changes(vault)["Reference/Guides/Agent Brief.md"]
    assert "Demo App code is" not in c.new.replace("[[_Demo App Index|Demo App]]", "")
    assert "[[_Demo App Index|Demo App]] code is in `~/projects/demo-app`." in c.new
    assert c.links == 1
    assert c.fixes == 1


def test_stack_log_old_daily_archive_and_obsidian_untouched(vault):
    changed = set(_changes(vault))
    assert "Reference/Guides/Stack Log.md" not in changed
    assert "Daily/2020-01-01.md" not in changed
    assert "Archive/old.md" not in changed
    assert ".obsidian/workspace.md" not in changed
    assert "Projects/Projects Index.md" not in changed


def test_history_line_untouched_while_body_mention_is_linked(vault):
    c = _changes(vault)["Reference/Note With History.md"]
    assert "We use [[_Demo App Index|Demo App]] daily." in c.new
    assert "- `[2026-01-01 10:00]` Demo App added\n" in c.new
    assert c.links == 1


def test_already_linked_note_gets_no_second_link(vault):
    text = "---\ntype: note\n---\nSee [[_Demo App Index|Demo App]] and Demo App again.\n"
    new, links, fixes = _transform(vault, text)
    assert new == text
    assert links == 0 and fixes == 0


def test_heading_mention_not_linked(vault):
    text = "# Demo App\n\n## Demo App notes\n\nDemo App ships.\n"
    new, links, _ = _transform(vault, text)
    assert new == "# Demo App\n\n## Demo App notes\n\n[[_Demo App Index|Demo App]] ships.\n"
    assert links == 1


def test_inline_code_mention_not_linked(vault):
    text = "Run `Demo App` now. Then Demo App ships.\n"
    new, links, _ = _transform(vault, text)
    assert new == "Run `Demo App` now. Then [[_Demo App Index|Demo App]] ships.\n"
    assert links == 1


def test_fenced_code_not_linked_but_path_fixed(vault):
    text = "Demo App here.\n\n```\nDemo App ~/Projects/x\n```\n"
    new, links, fixes = _transform(vault, text)
    assert new == "[[_Demo App Index|Demo App]] here.\n\n```\nDemo App ~/projects/x\n```\n"
    assert links == 1 and fixes == 1


def test_frontmatter_links_and_urls_protected(vault):
    text = ("---\ndescription: \"Demo App ~/Projects/x\"\n---\n"
            "See [Demo App](https://example.com/Demo App) and https://x.test/Demo App "
            "and [[Demo App Log]] then Demo App.\n")
    expected = ("---\ndescription: \"Demo App ~/Projects/x\"\n---\n"
                "See [Demo App](https://example.com/Demo App) and https://x.test/Demo App "
                "and [[Demo App Log]] then [[_Demo App Index|Demo App]].\n")
    new, links, fixes = _transform(vault, text)
    assert new == expected
    assert links == 1 and fixes == 0


def test_project_own_folder_untouched(vault):
    text = "Demo App notes.\n"
    new, links, _ = _transform(vault, text, rel="Projects/Demo App/Extra.md")
    assert new == text and links == 0


def test_include_note_rules():
    assert not link.include_note(Path("Archive/old.md"), TODAY)
    assert not link.include_note(Path("Templates/x.md"), TODAY)
    assert not link.include_note(Path("Daily/2020-01-01.md"), TODAY)
    assert not link.include_note(Path("Daily/notes.md"), TODAY)
    assert link.include_note(Path("Daily/2026-11-15.md"), TODAY)
    assert not link.include_note(Path("Reference/Guides/Stack Log.md"), TODAY)
    assert not link.include_note(Path("Projects/Demo App/Demo App Log.md"), TODAY)
    assert not link.include_note(Path("Projects/Projects Index.md"), TODAY)
    assert link.include_note(Path("Reference/Guides/Agent Brief.md"), TODAY)


def test_dry_run_prints_diff_and_writes_nothing(vault, capsys):
    brief = vault / "Reference/Guides/Agent Brief.md"
    before = brief.read_text(encoding="utf-8")
    assert link.main([]) == 0
    out = capsys.readouterr().out
    assert "--- a/Reference/Guides/Agent Brief.md" in out
    assert "+++ b/Reference/Guides/Agent Brief.md" in out
    assert out.strip().splitlines()[-1] == "files: 2, links: 2, path fixes: 1"
    assert brief.read_text(encoding="utf-8") == before


def test_apply_writes_and_second_dry_run_is_empty(vault, capsys):
    assert link.main(["--apply"]) == 0
    capsys.readouterr()
    brief = (vault / "Reference/Guides/Agent Brief.md").read_text(encoding="utf-8")
    assert "[[_Demo App Index|Demo App]]" in brief
    assert "~/projects/demo-app" in brief
    assert link.main([]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "files: 0, links: 0, path fixes: 0"


def test_project_filter_restricts_linking(vault, capsys):
    assert link.main(["--project", "Pond Build"]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "files: 1, links: 0, path fixes: 1"


def test_unknown_project_exits_2(vault, capsys):
    assert link.main(["--project", "Nope"]) == 2

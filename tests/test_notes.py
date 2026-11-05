"""Tests for notes (Note / NoteBook) and the note commands.

Contract under test:
- Note: non-blank text (stripped), tags lowercased without '#', only [letters digits _ -];
  edit keeps tags; remove_tag of a missing tag -> ValueError; matches text or tags
- NoteBook: ids start at 1, never reused; delete/get_note of unknown id -> KeyError
- add-note TEXT #tag: #words become tags; edit-note / delete-note / add-tag / remove-tag
  with a bad or unknown id -> message, nothing changed
- search-notes / find-tag / notes list "[id] text #tags"
- notes survive a restart
"""

import pytest

from personal_assistant import cli, commands, storage
from personal_assistant.notes import Note, NoteBook, normalize_tag
from personal_assistant.commands import (
    add_note,
    add_tag,
    delete_note,
    edit_note,
    find_tag,
    remove_tag,
    search_notes,
    show_notes,
)


class NoColor:
    def __getattr__(self, name):
        return ""


@pytest.fixture(autouse=True)
def no_colors(monkeypatch):
    monkeypatch.setattr(commands, "Fore", NoColor())
    monkeypatch.setattr(commands, "Style", NoColor())
    monkeypatch.setattr(cli, "Fore", NoColor())


def make_notes(*lines):
    """make_notes("Buy milk #shop", "Call mom") -> NoteBook with ids 1, 2, ..."""
    notes = NoteBook()
    for line in lines:
        add_note(line.split(), notes)
    return notes


# --- model -------------------------------------------------------------------

def test_note_strips_text_and_normalizes_tags():
    note = Note("  Buy milk ", ["#Shop", "URGENT", "to-do"])
    assert note.text == "Buy milk"
    assert note.tags == {"shop", "urgent", "to-do"}
    assert str(note) == "Buy milk #shop #to-do #urgent"


@pytest.mark.parametrize("bad", ["", "   "])
def test_note_text_required(bad):
    with pytest.raises(ValueError):
        Note(bad)


@pytest.mark.parametrize("bad", ["#", "a b", "tag!", ""])
def test_bad_tag(bad):
    with pytest.raises(ValueError):
        normalize_tag(bad)


def test_invalid_tag_adds_nothing():
    note = Note("x", ["a"])
    with pytest.raises(ValueError):
        note.add_tags("b", "bad tag!")
    assert note.tags == {"a"}


def test_edit_keeps_tags_and_remove_tag():
    note = Note("old", ["a", "b"])
    note.edit("new")
    note.remove_tag("#A")
    assert (note.text, note.tags) == ("new", {"b"})
    with pytest.raises(ValueError):
        note.remove_tag("a")


def test_ids_are_never_reused():
    notes = NoteBook()
    assert notes.add(Note("one")) == 1
    assert notes.add(Note("two")) == 2
    notes.delete(2)
    assert notes.add(Note("three")) == 3
    with pytest.raises(KeyError):
        notes.delete(2)
    with pytest.raises(KeyError):
        notes.get_note(2)


def test_search_text_and_tags_case_insensitive():
    notes = make_notes("Buy MILK #shop", "Call mom #family", "Shopping list")
    assert [i for i, _ in notes.search("milk")] == [1]
    assert [i for i, _ in notes.search("#SHOP")] == [1, 3]
    assert notes.search("nothing") == []


def test_by_tag_is_exact():
    notes = make_notes("a #shop", "b #shopping", "c #Shop")
    assert [i for i, _ in notes.by_tag("#shop")] == [1, 3]


# --- commands ----------------------------------------------------------------

def test_add_and_list_notes():
    notes = NoteBook()
    assert add_note(["Buy", "milk", "#shop", "#Urgent"], notes) == "Note 1 added."
    assert add_note(["Call", "mom"], notes) == "Note 2 added."
    assert show_notes([], notes) == "[1] Buy milk #shop #urgent\n[2] Call mom"


def test_empty_notebook_messages():
    notes = NoteBook()
    assert show_notes([], notes) == "No notes saved."
    assert search_notes(["x"], notes) == "No notes found."
    assert find_tag(["x"], notes) == "No notes with this tag."


@pytest.mark.parametrize("args", [[], ["#only", "#tags"]])
def test_add_note_needs_text(args):
    notes = NoteBook()
    assert add_note(args, notes) in (
        "Enter the argument for the command", "Note text must not be empty")
    assert len(notes) == 0


def test_edit_note_replaces_text_and_adds_tags():
    notes = make_notes("old text #a")
    assert edit_note(["1", "new", "text", "#b"], notes) == "Note updated."
    assert show_notes([], notes) == "[1] new text #a #b"


def test_edit_note_with_bad_tag_changes_nothing():
    notes = make_notes("old #a")
    assert edit_note(["1", "new", "#bad!"], notes).startswith("Tag may contain")
    assert show_notes([], notes) == "[1] old #a"


@pytest.mark.parametrize("handler, args", [
    (edit_note, ["9", "text"]),
    (delete_note, ["9"]),
    (add_tag, ["9", "x"]),
    (remove_tag, ["9", "x"]),
])
def test_unknown_note_id(handler, args):
    notes = make_notes("keep me")
    assert handler(args, notes) == "Note 9 not found."
    args[0] = "one"
    assert handler(args, notes) == "Note id must be a number"
    assert show_notes([], notes) == "[1] keep me"


def test_delete_note():
    notes = make_notes("a", "b")
    assert delete_note(["1"], notes) == "Note deleted."
    assert show_notes([], notes) == "[2] b"


def test_add_and_remove_tags():
    notes = make_notes("text")
    assert add_tag(["1", "#Work", "home"], notes) == "Tags added."
    assert remove_tag(["1", "home"], notes) == "Tag removed."
    assert remove_tag(["1", "home"], notes) == "Note has no tag #home"
    assert show_notes([], notes) == "[1] text #work"


def test_search_and_find_tag_commands():
    notes = make_notes("Buy milk #shop", "Call mom #family", "milk again")
    assert search_notes(["milk"], notes) == "[1] Buy milk #shop\n[3] milk again"
    assert find_tag(["#family"], notes) == "[2] Call mom #family"


def test_note_handlers_reject_address_book():
    from personal_assistant.contacts import AddressBook
    assert show_notes([], AddressBook()) == "Invalid input type."


# --- persistence ---------------------------------------------------------------

def test_notes_survive_restart(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    for lines in (["add-note Buy milk #shop", "exit"], ["notes", "exit"]):
        feed = iter(lines)
        monkeypatch.setattr(cli, "_read", lambda _prompt: next(feed))
        cli.main()
    assert "[1] Buy milk #shop" in capsys.readouterr().out.splitlines()
    assert len(storage.load_data(tmp_path / storage.NOTES_FILE, NoteBook)) == 1


def test_sort_notes_by_tags_untagged_last():
    from personal_assistant.commands import sort_notes
    notes = make_notes("plain", "z #zoo", "b #b #x", "a2 #a", "a1 #a #c")
    assert sort_notes([], notes) == "\n".join([
        "[4] a2 #a",
        "[5] a1 #a #c",
        "[3] b #b #x",
        "[2] z #zoo",
        "[1] plain",
    ])

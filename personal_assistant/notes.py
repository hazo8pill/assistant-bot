"""Notes model: Note (text + tags) and NoteBook (notes keyed by a numeric id).

Errors follow the commands' input_error decorator:
ValueError -> invalid text/tag, KeyError -> unknown note id,
TypeError  -> argument of the wrong type (nothing is changed).
"""

import re
from collections import UserDict
from datetime import date

TAG_PATTERN = r"[\w-]+"


def _require_str(value, what: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a str")


def normalize_tag(tag: str) -> str:
    """'#Work' -> 'work'. Tags are letters, digits, '_' or '-'; else ValueError."""
    _require_str(tag, "Tag")
    tag = tag.strip().lstrip("#").lower()
    if not re.fullmatch(TAG_PATTERN, tag):
        raise ValueError("Tag may contain only letters, digits, '_' and '-'")
    return tag


class Note:
    """A text note with a set of lowercase tags and its creation date."""

    def __init__(self, text: str, tags=()):
        self.text = self._clean(text)
        self.tags = set()
        self.created = date.today()
        self.add_tags(*tags)

    @staticmethod
    def _clean(text: str) -> str:
        _require_str(text, "Note text")
        if not text.strip():
            raise ValueError("Note text must not be empty")
        return text.strip()

    def edit(self, text: str) -> None:
        """Replace the text (tags are kept). Blank -> ValueError."""
        self.text = self._clean(text)

    def add_tags(self, *tags: str) -> None:
        """Add tags ('#' optional, any case). An invalid tag -> ValueError, nothing added."""
        self.tags |= {normalize_tag(t) for t in tags}

    def remove_tag(self, tag: str) -> None:
        """Remove a tag. Missing -> ValueError."""
        tag = normalize_tag(tag)
        if tag not in self.tags:
            raise ValueError(f"Note has no tag #{tag}")
        self.tags.remove(tag)

    def matches(self, query: str) -> bool:
        """True if query (case-insensitive) is in the text or in one of the tags."""
        _require_str(query, "Query")
        query = query.casefold().lstrip("#")
        return query in self.text.casefold() or any(query in t for t in self.tags)

    def __str__(self):
        tags = " ".join(f"#{t}" for t in sorted(self.tags))
        return f"{self.text} {tags}".rstrip()


class NoteBook(UserDict):
    """Notes keyed by int id. Ids start at 1 and are never reused after delete."""

    def __init__(self):
        super().__init__()
        self.next_id = 1

    def add(self, note: Note) -> int:
        """Store the note and return its new id."""
        if not isinstance(note, Note):
            raise TypeError("note must be a Note")
        note_id = self.next_id
        self.data[note_id] = note
        self.next_id += 1
        return note_id

    def get_note(self, note_id: int) -> Note:
        """The note with this id. Unknown id -> KeyError."""
        return self.data[note_id]

    def delete(self, note_id: int) -> None:
        """Delete the note. Unknown id -> KeyError."""
        del self.data[note_id]

    def search(self, query: str) -> list[tuple[int, Note]]:
        """(id, note) pairs whose text or tags contain query, by id."""
        return [(i, n) for i, n in self.data.items() if n.matches(query)]

    def by_tag(self, tag: str) -> list[tuple[int, Note]]:
        """(id, note) pairs that have exactly this tag, by id."""
        tag = normalize_tag(tag)
        return [(i, n) for i, n in self.data.items() if tag in n.tags]

    def sorted_by_tags(self) -> list[tuple[int, Note]]:
        """
        All (id, note) pairs ordered alphabetically by their sorted tags
        (#a #c before #b), untagged notes last; ties keep id order.
        """

        def sort_key(item: tuple[int, Note]):
            note_id, note = item
            return not note.tags, sorted(note.tags), note_id

        return sorted(self.data.items(), key=sort_key)

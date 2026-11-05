"""Command handlers for the assistant: contacts and notes.

Every handler takes (args, store) — args are the words typed after the command,
store is the AddressBook or NoteBook it works on — and returns the text to show.
Handlers raise on bad input; the input_error decorator turns those exceptions
into red messages, so the assistant never stops on bad input.

COMMANDS maps each command name to its handler, store and help text; the CLI
uses it for dispatch, `help`, Tab-completion and "Did you mean ...?".
"""

from functools import wraps

from colorama import Fore, Style

from .contacts import DEFAULT_DAYS, AddressBook, Phone, Record
from .notes import Note, NoteBook

# --- colors ------------------------------------------------------------------


def paint(text: str, color: str) -> str:
    """text in a colorama color, reset afterwards."""
    return f"{color}{text}{Style.RESET_ALL}"


def ok(message: str) -> str:
    """A success message (green)."""
    return paint(message, Fore.GREEN)


def err(message: str) -> str:
    """An error message (red)."""
    return paint(message, Fore.RED)


# --- error handling & argument checks ----------------------------------------


def input_error(func):
    """
    Turn user-input exceptions raised by a command handler into red messages.

    IndexError -> "Enter the argument for the command"   (wrong arg count)
    ValueError -> the exception's own message           (bad value, phone/note not found)
    KeyError   -> "Contact not found."
    TypeError  -> "Invalid input type."
    Any other exception propagates unchanged.
    """

    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IndexError:
            return err("Enter the argument for the command")
        except ValueError as e:
            return err(str(e))
        except KeyError:
            return err("Contact not found.")
        except TypeError:
            return err("Invalid input type.")

    return inner


def _check_types(args, store, cls=AddressBook) -> None:
    """Raise TypeError unless args is a list/tuple of str and store is a cls."""
    if not isinstance(args, (list, tuple)) or not all(isinstance(a, str) for a in args):
        raise TypeError("args must be a list or tuple of str")
    if not isinstance(store, cls):
        raise TypeError(f"store must be a {cls.__name__}")


def _check_count(args, *counts: int) -> None:
    """Raise IndexError unless len(args) is one of counts."""
    if len(args) not in counts:
        raise IndexError("wrong number of arguments")


def _check_min(args, minimum: int) -> None:
    """Raise IndexError if there are fewer than minimum args."""
    if len(args) < minimum:
        raise IndexError("not enough arguments")


def parse_input(user_input: str) -> tuple[str, ...]:
    """
    Split a command line into a lowercased command and its arguments.

    Returns (command, *args); arguments keep their casing. A blank line gives ("",).
    Raises TypeError if user_input is not a str.
    """
    if not isinstance(user_input, str):
        raise TypeError("user_input must be a str")
    cmd, *args = user_input.split() or [""]
    return cmd.lower(), *args


# --- contacts: helpers -------------------------------------------------------


def _find_record(name: str, book: AddressBook) -> Record | None:
    """Return the record whose name matches case-insensitively, or None."""
    folded = name.casefold()
    return next((r for key, r in book.data.items() if key.casefold() == folded), None)


def _get_record(name: str, book: AddressBook) -> Record:
    """Like _find_record, but raise KeyError if there is no such contact."""
    record = _find_record(name, book)
    if record is None:
        raise KeyError(name)
    return record


def _phones(record: Record) -> str:
    return "; ".join(p.value for p in record.phones) or "no phones"


def _describe(record: Record) -> str:
    """'John: 1234567890; 5555555555' plus birthday, email and address when set."""
    text = f"{paint(record.name.value, Fore.CYAN)}: {_phones(record)}"
    for label in ("birthday", "email", "address"):
        value = getattr(record, label)
        if value is not None:
            text += f", {label}: {value}"
    return text


# --- contacts: handlers ------------------------------------------------------


@input_error
def add_contact(args: list[str], book: AddressBook) -> str:
    """
    add NAME PHONE: create the contact, or add PHONE to an existing one.

    Returns "Contact added." for a new contact, "Contact updated." otherwise.
    A phone the contact already has is not added twice.
    """
    _check_types(args, book)
    _check_count(args, 2)
    name, phone = args
    record = _find_record(name, book)
    if record is None:
        record = Record(name)
        record.add_phone(phone)
        book.add_record(record)
        return ok("Contact added.")
    if record.find_phone(phone) is None:
        record.add_phone(phone)
    return ok("Contact updated.")


@input_error
def change_contact(args: list[str], book: AddressBook) -> str:
    """
    change NAME NEW      -> the contact's phones become just NEW
    change NAME OLD NEW  -> OLD is replaced by NEW

    Returns "Contact updated."; the book changes only on success.
    """
    _check_types(args, book)
    _check_count(args, 2, 3)
    name, *phones = args
    record = _get_record(name, book)
    if len(phones) == 1:
        record.phones = [Phone(phones[0])]
    else:
        record.edit_phone(*phones)
    return ok("Contact updated.")


@input_error
def remove_phone(args: list[str], book: AddressBook) -> str:
    """remove-phone NAME PHONE: delete one of the contact's phones."""
    _check_types(args, book)
    _check_count(args, 2)
    name, phone = args
    _get_record(name, book).remove_phone(phone)
    return ok("Phone removed.")


@input_error
def delete_contact(args: list[str], book: AddressBook) -> str:
    """delete NAME: remove the contact from the book."""
    _check_types(args, book)
    _check_count(args, 1)
    book.delete(_get_record(args[0], book).name.value)
    return ok("Contact deleted.")


@input_error
def show_phone(args: list[str], book: AddressBook) -> str:
    """phone NAME: the contact's phones joined by "; ". Extra args are ignored."""
    _check_types(args, book)
    return _phones(_get_record(args[0], book))


@input_error
def show_all(args: list[str], book: AddressBook) -> str:
    """One line per contact (see _describe), or "No contacts saved." if empty."""
    _check_types(args, book)
    if not book:
        return "No contacts saved."
    return "\n".join(_describe(record) for record in book.data.values())


@input_error
def search_contacts(args: list[str], book: AddressBook) -> str:
    """search QUERY: contacts whose name, phone, email, address or birthday contains QUERY."""
    _check_types(args, book)
    _check_min(args, 1)
    found = book.search(" ".join(args))
    if not found:
        return "No contacts found."
    return "\n".join(_describe(record) for record in found)


@input_error
def add_email(args: list[str], book: AddressBook) -> str:
    """add-email NAME EMAIL: set (or replace) the contact's e-mail."""
    _check_types(args, book)
    _check_count(args, 2)
    name, email = args
    _get_record(name, book).set_email(email)
    return ok("Email saved.")


@input_error
def add_address(args: list[str], book: AddressBook) -> str:
    """add-address NAME ADDRESS...: set (or replace) the contact's address (may contain spaces)."""
    _check_types(args, book)
    _check_min(args, 2)
    name, *address = args
    _get_record(name, book).set_address(" ".join(address))
    return ok("Address saved.")


@input_error
def add_birthday(args: list[str], book: AddressBook) -> str:
    """add-birthday NAME DD.MM.YYYY: set (or replace) the contact's birthday."""
    _check_types(args, book)
    _check_count(args, 2)
    name, birthday = args
    _get_record(name, book).add_birthday(birthday)
    return ok("Birthday added.")


@input_error
def show_birthday(args: list[str], book: AddressBook) -> str:
    """show-birthday NAME: "DD.MM.YYYY", or "NAME has no birthday set.". Extra args ignored."""
    _check_types(args, book)
    record = _get_record(args[0], book)
    if record.birthday is None:
        return f"{record.name.value} has no birthday set."
    return str(record.birthday)


@input_error
def birthdays(args: list[str], book: AddressBook) -> str:
    """
    birthdays [DAYS]: one "name: DD.MM.YYYY" line per contact to congratulate in
    the next DAYS days (default 7, today included; weekends moved to Monday).
    """
    _check_types(args, book)
    _check_count(args, 0, 1)
    days = DEFAULT_DAYS
    if args:
        if not args[0].isdecimal():
            raise ValueError("Number of days must be a positive integer")
        days = int(args[0])
    upcoming = book.get_upcoming_birthdays(days=days)
    if not upcoming:
        return f"No birthdays in the next {days} days."
    return "\n".join(
        f"{paint(u['name'], Fore.CYAN)}: {u['congratulation_date']}" for u in upcoming
    )


# --- notes: helpers ----------------------------------------------------------


def _split_tags(words: list[str]) -> tuple[str, list[str]]:
    """['Buy', 'milk', '#shop'] -> ('Buy milk', ['#shop'])."""
    tags = [w for w in words if w.startswith("#")]
    text = " ".join(w for w in words if not w.startswith("#"))
    return text, tags


def _get_note(note_id: str, notes: NoteBook) -> tuple[int, Note]:
    """Parse the id typed by the user and return (id, note). Bad or unknown id -> ValueError."""
    if not note_id.isdecimal():
        raise ValueError("Note id must be a number")
    if int(note_id) not in notes:
        raise ValueError(f"Note {note_id} not found.")
    return int(note_id), notes.get_note(int(note_id))


def _show_note(note_id: int, note: Note) -> str:
    """'[3] Buy milk #shop' with the id and tags colored."""
    tags = " ".join(paint(f"#{t}", Fore.MAGENTA) for t in sorted(note.tags))
    return f"{paint(f'[{note_id}]', Fore.YELLOW)} {note.text} {tags}".rstrip()


def _show_notes(items: list[tuple[int, Note]], empty: str) -> str:
    return "\n".join(_show_note(i, n) for i, n in items) if items else empty


# --- notes: handlers ---------------------------------------------------------


@input_error
def add_note(args: list[str], notes: NoteBook) -> str:
    """add-note TEXT... [#tag ...]: new note; words starting with # become tags."""
    _check_types(args, notes, NoteBook)
    _check_min(args, 1)
    text, tags = _split_tags(args)
    note_id = notes.add(Note(text, tags))
    return ok(f"Note {note_id} added.")


@input_error
def show_notes(args: list[str], notes: NoteBook) -> str:
    """notes: every note, by id."""
    _check_types(args, notes, NoteBook)
    return _show_notes(list(notes.items()), "No notes saved.")


@input_error
def edit_note(args: list[str], notes: NoteBook) -> str:
    """edit-note ID TEXT... [#tag ...]: replace the note's text; #words are added as tags."""
    _check_types(args, notes, NoteBook)
    _check_min(args, 2)
    _, note = _get_note(args[0], notes)
    text, tags = _split_tags(args[1:])
    Note(text, tags)  # validate everything first, so a bad tag changes nothing
    note.edit(text)
    note.add_tags(*tags)
    return ok("Note updated.")


@input_error
def delete_note(args: list[str], notes: NoteBook) -> str:
    """delete-note ID: remove the note."""
    _check_types(args, notes, NoteBook)
    _check_count(args, 1)
    note_id, _ = _get_note(args[0], notes)
    notes.delete(note_id)
    return ok("Note deleted.")


@input_error
def search_notes(args: list[str], notes: NoteBook) -> str:
    """search-notes QUERY: notes whose text or tags contain QUERY."""
    _check_types(args, notes, NoteBook)
    _check_min(args, 1)
    return _show_notes(notes.search(" ".join(args)), "No notes found.")


@input_error
def add_tag(args: list[str], notes: NoteBook) -> str:
    """add-tag ID TAG...: add tags to the note ('#' optional)."""
    _check_types(args, notes, NoteBook)
    _check_min(args, 2)
    _, note = _get_note(args[0], notes)
    note.add_tags(*args[1:])
    return ok("Tags added.")


@input_error
def remove_tag(args: list[str], notes: NoteBook) -> str:
    """remove-tag ID TAG: remove one tag from the note."""
    _check_types(args, notes, NoteBook)
    _check_count(args, 2)
    _, note = _get_note(args[0], notes)
    note.remove_tag(args[1])
    return ok("Tag removed.")


@input_error
def find_tag(args: list[str], notes: NoteBook) -> str:
    """find-tag TAG: notes that have exactly this tag."""
    _check_types(args, notes, NoteBook)
    _check_count(args, 1)
    return _show_notes(notes.by_tag(args[0]), "No notes with this tag.")


@input_error
def sort_notes(args: list[str], notes: NoteBook) -> str:
    """sort-notes: every note, ordered by tags."""
    _check_types(args, notes, NoteBook)
    return _show_notes(notes.sorted_by_tags(), "No notes saved.")


# --- command table -----------------------------------------------------------

CONTACTS = "contacts"
NOTES = "notes"

# name: (handler, store, usage, description)
COMMANDS = {
    "add": (add_contact, CONTACTS, "add NAME PHONE", "add a contact or another phone"),
    "change": (change_contact, CONTACTS, "change NAME [OLD] NEW", "replace a phone"),
    "remove-phone": (remove_phone, CONTACTS, "remove-phone NAME PHONE", "delete a phone"),
    "delete": (delete_contact, CONTACTS, "delete NAME", "delete a contact"),
    "phone": (show_phone, CONTACTS, "phone NAME", "show a contact's phones"),
    "all": (show_all, CONTACTS, "all", "list all contacts"),
    "search": (search_contacts, CONTACTS, "search QUERY", "find contacts by any field"),
    "add-email": (add_email, CONTACTS, "add-email NAME EMAIL", "set a contact's email"),
    "add-address": (add_address, CONTACTS, "add-address NAME ADDRESS", "set a contact's address"),
    "add-birthday": (add_birthday, CONTACTS, "add-birthday NAME DD.MM.YYYY", "set a birthday"),
    "show-birthday": (show_birthday, CONTACTS, "show-birthday NAME", "show a birthday"),
    "birthdays": (birthdays, CONTACTS, "birthdays [DAYS]", "birthdays in the next DAYS days (7)"),
    "add-note": (add_note, NOTES, "add-note TEXT [#tag ...]", "add a note"),
    "notes": (show_notes, NOTES, "notes", "list all notes"),
    "edit-note": (edit_note, NOTES, "edit-note ID TEXT [#tag ...]", "replace a note's text"),
    "delete-note": (delete_note, NOTES, "delete-note ID", "delete a note"),
    "search-notes": (search_notes, NOTES, "search-notes QUERY", "find notes by text or tag"),
    "add-tag": (add_tag, NOTES, "add-tag ID TAG [TAG ...]", "tag a note"),
    "remove-tag": (remove_tag, NOTES, "remove-tag ID TAG", "untag a note"),
    "find-tag": (find_tag, NOTES, "find-tag TAG", "notes with this tag"),
    "sort-notes": (sort_notes, NOTES, "sort-notes", "list notes ordered by tags"),
}

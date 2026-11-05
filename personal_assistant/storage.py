"""Keep the address book and the notes on disk between runs (pickle).

Everything lives in DATA_DIR (~/.personal_assistant): contacts.pkl, notes.pkl
and the command history.
"""

import os
import pickle
from pathlib import Path

from .contacts import AddressBook
from .notes import NoteBook

DATA_DIR = Path.home() / ".personal_assistant"
CONTACTS_FILE = "contacts.pkl"
NOTES_FILE = "notes.pkl"
STORABLE = (AddressBook, NoteBook)


def _require_path(filename) -> None:
    # open() would treat an int as a file descriptor, so only real paths get through.
    if not isinstance(filename, (str, os.PathLike)):
        raise TypeError("filename must be a str or path")


def save_data(book, filename) -> None:
    """
    Pickle an AddressBook or NoteBook into filename, creating its folder if needed.

    Raises TypeError for any other object or a bad filename. Writes a temp file
    first and renames it over the target, so a failed save never leaves a
    half-written (or emptied) file behind.
    """
    if not isinstance(book, STORABLE):
        raise TypeError("book must be an AddressBook or NoteBook")
    _require_path(filename)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{os.fspath(filename)}.tmp"
    with open(tmp, "wb") as f:
        pickle.dump(book, f)
    os.replace(tmp, filename)


def load_data(filename, cls=AddressBook):
    """
    Load what save_data wrote; a missing file gives a new empty cls().

    Raises TypeError for a bad filename or a file not holding a cls,
    ValueError for a file that can't be unpickled. The file is never modified.
    """
    _require_path(filename)
    try:
        with open(filename, "rb") as f:
            book = pickle.load(f)
    except FileNotFoundError:
        return cls()
    except OSError:
        raise
    except Exception as e:  # pickle can fail with many error types on junk input
        raise ValueError(f"{filename} is not a valid data file") from e
    if not isinstance(book, cls):
        raise TypeError(f"{filename} does not contain a {cls.__name__}")
    return book

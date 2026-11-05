"""Unit tests for bot (CLI assistant backed by AddressBook, with birthdays).

Contract under test (hw-05 behaviour, adapted to the hw-06 model):
- input_error: IndexError -> "Enter the argument for the command",
  ValueError -> its own message (e.g. bad phone), KeyError -> "Contact not found.",
  TypeError -> "Invalid input type."; other exceptions propagate; functools.wraps
- every command handler is wrapped by input_error
- parse_input: (cmd lowercased, *args as typed); blank -> ("",); non-str -> TypeError
- names case-insensitive, stored as first typed
- add: new name -> new record; existing name -> phone appended (no duplicates)
- change NAME NEW -> contact has only NEW; change NAME OLD NEW -> OLD replaced
- phone / all list every phone joined by "; "; all also shows the birthday if set
- add-birthday NAME DD.MM.YYYY -> "Birthday added." (replaces an old one)
- show-birthday NAME -> "DD.MM.YYYY" or "NAME has no birthday set."
- birthdays -> "name: DD.MM.YYYY" lines for the next 7 days, or "No birthdays in the next 7 days."
- wrong arg count / unknown name / bad phone / bad types -> message, book untouched
- main: all print/input; exit/close (any case), EOF or Ctrl-C -> "Good bye!"
- main loads contacts.pkl / notes.pkl from DATA_DIR at startup and saves them on every exit
  (close/exit, EOF, Ctrl-C); a corrupted file -> error message, bot quits, file untouched

Run: python -m pytest -v
"""

import pickle
from datetime import date

import pytest

from personal_assistant import cli, commands, contacts, storage
from personal_assistant.contacts import AddressBook, Record
from personal_assistant.storage import load_data, save_data
from personal_assistant.commands import (
    add_address,
    add_email,
    delete_contact,
    remove_phone,
    search_contacts,
    add_birthday,
    add_contact,
    birthdays,
    change_contact,
    input_error,
    parse_input,
    show_all,
    show_birthday,
    show_phone,
)

ENTER_ARG = "Enter the argument for the command"
NOT_FOUND = "Contact not found."
BAD_TYPE = "Invalid input type."
BAD_PHONE = "Phone must be exactly 10 digits"
BAD_DATE = "Invalid date format. Use DD.MM.YYYY"
NO_BIRTHDAYS = "No birthdays in the next 7 days."
WELCOME = "Welcome to the assistant bot! Type 'help' to see all commands."


class NoColor:
    """Stands in for colorama's Fore / Style: every color is ''."""

    def __getattr__(self, name):
        return ""


@pytest.fixture(autouse=True)
def no_colors(monkeypatch):
    """Compare plain text; test_colors checks the real colors."""
    monkeypatch.setattr(commands, "Fore", NoColor())
    monkeypatch.setattr(commands, "Style", NoColor())
    monkeypatch.setattr(cli, "Fore", NoColor())


P1, P2, P3 = "1234567890", "0987654321", "5555555555"


def make_book(**contacts):
    """make_book(John=[P1, P2]) -> AddressBook with those records."""
    book = AddressBook()
    for name, phones in contacts.items():
        record = Record(name)
        for phone in phones:
            record.add_phone(phone)
        book.add_record(record)
    return book


def snapshot(book):
    """{name: [phones]} for easy equality checks."""
    return {name: [p.value for p in r.phones] for name, r in book.data.items()}


def birthday_of(book, name):
    """The record's birthday as "DD.MM.YYYY", or None."""
    birthday = book.find(name).birthday
    return birthday and str(birthday)


class FrozenDate(date):
    """date whose today() is Monday 22.01.2024 (window: 22.01 .. 28.01)."""

    @classmethod
    def today(cls):
        return cls(2024, 1, 22)


@pytest.fixture
def frozen_today(monkeypatch):
    monkeypatch.setattr(contacts, "date", FrozenDate)


# --- input_error -------------------------------------------------------------

def raiser(exc):
    @input_error
    def handler(*args, **kwargs):
        raise exc

    return handler


@pytest.mark.parametrize("exc, message", [
    (IndexError("list index out of range"), ENTER_ARG),
    (ValueError(BAD_PHONE), BAD_PHONE),
    (KeyError("John"), NOT_FOUND),
    (TypeError("args must be a list"), BAD_TYPE),
])
def test_decorator_maps_exceptions_to_messages(exc, message):
    assert raiser(exc)(["John"], AddressBook()) == message


def test_decorator_lets_other_exceptions_propagate():
    with pytest.raises(RuntimeError):
        raiser(RuntimeError("boom"))()


def test_decorator_passes_result_and_arguments_through():
    @input_error
    def echo(*args, **kwargs):
        return args, kwargs

    assert echo(1, 2, key="v") == ((1, 2), {"key": "v"})


@pytest.mark.parametrize("handler", [h for h, *_ in commands.COMMANDS.values()])
def test_every_handler_is_decorated(handler):
    assert hasattr(handler, "__wrapped__")
    assert handler.__name__ == handler.__wrapped__.__name__


# --- parse_input -------------------------------------------------------------

def test_parse_splits_command_and_args():
    assert parse_input("add John 123") == ("add", "John", "123")


def test_parse_lowercases_command_only():
    assert parse_input("ADD John 123") == ("add", "John", "123")
    assert parse_input("HeLLo") == ("hello",)


def test_parse_ignores_extra_whitespace():
    assert parse_input("   phone    John  \n") == ("phone", "John")


@pytest.mark.parametrize("line", ["", "   ", "\t\n"])
def test_parse_blank_line(line):
    assert parse_input(line) == ("",)


@pytest.mark.parametrize("bad", [None, 123, b"add", ["add", "John"]])
def test_parse_rejects_non_str(bad):
    with pytest.raises(TypeError):
        parse_input(bad)


# --- add_contact -------------------------------------------------------------

def test_add_contact():
    book = AddressBook()
    assert add_contact(["John", P1], book) == "Contact added."
    assert snapshot(book) == {"John": [P1]}
    assert isinstance(book.find("John"), Record)


def test_add_accepts_tuple_args():
    book = AddressBook()
    add_contact(("John", P1), book)
    assert snapshot(book) == {"John": [P1]}


def test_add_existing_appends_phone_and_keeps_original_casing():
    book = make_book(John=[P1])
    assert add_contact(["JOHN", P2], book) == "Contact updated."
    assert snapshot(book) == {"John": [P1, P2]}


def test_add_existing_phone_is_not_duplicated():
    book = make_book(John=[P1])
    assert add_contact(["john", P1], book) == "Contact updated."
    assert snapshot(book) == {"John": [P1]}


@pytest.mark.parametrize("phone", ["123", "phone12345", "+380501234567"])
def test_add_invalid_phone_creates_nothing(phone):
    book = make_book(Ann=[P3])
    assert add_contact(["John", phone], book) == BAD_PHONE
    assert snapshot(book) == {"Ann": [P3]}


def test_add_invalid_phone_to_existing_contact():
    book = make_book(John=[P1])
    assert add_contact(["John", "123"], book) == BAD_PHONE
    assert snapshot(book) == {"John": [P1]}


@pytest.mark.parametrize("args", [[], ["John"], ["John", P1, "extra"]])
def test_add_wrong_arg_count(args):
    book = make_book(Ann=[P3])
    assert add_contact(args, book) == ENTER_ARG
    assert snapshot(book) == {"Ann": [P3]}


# --- change_contact ----------------------------------------------------------

def test_change_replaces_all_phones_case_insensitive():
    book = make_book(John=[P1, P3])
    assert change_contact(["john", P2], book) == "Contact updated."
    assert snapshot(book) == {"John": [P2]}


def test_change_one_phone_of_many():
    book = make_book(John=[P1, P3])
    assert change_contact(["John", P1, P2], book) == "Contact updated."
    assert snapshot(book) == {"John": [P2, P3]}


def test_change_missing_old_phone():
    book = make_book(John=[P1])
    assert change_contact(["John", P3, P2], book) == f"Phone {P3} not found"
    assert snapshot(book) == {"John": [P1]}


@pytest.mark.parametrize("args", [["John", "123"], ["John", P1, "123"]])
def test_change_to_invalid_phone(args):
    book = make_book(John=[P1])
    assert change_contact(args, book) == BAD_PHONE
    assert snapshot(book) == {"John": [P1]}


def test_change_unknown_contact():
    book = make_book(John=[P1])
    assert change_contact(["Ann", P3], book) == NOT_FOUND
    assert snapshot(book) == {"John": [P1]}


@pytest.mark.parametrize("args", [[], ["John"], ["John", P1, P2, P3]])
def test_change_wrong_arg_count(args):
    book = make_book(John=[P1])
    assert change_contact(args, book) == ENTER_ARG
    assert snapshot(book) == {"John": [P1]}


# --- show_phone --------------------------------------------------------------

def test_show_phone_case_insensitive():
    assert show_phone(["JOHN"], make_book(John=[P1])) == P1


def test_show_phone_lists_all_phones():
    assert show_phone(["John"], make_book(John=[P1, P2])) == f"{P1}; {P2}"


def test_show_phone_unknown_contact():
    assert show_phone(["Ann"], make_book(John=[P1])) == NOT_FOUND


def test_show_phone_without_name():
    assert show_phone([], make_book(John=[P1])) == ENTER_ARG


def test_show_phone_ignores_extra_args():
    assert show_phone(["John", "extra"], make_book(John=[P1])) == P1


# --- show_all ----------------------------------------------------------------

def test_show_all_empty():
    assert show_all([], AddressBook()) == "No contacts saved."


def test_show_all_in_insertion_order():
    book = make_book(John=[P1, P2], Ann=[P3])
    assert show_all([], book) == f"John: {P1}; {P2}\nAnn: {P3}"


def test_show_all_with_birthday():
    book = make_book(John=[P1], Ann=[P3])
    book.find("John").add_birthday("01.02.1990")
    assert show_all([], book) == f"John: {P1}, birthday: 01.02.1990\nAnn: {P3}"


# --- add_birthday --------------------------------------------------------------

def test_add_birthday_case_insensitive():
    book = make_book(John=[P1])
    assert add_birthday(["john", "01.02.1990"], book) == "Birthday added."
    assert birthday_of(book, "John") == "01.02.1990"


def test_add_birthday_replaces_old_one():
    book = make_book(John=[P1])
    add_birthday(["John", "01.02.1990"], book)
    assert add_birthday(["John", "03.04.1985"], book) == "Birthday added."
    assert birthday_of(book, "John") == "03.04.1985"


@pytest.mark.parametrize("bad", ["1990-02-01", "1.2.1990", "31.02.1990", "01.02.3000"])
def test_add_birthday_invalid_date(bad):
    book = make_book(John=[P1])
    add_birthday(["John", "01.02.1990"], book)
    assert add_birthday(["John", bad], book) == BAD_DATE
    assert birthday_of(book, "John") == "01.02.1990"


def test_add_birthday_unknown_contact():
    book = make_book(John=[P1])
    assert add_birthday(["Ann", "01.02.1990"], book) == NOT_FOUND
    assert snapshot(book) == {"John": [P1]}


@pytest.mark.parametrize("args", [[], ["John"], ["John", "01.02.1990", "extra"]])
def test_add_birthday_wrong_arg_count(args):
    book = make_book(John=[P1])
    assert add_birthday(args, book) == ENTER_ARG
    assert birthday_of(book, "John") is None


# --- show_birthday -------------------------------------------------------------

def test_show_birthday():
    book = make_book(John=[P1])
    book.find("John").add_birthday("01.02.1990")
    assert show_birthday(["JOHN"], book) == "01.02.1990"


def test_show_birthday_not_set():
    assert show_birthday(["john"], make_book(John=[P1])) == "John has no birthday set."


def test_show_birthday_unknown_contact():
    assert show_birthday(["Ann"], make_book(John=[P1])) == NOT_FOUND


def test_show_birthday_without_name():
    assert show_birthday([], make_book(John=[P1])) == ENTER_ARG


# --- birthdays -----------------------------------------------------------------

def test_birthdays_lists_next_week_with_weekend_on_monday(frozen_today):
    book = make_book(Sat=[P1], NoDate=[P2], Tue=[P3], Past=[P1])
    book.find("Sat").add_birthday("27.01.1990")
    book.find("Tue").add_birthday("23.01.1985")
    book.find("Past").add_birthday("21.01.1990")
    assert birthdays([], book) == "Tue: 23.01.2024\nSat: 29.01.2024"


def test_birthdays_none_upcoming(frozen_today):
    book = make_book(John=[P1])
    book.find("John").add_birthday("21.01.1990")
    assert birthdays([], book) == NO_BIRTHDAYS


def test_birthdays_empty_book():
    assert birthdays([], AddressBook()) == NO_BIRTHDAYS


def test_birthdays_custom_number_of_days(frozen_today):
    # today is Mon 22.01.2024; "birthdays 2" covers 22.01 and 23.01 only
    book = make_book(John=[P1], Ann=[P2])
    book.find("John").add_birthday("23.01.1990")
    book.find("Ann").add_birthday("25.01.1990")
    assert birthdays(["2"], book) == "John: 23.01.2024"
    assert birthdays(["30"], book) == "John: 23.01.2024\nAnn: 25.01.2024"
    assert birthdays(["1"], book) == "No birthdays in the next 1 days."


@pytest.mark.parametrize("bad", ["0", "-3", "week", "1.5"])
def test_birthdays_bad_number_of_days(bad):
    assert birthdays([bad], AddressBook()) == "Number of days must be a positive integer"


def test_birthdays_too_many_args():
    assert birthdays(["7", "8"], AddressBook()) == ENTER_ARG


# --- type robustness: bad types give a message, never an exception ----------

HANDLERS = [
    (add_contact, ["John", P1]),
    (change_contact, ["John", P1]),
    (show_phone, ["John"]),
    (add_birthday, ["John", "01.02.1990"]),
    (show_birthday, ["John"]),
    (birthdays, []),
]


@pytest.mark.parametrize("handler, _", HANDLERS)
@pytest.mark.parametrize("bad_args", [None, 42, "John 123", {"John": P1}, [1, 2], ["John", None]])
def test_handlers_bad_args_type(handler, _, bad_args):
    book = make_book(John=[P3])
    assert handler(bad_args, book) == BAD_TYPE
    assert snapshot(book) == {"John": [P3]}
    assert birthday_of(book, "John") is None


@pytest.mark.parametrize("bad_date", [19900201, date(1990, 2, 1), None])
def test_add_birthday_non_str_date(bad_date):
    book = make_book(John=[P3])
    assert add_birthday(["John", bad_date], book) == BAD_TYPE
    assert birthday_of(book, "John") is None


@pytest.mark.parametrize("handler, good_args", HANDLERS)
@pytest.mark.parametrize("bad_book", [None, [], {"John": P1}, "John:123"])
def test_handlers_bad_book_type(handler, good_args, bad_book):
    assert handler(good_args, bad_book) == BAD_TYPE


@pytest.mark.parametrize("bad_book", [None, [], {"John": P1}, "John:123"])
def test_show_all_bad_book_type(bad_book):
    assert show_all([], bad_book) == BAD_TYPE


# --- main --------------------------------------------------------------------

@pytest.fixture(autouse=True)
def in_tmp_dir(tmp_path, monkeypatch):
    """Every test gets its own empty DATA_DIR, so main() never touches real data."""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    return tmp_path


def run_session(monkeypatch, capsys, lines):
    monkeypatch.setattr(cli, "_read", lambda _prompt="": next(feed))
    feed = iter(lines)
    cli.main()
    return capsys.readouterr().out.splitlines()


def test_main_assignment_example_dialog(monkeypatch, capsys):
    out = run_session(monkeypatch, capsys, [
        "add",
        "add Bob",
        "add Jime 0501234356",
        "phone",
        "all",
        "exit",
    ])
    assert out == [
        WELCOME,
        ENTER_ARG,
        ENTER_ARG,
        "Contact added.",
        ENTER_ARG,
        "Jime: 0501234356",
        "Good bye!",
    ]


def test_main_full_session(monkeypatch, capsys):
    out = run_session(monkeypatch, capsys, [
        "hello",
        f"add John {P1}",
        f"add john {P3}",
        f"change JOHN {P1} {P2}",
        "phone JOHN",
        "phone Ann",
        f"change Ann {P3}",
        "add Ann 555",
        f"add Ann {P3}",
        "all",
        "exit",
    ])
    assert out == [
        WELCOME,
        "How can I help you?",
        "Contact added.",
        "Contact updated.",
        "Contact updated.",
        f"{P2}; {P3}",
        NOT_FOUND,
        NOT_FOUND,
        BAD_PHONE,
        "Contact added.",
        f"John: {P2}; {P3}",
        f"Ann: {P3}",
        "Good bye!",
    ]


def test_main_birthday_session(monkeypatch, capsys, frozen_today):
    out = run_session(monkeypatch, capsys, [
        f"add John {P1}",
        "add-birthday John 1990-01-23",
        "add-birthday Ann 23.01.1990",
        "add-birthday",
        "show-birthday john",
        "add-birthday john 23.01.1990",
        "show-birthday John",
        f"add Ann {P3}",
        "Add-Birthday Ann 28.01.1992",
        "birthdays",
        "all",
        "close",
    ])
    assert out == [
        WELCOME,
        "Contact added.",
        BAD_DATE,
        NOT_FOUND,
        ENTER_ARG,
        "John has no birthday set.",
        "Birthday added.",
        "23.01.1990",
        "Contact added.",
        "Birthday added.",
        "John: 23.01.2024",
        "Ann: 29.01.2024",
        f"John: {P1}, birthday: 23.01.1990",
        f"Ann: {P3}, birthday: 28.01.1992",
        "Good bye!",
    ]


@pytest.mark.parametrize("word", ["close", "CLOSE", "Exit"])
def test_main_exit_words_any_case(monkeypatch, capsys, word):
    out = run_session(monkeypatch, capsys, [word, "hello"])
    assert out == [WELCOME, "Good bye!"]


def test_main_invalid_and_blank_commands(monkeypatch, capsys):
    out = run_session(monkeypatch, capsys, ["test", "", "   ", "qwzx", "exit"])
    assert out[1:] == [
        "Unknown command 'test'. Did you mean 'notes'?",
        "Unknown command 'qwzx'. Type 'help' to see all commands.",
        "Good bye!",
    ]


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_main_eof_or_ctrl_c_exits(monkeypatch, capsys, exc):
    def raise_exc(_prompt=""):
        raise exc

    monkeypatch.setattr(cli, "_read", raise_exc)
    cli.main()
    assert capsys.readouterr().out.splitlines()[-1] == "Good bye!"


# --- main: persistence ---------------------------------------------------------

def test_main_restores_book_from_previous_session(monkeypatch, capsys):
    run_session(monkeypatch, capsys, [
        f"add John {P1}",
        "add-birthday John 23.01.1990",
        f"add Ann {P3}",
        "exit",
    ])
    out = run_session(monkeypatch, capsys, ["all", "show-birthday john", "exit"])
    assert out == [
        WELCOME,
        f"John: {P1}, birthday: 23.01.1990",
        f"Ann: {P3}",
        "23.01.1990",
        "Good bye!",
    ]


def test_main_changes_in_second_session_are_kept(monkeypatch, capsys, in_tmp_dir):
    run_session(monkeypatch, capsys, [f"add John {P1}", "exit"])
    run_session(monkeypatch, capsys, [f"change John {P2}", "close"])
    assert snapshot(load_data(in_tmp_dir / storage.CONTACTS_FILE)) == {"John": [P2]}


@pytest.mark.parametrize("ending", ["close", EOFError, KeyboardInterrupt])
def test_main_saves_on_every_exit(monkeypatch, capsys, in_tmp_dir, ending):
    lines = iter([f"add John {P1}", ending])

    def fake_input(_prompt=""):
        item = next(lines)
        if isinstance(item, type):
            raise item
        return item

    monkeypatch.setattr(cli, "_read", fake_input)
    cli.main()
    assert capsys.readouterr().out.splitlines()[-1] == "Good bye!"
    assert (in_tmp_dir / storage.CONTACTS_FILE).is_file()
    assert snapshot(load_data(in_tmp_dir / storage.CONTACTS_FILE)) == {"John": [P1]}


def test_main_loads_existing_file(monkeypatch, capsys, in_tmp_dir):
    save_data(make_book(Ann=[P2, P3]), in_tmp_dir / storage.CONTACTS_FILE)
    out = run_session(monkeypatch, capsys, ["phone ann", "exit"])
    assert out == [WELCOME, f"{P2}; {P3}", "Good bye!"]


@pytest.mark.parametrize("content", [b"junk\n", b"", pickle.dumps([1, 2])])
def test_main_bad_file_is_reported_and_left_untouched(monkeypatch, capsys, in_tmp_dir, content):
    path = in_tmp_dir / storage.CONTACTS_FILE
    path.write_bytes(content)

    def no_input(_prompt=""):
        raise AssertionError("bot must not read commands when the file can't be loaded")

    monkeypatch.setattr(cli, "_read", no_input)
    cli.main()
    out = capsys.readouterr().out
    assert out.startswith("Cannot load saved data:")
    assert path.read_bytes() == content


# --- new contact commands ----------------------------------------------------------

def test_delete_contact():
    book = make_book(John=[P1], Ann=[P2])
    assert delete_contact(["john"], book) == "Contact deleted."
    assert delete_contact(["john"], book) == NOT_FOUND
    assert snapshot(book) == {"Ann": [P2]}


def test_remove_phone():
    book = make_book(John=[P1, P2])
    assert remove_phone(["John", P1], book) == "Phone removed."
    assert remove_phone(["John", P1], book) == f"Phone {P1} not found"
    assert snapshot(book) == {"John": [P2]}


def test_email_and_address_are_shown():
    book = make_book(John=[P1])
    assert add_address(["john", "Kyiv,", "Khreshchatyk", "1"], book) == "Address saved."
    assert add_email(["John", "john@example.com"], book) == "Email saved."
    assert add_email(["John", "not-an-email"], book).startswith("Invalid email")
    assert show_all([], book) == (
        f"John: {P1}, email: john@example.com, address: Kyiv, Khreshchatyk 1")


def test_search_command():
    book = make_book(John=[P1], Ann=[P2])
    assert search_contacts(["ann"], book) == f"Ann: {P2}"
    assert search_contacts([P1[:4]], book) == f"John: {P1}"
    assert search_contacts(["zzz"], book) == "No contacts found."
    assert search_contacts([], book) == ENTER_ARG


# --- colors, help, did-you-mean ----------------------------------------------------

def test_colors(monkeypatch):
    monkeypatch.undo()  # real colorama codes
    from colorama import Fore, Style
    book = make_book(John=[P1])
    assert add_contact(["Ann", P2], book) == f"{Fore.GREEN}Contact added.{Style.RESET_ALL}"
    assert show_phone(["Bob"], book) == f"{Fore.RED}{NOT_FOUND}{Style.RESET_ALL}"


def test_help_lists_every_command(monkeypatch, capsys):
    out = "\n".join(run_session(monkeypatch, capsys, ["help", "exit"]))
    for _, _, usage, _ in commands.COMMANDS.values():
        assert usage in out


@pytest.mark.parametrize("typo, guess", [
    ("ad", "add"), ("bithdays", "birthdays"), ("note", "notes"), ("add-bi", "add-birthday"),
])
def test_did_you_mean(typo, guess):
    assert cli.unknown_command(typo) == f"Unknown command '{typo}'. Did you mean '{guess}'?"

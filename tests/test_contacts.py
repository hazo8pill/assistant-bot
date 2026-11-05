"""Unit tests for contacts (Field / Name / Phone / Birthday / Record / AddressBook) and storage.

Contract under test:
- Field keeps .value; str(field) == str(value)
- Name is required: blank -> ValueError
- Phone is exactly 10 ASCII digits, otherwise ValueError
- wrong argument types anywhere (non-str name/phone, non-Record) -> TypeError,
  nothing changed
- Record: .name is Name, .phones is list[Phone];
  add_phone / find_phone (Phone or None) / remove_phone / edit_phone;
  missing phone or invalid new phone -> ValueError, record left unchanged
- AddressBook (UserDict): add_record keys by name, find -> Record or None,
  delete removes, missing name -> KeyError; names match exactly (case-sensitive)
- Birthday: str "DD.MM.YYYY" (zero-padded, real, not in the future) -> .value is a date;
  anything else -> ValueError("Invalid date format. Use DD.MM.YYYY"); non-str -> TypeError
- Record.birthday is None until add_birthday; a second add_birthday replaces it
- AddressBook.get_upcoming_birthdays(today): who to congratulate in the next 7 days
  (today included), weekends moved to Monday, 29 Feb -> 1 Mar in non-leap years,
  sorted by date, as [{"name", "congratulation_date": "DD.MM.YYYY"}]
- the assignment's example script prints the expected output
- storage.save_data(book, filename) / load_data(filename): pickle round trip;
  missing file -> empty AddressBook; wrong argument types -> TypeError, nothing written;
  a file holding something else -> TypeError, a corrupted file -> ValueError (file untouched)

Run: python -m pytest -v
"""

from collections import UserDict
import pickle
from datetime import date, datetime, timedelta

import pytest

from personal_assistant.contacts import (
    AddressBook,
    Birthday,
    Field,
    Name,
    Phone,
    Record,
)
from personal_assistant.storage import load_data, save_data

BAD_DATE = "Invalid date format. Use DD.MM.YYYY"


# --- Field / Name ------------------------------------------------------------

def test_field_stores_value_and_str():
    field = Field(42)
    assert field.value == 42
    assert str(field) == "42"


def test_name_is_field():
    name = Name("John")
    assert isinstance(name, Field)
    assert name.value == "John"
    assert str(name) == "John"


@pytest.mark.parametrize("bad", ["", "   "])
def test_name_required(bad):
    with pytest.raises(ValueError):
        Name(bad)


@pytest.mark.parametrize("bad", [None, 123, ["John"]])
def test_name_must_be_str(bad):
    with pytest.raises(TypeError):
        Name(bad)


# --- Phone -------------------------------------------------------------------

def test_phone_valid():
    phone = Phone("0501234567")
    assert isinstance(phone, Field)
    assert phone.value == "0501234567"
    assert str(phone) == "0501234567"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "123456789",          # 9 digits
        "12345678901",        # 11 digits
        "12345abcde",         # letters
        "+380501234",         # plus sign
        "050 123 456",        # spaces
        "050-123-45-67",      # dashes
        " 0501234567",        # surrounding whitespace
        "0501234567\n",       # trailing newline
        "١٢٣٤٥٦٧٨٩٠",         # Arabic-Indic digits: isdigit() is True, still invalid
    ],
)
def test_phone_invalid(bad):
    with pytest.raises(ValueError):
        Phone(bad)


@pytest.mark.parametrize("bad", [1234567890, None, b"1234567890"])
def test_phone_must_be_str(bad):
    with pytest.raises(TypeError):
        Phone(bad)


# --- Record ------------------------------------------------------------------

def make_record(*phones):
    record = Record("John")
    for phone in phones:
        record.add_phone(phone)
    return record


def values(record):
    return [p.value for p in record.phones]


def test_record_init():
    record = Record("John")
    assert isinstance(record.name, Name)
    assert record.name.value == "John"
    assert record.phones == []


def test_record_requires_name():
    with pytest.raises(ValueError):
        Record("")


def test_add_phone_stores_phone_objects_in_order():
    record = make_record("1234567890", "5555555555")
    assert all(isinstance(p, Phone) for p in record.phones)
    assert values(record) == ["1234567890", "5555555555"]


def test_add_invalid_phone_leaves_record_unchanged():
    record = make_record("1234567890")
    with pytest.raises(ValueError):
        record.add_phone("123")
    assert values(record) == ["1234567890"]


def test_find_phone_returns_phone_object():
    record = make_record("1234567890", "5555555555")
    found = record.find_phone("5555555555")
    assert isinstance(found, Phone)
    assert found is record.phones[1]


def test_find_phone_missing_returns_none():
    assert make_record("1234567890").find_phone("5555555555") is None


def test_remove_phone():
    record = make_record("1234567890", "5555555555")
    record.remove_phone("1234567890")
    assert values(record) == ["5555555555"]


def test_remove_missing_phone():
    record = make_record("1234567890")
    with pytest.raises(ValueError):
        record.remove_phone("5555555555")
    assert values(record) == ["1234567890"]


def test_edit_phone_keeps_position():
    record = make_record("1234567890", "5555555555")
    record.edit_phone("1234567890", "1112223333")
    assert values(record) == ["1112223333", "5555555555"]
    assert all(isinstance(p, Phone) for p in record.phones)


def test_edit_missing_phone():
    record = make_record("1234567890")
    with pytest.raises(ValueError):
        record.edit_phone("5555555555", "1112223333")
    assert values(record) == ["1234567890"]


def test_edit_to_invalid_phone_leaves_record_unchanged():
    record = make_record("1234567890")
    with pytest.raises(ValueError):
        record.edit_phone("1234567890", "bad")
    assert values(record) == ["1234567890"]


def test_record_str():
    assert str(make_record("1112223333", "5555555555")) == (
        "Contact name: John, phones: 1112223333; 5555555555"
    )


def test_record_str_without_phones():
    assert str(Record("John")) == "Contact name: John, phones: "


# --- AddressBook -------------------------------------------------------------

def test_book_is_userdict():
    book = AddressBook()
    assert isinstance(book, UserDict)
    assert book.data == {}


def test_add_record_keys_by_name():
    book = AddressBook()
    record = Record("John")
    book.add_record(record)
    assert book.data == {"John": record}


def test_add_record_same_name_overwrites():
    book = AddressBook()
    book.add_record(Record("John"))
    newer = make_record("1234567890")
    book.add_record(newer)
    assert len(book) == 1
    assert book.find("John") is newer


def test_find():
    book = AddressBook()
    record = Record("John")
    book.add_record(record)
    assert book.find("John") is record


def test_find_missing_returns_none():
    assert AddressBook().find("John") is None


def test_find_is_case_sensitive():
    book = AddressBook()
    book.add_record(Record("John"))
    assert book.find("john") is None


def test_delete():
    book = AddressBook()
    book.add_record(Record("John"))
    book.add_record(Record("Jane"))
    book.delete("Jane")
    assert list(book.data) == ["John"]


def test_delete_missing_raises_key_error():
    book = AddressBook()
    book.add_record(Record("John"))
    with pytest.raises(KeyError):
        book.delete("Jane")
    assert list(book.data) == ["John"]


# --- wrong argument types -> TypeError, nothing changed ----------------------

@pytest.mark.parametrize("call", [
    lambda r: r.add_phone(1234567890),
    lambda r: r.find_phone(1234567890),
    lambda r: r.remove_phone(None),
    lambda r: r.edit_phone(1234567890, "1112223333"),
    lambda r: r.edit_phone("1234567890", 1112223333),
])
def test_record_methods_reject_non_str(call):
    record = make_record("1234567890")
    with pytest.raises(TypeError):
        call(record)
    assert values(record) == ["1234567890"]


@pytest.mark.parametrize("bad", ["John", None, {"John": "1234567890"}])
def test_add_record_rejects_non_record(bad):
    book = AddressBook()
    with pytest.raises(TypeError):
        book.add_record(bad)
    assert book.data == {}


@pytest.mark.parametrize("method", ["find", "delete"])
@pytest.mark.parametrize("bad", [None, 123, ["John"]])
def test_book_lookup_rejects_non_str(method, bad):
    book = AddressBook()
    book.add_record(Record("John"))
    with pytest.raises(TypeError):
        getattr(book, method)(bad)
    assert list(book.data) == ["John"]


# --- Birthday ----------------------------------------------------------------

def test_birthday_valid():
    birthday = Birthday("01.02.1990")
    assert isinstance(birthday, Field)
    assert birthday.value == date(1990, 2, 1)
    assert str(birthday) == "01.02.1990"


def test_birthday_today_is_valid():
    today = date.today()
    assert Birthday(today.strftime("%d.%m.%Y")).value == today


def test_birthday_leap_day():
    assert Birthday("29.02.2000").value == date(2000, 2, 29)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "1990-02-01",          # ISO
        "01/02/1990",          # slashes
        "1.2.1990",            # not zero-padded
        "01.02.90",            # 2-digit year
        "31.02.1990",          # no such day
        "32.01.1990",
        "01.13.1990",
        "29.02.2001",          # not a leap year
        " 01.02.1990",         # surrounding whitespace
        "01.02.1990\n",
        "01.02.1990 extra",
        "birthday",
        (date.today() + timedelta(days=1)).strftime("%d.%m.%Y"),  # future
    ],
)
def test_birthday_invalid(bad):
    with pytest.raises(ValueError, match=BAD_DATE):
        Birthday(bad)


@pytest.mark.parametrize("bad", [None, 1021990, date(1990, 2, 1), datetime(1990, 2, 1)])
def test_birthday_must_be_str(bad):
    with pytest.raises(TypeError):
        Birthday(bad)


def test_record_has_no_birthday_by_default():
    assert Record("John").birthday is None


def test_add_birthday():
    record = Record("John")
    record.add_birthday("01.02.1990")
    assert isinstance(record.birthday, Birthday)
    assert record.birthday.value == date(1990, 2, 1)


def test_add_birthday_again_replaces_it():
    record = Record("John")
    record.add_birthday("01.02.1990")
    record.add_birthday("03.04.1985")
    assert str(record.birthday) == "03.04.1985"


@pytest.mark.parametrize("bad", ["1990-02-01", 19900201, None])
def test_add_invalid_birthday_leaves_record_unchanged(bad):
    record = Record("John")
    record.add_birthday("01.02.1990")
    with pytest.raises((ValueError, TypeError)):
        record.add_birthday(bad)
    assert str(record.birthday) == "01.02.1990"


def test_record_str_with_birthday():
    record = make_record("1112223333")
    record.add_birthday("01.02.1990")
    assert str(record) == "Contact name: John, phones: 1112223333, birthday: 01.02.1990"


# --- AddressBook.get_upcoming_birthdays ----------------------------------------

MONDAY = date(2024, 1, 22)  # window: Mon 22.01 .. Sun 28.01


def birthday_book(**birthdays):
    """birthday_book(John="23.01.1990", Ann=None) -> AddressBook."""
    book = AddressBook()
    for name, birthday in birthdays.items():
        record = Record(name)
        if birthday:
            record.add_birthday(birthday)
        book.add_record(record)
    return book


def upcoming(book, today):
    return [(u["name"], u["congratulation_date"]) for u in book.get_upcoming_birthdays(today)]


def test_upcoming_empty_book():
    assert AddressBook().get_upcoming_birthdays(MONDAY) == []


def test_upcoming_returns_dicts():
    book = birthday_book(John="23.01.1985")
    assert book.get_upcoming_birthdays(MONDAY) == [
        {"name": "John", "congratulation_date": "23.01.2024"},
    ]


def test_upcoming_window_is_today_plus_six_days():
    book = birthday_book(
        Past="21.01.1990",     # yesterday
        Today="22.01.1990",
        Friday="26.01.1990",
        Next="29.01.1990",     # 7 days ahead: out
    )
    assert upcoming(book, MONDAY) == [("Today", "22.01.2024"), ("Friday", "26.01.2024")]


def test_upcoming_weekend_moves_to_monday():
    book = birthday_book(Sat="27.01.1990", Sun="28.01.1990")
    assert upcoming(book, MONDAY) == [("Sat", "29.01.2024"), ("Sun", "29.01.2024")]


def test_upcoming_sorted_by_date():
    book = birthday_book(Late="27.01.1990", Early="23.01.1990", Mid="25.01.1990")
    assert [name for name, _ in upcoming(book, MONDAY)] == ["Early", "Mid", "Late"]


def test_upcoming_skips_contacts_without_birthday():
    book = birthday_book(NoBirthday=None, John="23.01.1990")
    assert upcoming(book, MONDAY) == [("John", "23.01.2024")]


def test_upcoming_year_rollover():
    book = birthday_book(NewYear="02.01.1990", Gone="29.12.1990")
    assert upcoming(book, date(2024, 12, 30)) == [("NewYear", "02.01.2025")]


def test_upcoming_leap_day_in_non_leap_year():
    book = birthday_book(Leap="29.02.2000")
    assert upcoming(book, date(2023, 2, 27)) == [("Leap", "01.03.2023")]


def test_upcoming_defaults_to_today():
    born = date.today().replace(year=2000)  # 2000 is leap, so 29.02 works too
    book = birthday_book(John=born.strftime("%d.%m.%Y"))
    assert [u["name"] for u in book.get_upcoming_birthdays()] == ["John"]


@pytest.mark.parametrize("bad", ["22.01.2024", 20240122, datetime(2024, 1, 22)])
def test_upcoming_rejects_non_date(bad):
    with pytest.raises(TypeError):
        birthday_book(John="23.01.1990").get_upcoming_birthdays(bad)


# --- assignment example ------------------------------------------------------

def test_assignment_example(capsys):
    book = AddressBook()

    john_record = Record("John")
    john_record.add_phone("1234567890")
    john_record.add_phone("5555555555")
    book.add_record(john_record)

    jane_record = Record("Jane")
    jane_record.add_phone("9876543210")
    book.add_record(jane_record)

    for name, record in book.data.items():
        print(record)

    john = book.find("John")
    john.edit_phone("1234567890", "1112223333")
    print(john)

    found_phone = john.find_phone("5555555555")
    print(f"{john.name}: {found_phone}")

    book.delete("Jane")

    assert capsys.readouterr().out.splitlines() == [
        "Contact name: John, phones: 1234567890; 5555555555",
        "Contact name: Jane, phones: 9876543210",
        "Contact name: John, phones: 1112223333; 5555555555",
        "John: 5555555555",
    ]
    assert list(book.data) == ["John"]


# --- persistence (save_data / load_data) ---------------------------------------

def sample_book():
    book = AddressBook()
    john = Record("John")
    john.add_phone("1234567890")
    john.add_phone("5555555555")
    john.add_birthday("23.01.1990")
    book.add_record(john)
    ann = Record("Ann")
    ann.add_phone("0987654321")
    book.add_record(ann)
    return book


def as_plain(book):
    """{name: ([phones], "DD.MM.YYYY" or None)} for equality checks."""
    return {
        name: ([p.value for p in r.phones], r.birthday and str(r.birthday))
        for name, r in book.data.items()
    }


def test_save_and_load_round_trip(tmp_path):
    path = str(tmp_path / "book.pkl")
    book = sample_book()
    save_data(book, path)
    loaded = load_data(path)
    assert isinstance(loaded, AddressBook)
    assert loaded is not book
    assert as_plain(loaded) == {
        "John": (["1234567890", "5555555555"], "23.01.1990"),
        "Ann": (["0987654321"], None),
    }


def test_loaded_book_is_fully_usable(tmp_path):
    path = str(tmp_path / "book.pkl")
    save_data(sample_book(), path)
    loaded = load_data(path)
    john = loaded.find("John")
    assert isinstance(john, Record)
    assert isinstance(john.birthday.value, date)
    john.edit_phone("1234567890", "1112223333")
    assert [p.value for p in john.phones] == ["1112223333", "5555555555"]
    assert loaded.get_upcoming_birthdays(date(2024, 1, 22)) == [
        {"name": "John", "congratulation_date": "23.01.2024"}
    ]
    loaded.delete("Ann")
    assert list(loaded.data) == ["John"]


def test_empty_book_round_trip(tmp_path):
    path = str(tmp_path / "book.pkl")
    save_data(AddressBook(), path)
    loaded = load_data(path)
    assert isinstance(loaded, AddressBook)
    assert len(loaded) == 0


def test_load_missing_file_gives_empty_book(tmp_path):
    path = tmp_path / "missing.pkl"
    loaded = load_data(str(path))
    assert isinstance(loaded, AddressBook)
    assert len(loaded) == 0
    assert not path.exists()


def test_second_save_overwrites_and_leaves_no_temp_file(tmp_path):
    path = str(tmp_path / "book.pkl")
    save_data(sample_book(), path)
    book = load_data(path)
    book.delete("John")
    save_data(book, path)
    assert list(load_data(path).data) == ["Ann"]
    assert [f.name for f in tmp_path.iterdir()] == ["book.pkl"]


def test_path_object_filename_is_accepted(tmp_path):
    path = tmp_path / "book.pkl"
    save_data(sample_book(), path)
    assert as_plain(load_data(path)) == as_plain(sample_book())


@pytest.mark.parametrize("bad_book", [None, {}, [], {"John": "1234567890"}, Record("John")])
def test_save_rejects_non_address_book(tmp_path, bad_book):
    path = tmp_path / "book.pkl"
    with pytest.raises(TypeError):
        save_data(bad_book, str(path))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad_name", [None, 123, 1.5, ["book.pkl"]])
def test_save_rejects_bad_filename_type(tmp_path, monkeypatch, bad_name):
    # an int would otherwise be taken by open() as a file descriptor
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TypeError):
        save_data(sample_book(), bad_name)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad_name", [None, 123, 1.5, ["book.pkl"]])
def test_load_rejects_bad_filename_type(bad_name):
    with pytest.raises(TypeError):
        load_data(bad_name)


@pytest.mark.parametrize("payload", [[1, 2], {"John": "1234567890"}, "John", Record("John")])
def test_load_file_with_wrong_content_type(tmp_path, payload):
    path = tmp_path / "book.pkl"
    path.write_bytes(pickle.dumps(payload))
    before = path.read_bytes()
    with pytest.raises(TypeError):
        load_data(str(path))
    assert path.read_bytes() == before


@pytest.mark.parametrize("content", [b"", b"junk\n", b"\x80\x04garbage", b"\x00" * 16])
def test_load_corrupted_file(tmp_path, content):
    path = tmp_path / "book.pkl"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        load_data(str(path))
    assert path.read_bytes() == content


# --- email / address / search / custom birthday window ---------------------------

def test_address_is_stripped_and_required():
    record = Record("John")
    record.set_address("  Kyiv, Khreshchatyk 1 ")
    assert record.address.value == "Kyiv, Khreshchatyk 1"
    with pytest.raises(ValueError):
        record.set_address("   ")
    assert record.address.value == "Kyiv, Khreshchatyk 1"


@pytest.mark.parametrize("good", ["john@example.com", "j.doe+work@mail.example.ua"])
def test_email_valid(good):
    record = Record("John")
    record.set_email(good)
    assert record.email.value == good


@pytest.mark.parametrize("bad", [
    "john", "john@", "@example.com", "john@example", "jo hn@example.com",
])
def test_email_invalid(bad):
    record = Record("John")
    with pytest.raises(ValueError):
        record.set_email(bad)
    assert record.email is None


def test_search_matches_any_field_case_insensitive():
    book = sample_book()
    book.find("Ann").set_address("Lviv, Rynok 5")
    book.find("Ann").set_email("ann@example.com")
    assert [r.name.value for r in book.search("lviv")] == ["Ann"]
    assert [r.name.value for r in book.search("EXAMPLE")] == ["Ann"]
    assert [r.name.value for r in book.search("555")] == ["John"]
    assert [r.name.value for r in book.search("23.01")] == ["John"]
    assert book.search("nobody") == []


def test_upcoming_custom_days():
    book = birthday_book(John="23.01.1990", Ann="10.02.1990")
    today = date(2024, 1, 22)
    assert [u["name"] for u in book.get_upcoming_birthdays(today, days=1)] == []
    assert [u["name"] for u in book.get_upcoming_birthdays(today, days=2)] == ["John"]
    assert [u["name"] for u in book.get_upcoming_birthdays(today, days=30)] == ["John", "Ann"]


@pytest.mark.parametrize("bad, exc", [
    (0, ValueError), (-1, ValueError), ("7", TypeError), (True, TypeError),
])
def test_upcoming_bad_days(bad, exc):
    with pytest.raises(exc):
        AddressBook().get_upcoming_birthdays(date(2024, 1, 22), days=bad)

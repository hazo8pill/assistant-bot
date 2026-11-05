"""Contacts model: Field -> Name / Phone / Email / Address / Birthday, Record, AddressBook.

Errors follow the commands' input_error decorator:
ValueError -> invalid value or missing phone, KeyError -> unknown contact,
TypeError  -> argument of the wrong type (nothing is changed).
"""

import re
from collections import UserDict
from datetime import date, datetime, timedelta

DATE_FORMAT = "%d.%m.%Y"
DEFAULT_DAYS = 7


def _require_str(value, what: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a str")


class Field:
    """Base class for record fields; holds a single value."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Name(Field):
    """Contact name. Required: must be a non-blank str."""

    def __init__(self, value):
        _require_str(value, "Name")
        if not value.strip():
            raise ValueError("Name is required")
        super().__init__(value)


class Phone(Field):
    """Phone number: exactly 10 ASCII digits, e.g. "0501234567"."""

    def __init__(self, value):
        _require_str(value, "Phone")
        if not re.fullmatch(r"[0-9]{10}", value):
            raise ValueError("Phone must be exactly 10 digits")
        super().__init__(value)


class Email(Field):
    """E-mail address, e.g. "john@example.com". Invalid -> ValueError("Invalid email ...")."""

    def __init__(self, value):
        _require_str(value, "Email")
        # local part @ domain labels . top-level domain of 2+ letters; no spaces anywhere
        if not re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)*\.[A-Za-z]{2,}", value):
            raise ValueError("Invalid email. Example: john@example.com")
        super().__init__(value)


class Address(Field):
    """Postal address: any non-blank text, stored without surrounding spaces."""

    def __init__(self, value):
        _require_str(value, "Address")
        if not value.strip():
            raise ValueError("Address must not be empty")
        super().__init__(value.strip())


class Birthday(Field):
    """
    Date of birth from a "DD.MM.YYYY" str, e.g. "01.02.1990"; .value is a date.

    Day and month must be zero-padded, the date must exist and not be in the future,
    otherwise ValueError("Invalid date format. Use DD.MM.YYYY").
    """

    def __init__(self, value):
        _require_str(value, "Birthday")
        try:
            if not re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", value):
                raise ValueError
            born = datetime.strptime(value, DATE_FORMAT).date()
            if born > date.today():
                raise ValueError
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY") from None
        super().__init__(born)

    def __str__(self):
        return self.value.strftime(DATE_FORMAT)


class Record:
    """
    A contact: one Name, a list of Phone objects and optional
    Email, Address and Birthday (None until set).
    """

    def __init__(self, name):
        self.name = Name(name)
        self.phones = []
        self.email = None
        self.address = None
        self.birthday = None

    def add_birthday(self, birthday: str) -> None:
        """Set the birthday ("DD.MM.YYYY"), replacing any old one. Invalid -> ValueError."""
        self.birthday = Birthday(birthday)

    def set_email(self, email: str) -> None:
        """Set the e-mail, replacing any old one. Invalid -> ValueError."""
        self.email = Email(email)

    def set_address(self, address: str) -> None:
        """Set the address, replacing any old one. Blank -> ValueError."""
        self.address = Address(address)

    def add_phone(self, phone: str) -> None:
        """Append a phone. Raises ValueError if it is invalid."""
        self.phones.append(Phone(phone))

    def find_phone(self, phone: str) -> Phone | None:
        """Return the Phone object with this number, or None."""
        _require_str(phone, "Phone")
        return next((p for p in self.phones if p.value == phone), None)

    def remove_phone(self, phone: str) -> None:
        """Remove a phone. Raises ValueError if the record doesn't have it."""
        self.phones.remove(self._get_phone(phone))

    def edit_phone(self, old_phone: str, new_phone: str) -> None:
        """
        Replace old_phone with new_phone, keeping its position.

        Raises ValueError if old_phone is missing or new_phone is invalid;
        the record is left unchanged in both cases.
        """
        index = self.phones.index(self._get_phone(old_phone))
        self.phones[index] = Phone(new_phone)

    def _get_phone(self, phone: str) -> Phone:
        found = self.find_phone(phone)
        if found is None:
            raise ValueError(f"Phone {phone} not found")
        return found

    def matches(self, query: str) -> bool:
        """True if query (case-insensitive) is in the name, a phone, email, address or birthday."""
        _require_str(query, "Query")
        query = query.casefold()
        fields = [self.name, *self.phones, self.email, self.address, self.birthday]
        return any(query in str(f).casefold() for f in fields if f is not None)

    def __str__(self):
        text = f"Contact name: {self.name.value}, phones: {'; '.join(p.value for p in self.phones)}"
        if self.birthday:
            text += f", birthday: {self.birthday}"
        return text


class AddressBook(UserDict):
    """Records keyed by contact name (exact, case-sensitive match)."""

    def add_record(self, record: Record) -> None:
        """Add a record; a record with the same name is replaced."""
        if not isinstance(record, Record):
            raise TypeError("record must be a Record")
        self.data[record.name.value] = record

    def find(self, name: str) -> Record | None:
        """Return the record for name, or None."""
        _require_str(name, "Name")
        return self.data.get(name)

    def delete(self, name: str) -> None:
        """Delete the record for name. Raises KeyError if there is none."""
        _require_str(name, "Name")
        del self.data[name]

    def search(self, query: str) -> list[Record]:
        """Records whose name, phone, email, address or birthday contains query."""
        _require_str(query, "Query")
        return [r for r in self.data.values() if r.matches(query)]

    def get_upcoming_birthdays(self, today: date | None = None,
                               days: int = DEFAULT_DAYS) -> list[dict]:
        """
        Who to congratulate in the next `days` days, today included (default: 7, from date.today()).

        A birthday on Saturday or Sunday is congratulated on the following Monday;
        29 Feb is celebrated on 1 Mar in non-leap years. Contacts without a birthday
        are skipped. Raises TypeError if today is not a date or days is not an int,
        ValueError if days < 1 (days=1 means today only).

        Returns dicts sorted by date, e.g. with today = 22.01.2024 (Monday):
            [{"name": "John", "congratulation_date": "23.01.2024"},
             {"name": "Jane", "congratulation_date": "29.01.2024"}]   # born 27.01 (Sat)
        """
        if today is None:
            today = date.today()

        if not isinstance(today, date) or isinstance(today, datetime):
            raise TypeError("today must be a date")
        if not isinstance(days, int) or isinstance(days, bool):
            raise TypeError("days must be an int")
        if days < 1:
            raise ValueError("Number of days must be a positive integer")

        upcoming = []
        for record in self.data.values():
            if record.birthday is None:
                continue
            birthday = _in_year(record.birthday.value, today.year)
            if birthday < today:
                birthday = _in_year(record.birthday.value, today.year + 1)
            if (birthday - today).days >= days:
                continue
            if birthday.weekday() >= 5:
                birthday += timedelta(days=7 - birthday.weekday())
            upcoming.append((birthday, record.name.value))

        upcoming.sort(key=lambda item: item[0])
        return [
            {"name": name, "congratulation_date": day.strftime(DATE_FORMAT)}
            for day, name in upcoming
        ]


def _in_year(birthday: date, year: int) -> date:
    """birthday moved to year; 29 Feb becomes 1 Mar in non-leap years."""
    try:
        return birthday.replace(year=year)
    except ValueError:
        return date(year, 3, 1)

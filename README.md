# Personal Assistant

A command-line personal assistant: an **address book** (phones, email, address, birthdays)
and a **notebook** (text notes with tags). Everything is saved to your home folder, so
nothing is lost when you restart it.

```text
$ assistant
Welcome to the assistant bot! Type 'help' to see all commands.
Enter a command: add John 0501234567
Contact added.
Enter a command: add-email John john@example.com
Email saved.
Enter a command: add-address John Kyiv, Khreshchatyk 1
Address saved.
Enter a command: add-birthday John 07.11.1990
Birthday added.
Enter a command: birthdays 5
John: 07.11.2026
Enter a command: add-note Buy a gift for John #shopping #birthday
Note 1 added.
Enter a command: find-tag birthday
[1] Buy a gift for John #birthday #shopping
Enter a command: ad
Unknown command 'ad'. Did you mean 'add'?
Enter a command: exit
Good bye!
```

## Features

- **Contacts:** name, any number of phones, email, address and birthday.
- **Validation:** a phone must be exactly 10 digits (`0501234567`), an email must look like
  `john@example.com`, and a birthday must be a real past date in `DD.MM.YYYY` format.
  If a value is wrong, the assistant explains why and nothing is changed.
- **Search** contacts by any field: name, phone, email, address or birthday.
- **Edit and delete** contacts and individual phones.
- **Upcoming birthdays:** who to congratulate in the next N days. Birthdays that fall on a
  weekend are moved to Monday.
- **Notes** with **tags** (`#work`, `#shopping`): add, edit, delete, search by text or tag,
  filter by a tag, and list sorted by tags.
- **Persistence:** data is saved on every exit (including Ctrl-C and Ctrl-D) to `~/.personal_assistant/`.
- **Convenient CLI:** colored output (colorama), Tab completion of command names and
  ↑/↓ command history (prompt_toolkit), "Did you mean …?" hints for typos, and a `help` command.
- Bad input never crashes the assistant. It always answers with a message.

## Installation

Requires **Python 3.10+**. Check your version with `python3 --version`
(on Windows: `python --version`).

### 1. Get the code

```bash
git clone <this repository URL>
cd python-final-project
```

### 2. Create a virtual environment

A virtual environment (venv) keeps the project's libraries separate from the rest of your
system. Create it once, inside the project folder:

```bash
python3 -m venv .venv              # Windows: python -m venv .venv
```

This creates a `.venv` folder. It is already listed in `.gitignore`.

### 3. Activate the virtual environment

Activate it **every time you open a new terminal** to work with the project:

| System | Command |
| ------ | ------- |
| macOS / Linux | `source .venv/bin/activate` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |

When it is active, your prompt starts with `(.venv)`. All `pip` and `python` commands
below then use the venv, not your system Python.

### 4. Install the dependencies and the app

```bash
pip install -r requirements.txt    # libraries: colorama, prompt_toolkit, pytest
pip install .                      # the app itself + the `assistant` command
```

### 5. Run

```bash
assistant
# or, without the command:
python -m personal_assistant
```

While the venv is active, `assistant` works from any folder. In a new terminal, activate
the venv again first (step 3). Otherwise you get `command not found: assistant`.

To leave the venv, run `deactivate`.

### Development

Use an editable install: code changes then take effect without reinstalling.

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest                   # run the tests
```

## Commands

Command names are case-insensitive, and contact names match case-insensitively.
Press **Tab** to complete a command name.

### Contacts

| Command | What it does |
| ------- | ------------ |
| `add NAME PHONE` | new contact, or another phone for an existing one |
| `change NAME NEW` | the contact now has only phone `NEW` |
| `change NAME OLD NEW` | replace one phone |
| `remove-phone NAME PHONE` | delete one phone |
| `delete NAME` | delete the contact |
| `phone NAME` | the contact's phones |
| `all` | every contact with all details |
| `search QUERY` | contacts whose name, phone, email, address or birthday contains `QUERY` |
| `add-email NAME EMAIL` | set or replace the email |
| `add-address NAME ADDRESS` | set or replace the address (spaces allowed) |
| `add-birthday NAME DD.MM.YYYY` | set or replace the birthday |
| `show-birthday NAME` | the contact's birthday |
| `birthdays [DAYS]` | birthdays in the next `DAYS` days, today included (default 7) |

### Notes

| Command | What it does |
| ------- | ------------ |
| `add-note TEXT [#tag ...]` | new note; words starting with `#` become tags |
| `notes` | every note as `[id] text #tags` |
| `edit-note ID TEXT [#tag ...]` | replace the text (existing tags are kept, new `#tags` added) |
| `delete-note ID` | delete the note |
| `search-notes QUERY` | notes whose text or tags contain `QUERY` |
| `add-tag ID TAG [TAG ...]` | add tags (`#` optional) |
| `remove-tag ID TAG` | remove a tag |
| `find-tag TAG` | notes with exactly this tag |
| `sort-notes` | every note, ordered alphabetically by tags; untagged notes last |

### General

| Command | What it does |
| ------- | ------------ |
| `hello` | greeting |
| `help` | list all commands |
| `exit` / `close` / Ctrl-D / Ctrl-C | save and quit |

## Where the data lives

| File | Content |
| ---- | ------- |
| `~/.personal_assistant/contacts.pkl` | the address book |
| `~/.personal_assistant/notes.pkl` | the notes |
| `~/.personal_assistant/history` | command history for ↑/↓ |

Each file is written to a temporary file first and then renamed, so a crash during a save
can never corrupt existing data. If a data file is damaged, the assistant reports it and
quits **without overwriting it**.

## Project structure

```text
personal_assistant/
  contacts.py   Field → Name / Phone / Email / Address / Birthday, Record, AddressBook
  notes.py      Note, NoteBook
  storage.py    save_data / load_data (pickle) in ~/.personal_assistant
  commands.py   command handlers, input_error decorator, COMMANDS table
  cli.py        main loop: prompt, help, "Did you mean", load/save
tests/          pytest suite
```

Design notes:

- **Inheritance:** every contact field subclasses `Field` and validates itself in its
  constructor. `AddressBook` and `NoteBook` extend `collections.UserDict`.
- **Composition:** a `Record` *has* a `Name`, `Phone`s, an `Email`, an `Address` and a
  `Birthday`. A `Note` *has* tags.
- Handlers raise exceptions on bad input. The `input_error` decorator turns them into
  readable messages.
- One `COMMANDS` table drives dispatch, `help`, Tab completion and typo hints.

Code style: PEP 8 (checked with `pycodestyle --max-line-length=100`).

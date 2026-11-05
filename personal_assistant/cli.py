"""Interactive loop of the Personal Assistant (the `assistant` console command).

Contacts and notes are loaded from storage.DATA_DIR at startup and saved back
on every exit. Input comes from prompt_toolkit (Tab completes command names,
Up/Down walk through the history); an unknown command gets a "Did you mean ...?"
hint.
"""

import difflib

import colorama
from colorama import Fore

from . import storage
from .commands import COMMANDS, CONTACTS, NOTES, err, paint, parse_input
from .contacts import AddressBook
from .notes import NoteBook

EXIT_WORDS = ("close", "exit")
BUILTINS = {
    "hello": ("hello", "greeting"),
    "help": ("help", "show this list"),
    "exit": ("exit | close", "save and quit (also Ctrl-D / Ctrl-C)"),
}
ALL_COMMANDS = [*COMMANDS, *BUILTINS, "close"]
PROMPT = "Enter a command: "

_session = None


def _read(prompt: str) -> str:
    """Read one command line. Tests replace this function."""
    global _session
    if _session is None:
        # Imported lazily: prompt_toolkit needs a real terminal.
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory

        storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _session = PromptSession(
            completer=WordCompleter(ALL_COMMANDS, sentence=True),
            history=FileHistory(str(storage.DATA_DIR / "history")),
        )
    return _session.prompt(prompt)


def help_text() -> str:
    """Every command with its usage, grouped, generated from COMMANDS."""
    def line(usage: str, description: str) -> str:
        return f"  {paint(usage.ljust(30), Fore.CYAN)} {description}"

    lines = [paint("Contacts:", Fore.YELLOW)]
    lines += [line(u, d) for _, store, u, d in COMMANDS.values() if store == CONTACTS]
    lines.append(paint("Notes:", Fore.YELLOW))
    lines += [line(u, d) for _, store, u, d in COMMANDS.values() if store == NOTES]
    lines.append(paint("General:", Fore.YELLOW))
    lines += [line(u, d) for u, d in BUILTINS.values()]
    return "\n".join(lines)


def unknown_command(command: str) -> str:
    """'Unknown command' plus the closest real command, if any."""
    prefixed = [c for c in ALL_COMMANDS if c.startswith(command)]
    guess = prefixed[:1] or difflib.get_close_matches(command, ALL_COMMANDS, n=1)
    hint = f" Did you mean '{guess[0]}'?" if guess else " Type 'help' to see all commands."
    return err(f"Unknown command '{command}'.") + hint


def main() -> None:
    """
    Run the assistant until exit/close, Ctrl-D or Ctrl-C.

    Contacts and notes are loaded at startup and saved on every exit. If a saved
    file can't be read, the assistant reports it and quits without touching it.
    """
    colorama.just_fix_windows_console()
    contacts_path = storage.DATA_DIR / storage.CONTACTS_FILE
    notes_path = storage.DATA_DIR / storage.NOTES_FILE
    try:
        stores = {
            CONTACTS: storage.load_data(contacts_path, AddressBook),
            NOTES: storage.load_data(notes_path, NoteBook),
        }
    except (TypeError, ValueError) as e:
        print(err(f"Cannot load saved data: {e}"))
        return
    try:
        _run(stores)
    finally:
        storage.save_data(stores[CONTACTS], contacts_path)
        storage.save_data(stores[NOTES], notes_path)


def _run(stores: dict) -> None:
    print(paint("Welcome to the assistant bot!", Fore.GREEN), "Type 'help' to see all commands.")
    while True:
        try:
            user_input = _read(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print("\nGood bye!")
            break
        command, *args = parse_input(user_input)

        if command in EXIT_WORDS:
            print("Good bye!")
            break
        elif command == "":
            continue
        elif command == "hello":
            print("How can I help you?")
        elif command == "help":
            print(help_text())
        elif command in COMMANDS:
            handler, store, _, _ = COMMANDS[command]
            print(handler(args, stores[store]))
        else:
            print(unknown_command(command))


if __name__ == "__main__":
    main()

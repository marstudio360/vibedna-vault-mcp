#!/usr/bin/env python3
"""The vault itself: the encrypted file, and the way a human opens it without any AI.

This shipped broken. The MCP imported a `vault.py` from four folders above itself, which
is a path that only exists on the machine that built it, so on a buyer's computer the
whole thing started up unable to open anything. The crypto now lives here, inside the
package, and this file is also a command line, which answers the other half of the
problem: **you must be able to read your own keys without an AI in the room.**

    python vault_core.py init
    python vault_core.py list
    python vault_core.py show <name>
    python vault_core.py copy <name> <field>
    python vault_core.py add
    python vault_core.py export <name>          # as .env lines
    python vault_core.py where                  # where the file is, for your backups

One file, encrypted with a key derived from your master password (scrypt), sealed with
Fernet. The password is never written anywhere. Lose it and the file is gone: that is
what encryption means, and it is why `where` exists, so you can back the file up.
"""
from __future__ import annotations

import base64
import getpass
import json
import os
import sys
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
except ImportError:
    sys.exit("This needs the cryptography package: pip install cryptography")

# Where the vault lives. VAULT_HOME moves it, so it can sit in a synced folder if that is
# what you want; it is encrypted at rest either way.
HOME = Path(os.environ.get("VAULT_HOME", str(Path.home() / ".vibedna-vault")))
VAULT = HOME / "vault.enc"

SALT_SIZE = 32
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 17, 8, 1

CATEGORIES = ["api", "payment", "infra", "social", "login", "note",
              "exchange", "wallet", "seed", "telegram"]


def _derive(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                 backend=default_backend())
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _encrypt(data: dict, password: str) -> bytes:
    salt = os.urandom(SALT_SIZE)
    return salt + Fernet(_derive(password, salt)).encrypt(json.dumps(data).encode())


def _decrypt(raw: bytes, password: str) -> dict:
    salt, tok = raw[:SALT_SIZE], raw[SALT_SIZE:]
    try:
        return json.loads(Fernet(_derive(password, salt)).decrypt(tok))
    except InvalidToken:
        raise ValueError("wrong master password")


def load(password: str) -> dict:
    if not VAULT.exists():
        raise FileNotFoundError(f"no vault at {VAULT}. Create one: python vault_core.py init")
    return _decrypt(VAULT.read_bytes(), password)


def save(data: dict, password: str) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    VAULT.write_bytes(_encrypt(data, password))
    try:
        os.chmod(VAULT, 0o600)          # no-op on Windows, and correct everywhere else
    except OSError:
        pass


def empty() -> dict:
    return {"version": 1, "entries": {}}


# ─────────────────────────────── the human side ───────────────────────────────

def _pw(prompt="Master password: ") -> str:
    return getpass.getpass(prompt)


def _open() -> tuple[dict, str]:
    pw = _pw()
    try:
        return load(pw), pw
    except (ValueError, FileNotFoundError) as e:
        sys.exit(str(e))


def cmd_init():
    if VAULT.exists():
        sys.exit(f"there is already a vault at {VAULT}")
    pw = _pw("Choose a master password: ")
    if pw != _pw("Repeat it: "):
        sys.exit("they do not match")
    if len(pw) < 8:
        sys.exit("make it at least 8 characters")
    save(empty(), pw)
    print(f"vault created at {VAULT}")
    print("Back that file up. It is encrypted, so a copy in your cloud drive is fine.")


def cmd_list():
    data, _ = _open()
    entries = data.get("entries", {})
    if not entries:
        print("empty. Add one: python vault_core.py add")
        return
    print(f"{len(entries)} entries in {VAULT}\n")
    for name in sorted(entries):
        e = entries[name]
        fields = ", ".join(sorted((e.get("fields") or {}).keys()))
        print(f"  {name}  [{e.get('category', 'note')}]")
        if fields:
            print(f"      {fields}")


def cmd_show(name: str):
    data, _ = _open()
    e = (data.get("entries") or {}).get(name)
    if not e:
        sys.exit(f"no entry called {name}. See them all: python vault_core.py list")
    print(f"\n{name}  [{e.get('category', 'note')}]")
    for k, v in (e.get("fields") or {}).items():
        print(f"  {k} = {v}")
    if e.get("notes"):
        print(f"  notes: {e['notes']}")
    print()


def cmd_copy(name: str, field: str):
    data, _ = _open()
    e = (data.get("entries") or {}).get(name) or {}
    val = (e.get("fields") or {}).get(field)
    if val is None:
        sys.exit(f"{name} has no field called {field}")
    try:
        import subprocess
        if sys.platform == "win32":
            subprocess.run("clip", input=val.encode("utf-16le"), check=True)
        elif sys.platform == "darwin":
            subprocess.run("pbcopy", input=val.encode(), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=val.encode(), check=True)
        print(f"{name}.{field} copied to the clipboard")
    except Exception:
        # Printing it is worse than the clipboard and far better than not having it.
        print(f"could not reach the clipboard, so here it is:\n{val}")


def cmd_add():
    pw = _pw()
    try:
        data = load(pw)
    except FileNotFoundError:
        sys.exit("no vault yet. Create one: python vault_core.py init")
    except ValueError as e:
        sys.exit(str(e))
    name = input("name (e.g. anthropic-api): ").strip()
    if not name:
        sys.exit("a name is required")
    print(f"category, one of: {', '.join(CATEGORIES)}")
    cat = input("category [api]: ").strip() or "api"
    fields = {}
    print("fields, one per line as KEY=value. Empty line to finish.")
    while True:
        line = input("  ").strip()
        if not line:
            break
        if "=" not in line:
            print("  needs a KEY=value")
            continue
        k, v = line.split("=", 1)
        fields[k.strip()] = v.strip()
    notes = input("notes (optional): ").strip()
    data.setdefault("entries", {})[name] = {"category": cat, "fields": fields, "notes": notes}
    save(data, pw)
    print(f"saved {name} with {len(fields)} field(s)")


def cmd_export(name: str):
    data, _ = _open()
    e = (data.get("entries") or {}).get(name)
    if not e:
        sys.exit(f"no entry called {name}")
    for k, v in (e.get("fields") or {}).items():
        print(f"{k}={v}")


def cmd_where():
    print(f"vault file: {VAULT}")
    print(f"exists: {VAULT.exists()}")
    print("It is encrypted with your master password. Back it up anywhere; without the")
    print("password the file is meaningless, and without the file the password is too.")


USAGE = """vault_core.py, your keys without an AI in the room

  init                  create the vault
  list                  every entry and its field names (no values)
  show <name>           one entry, with its values
  copy <name> <field>   one value straight to the clipboard
  add                   add an entry
  export <name>         the entry as .env lines
  where                 the file's path, for your backups
"""


def main():
    a = sys.argv[1:]
    if not a:
        print(USAGE)
        return
    c = a[0].lower()
    if c == "init":                      cmd_init()
    elif c == "list":                    cmd_list()
    elif c == "show" and len(a) >= 2:    cmd_show(a[1])
    elif c == "copy" and len(a) >= 3:    cmd_copy(a[1], a[2])
    elif c == "add":                     cmd_add()
    elif c == "export" and len(a) >= 2:  cmd_export(a[1])
    elif c == "where":                   cmd_where()
    else:                                print(USAGE)


if __name__ == "__main__":
    main()

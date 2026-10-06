# Install Vault

Drop this file into a Claude chat and ask it to install the MCP. It has everything it needs. The manual steps are below and none of them are hard.

---

## What this is

One encrypted file on your machine that holds every key, token and password you use, and two ways in: your AI, so it stops asking you for the same key every week, and **you, from a terminal or a small desktop window, with no AI involved at all.**

That second way matters more than it sounds. A vault you can only open by asking a machine is not your vault.

## Install

```bash
git clone https://github.com/marstudio360/vibedna-vault-mcp
cd vibedna-vault-mcp
python -m venv .venv
# Windows:  .venv\Scripts\activate
# mac/linux: source .venv/bin/activate
pip install -r requirements.txt
```

(Or unzip the download from vibedna.ai and `cd` into that folder.)

## Create it

```bash
python vault_core.py init
```

It asks for a master password twice and writes one encrypted file. **Write that password down somewhere physical.** There is no reset: the encryption is real, and a vault whose password is lost is a file of noise. That is the trade you are making, and it is the right one.

Then ask where the file is, so you can back it up:

```bash
python vault_core.py where
```

Copy that file wherever you like, including a cloud drive. It is encrypted at rest, so a copy in someone else's storage is still only readable by you.

## Add your first keys

```bash
python vault_core.py add
```

Name it after the service (`anthropic-api`, `stripe`, `supabase-myapp`), pick a category, and add fields as `KEY=value`, one per line. The field names should be the exact variable names your code expects, because then this works:

```bash
python vault_core.py export anthropic-api > .env
```

## The window: double-click, type your password, edit

This answers the question that decides whether a vault is really yours: **how do I open it when no AI is around?**

- **Windows:** double-click `Open Vault.bat`
- **macOS:** double-click `open-vault.command`
- **Anywhere:** `python vault_ui.py`

It asks for your master password, then shows every entry on the left and its contents on the right, as plain `KEY=value` lines you can edit and save. There is a search box, a copy button, and buttons to add and delete. Nothing goes anywhere: no network, and the password lives in memory only while the window is open.

Three wrong passwords and the window closes. There is no reset, and there cannot be: that is what the encryption is protecting you from.

## Or from the terminal, if you prefer it

```bash
python vault_core.py list                 # everything, names only
python vault_core.py show anthropic-api   # one entry, with values
python vault_core.py copy stripe SECRET   # straight to the clipboard
```

## Give your AI access

Add this to your MCP config with the real paths:

```json
{
  "mcpServers": {
    "vault": {
      "command": "/absolute/path/to/vibedna-vault-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/vibedna-vault-mcp/server.py"]
    }
  }
}
```

On Windows the interpreter is `.venv\Scripts\python.exe`. With Claude Code you can also run:

```bash
claude mcp add vault --scope user -- /absolute/path/to/vibedna-vault-mcp/.venv/bin/python /absolute/path/to/vibedna-vault-mcp/server.py
```

The server reads the master password from your system keyring, and falls back to a `VAULT_MASTER_PASSWORD` environment variable for machines that have no keyring, like a headless server.

To store it in the keyring once:

```bash
python -c "import keyring; keyring.set_password('vibedna-vault','master', input('master password: '))"
```

Restart your client. Your AI can now find a key by name and put it where it belongs, and you stop pasting secrets into a chat window.

## The habit that makes this worth it

**Any key that appears in a conversation goes into the vault the same day.** Not later. A year from now you will not remember which of six services that token belonged to, and the vault will.

And in your code: read from the environment, never a literal. `os.environ.get("KEY")`, `process.env.KEY`. The vault fills the environment; the key never lands in a file you might share.

## If something breaks

- **Wrong master password.** There is no recovery. Try your other passwords; the file is fine and patient.
- **Your AI says the vault is unavailable.** The password is not in the keyring. Run the keyring line above, or set `VAULT_MASTER_PASSWORD`.
- **`cryptography` fails to install.** On Linux it wants a build toolchain: `apt install build-essential python3-dev` and try again.

## Support

admin@vibedna.ai · https://vibedna.ai/store/vault

License: MIT.

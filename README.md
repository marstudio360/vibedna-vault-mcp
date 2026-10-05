# VibeDNA Vault MCP

Encrypted local vault for API keys. Your AI fetches keys on demand and scans code for leaks.

Vault keeps every API key, token and password in one encrypted file on your machine (Fernet, with the key derived from your master password by scrypt). The master password is read from your system keyring, or from `VAULT_MASTER_PASSWORD` on machines with no keyring. Your AI searches the vault and fetches the exact key it needs when it needs it, so keys stop getting pasted into chats. It exports an entry as `.env` lines, tracks rotation dates, keeps a usage log, ships entry templates for common services, and scans a project folder for keys left in plain text, reporting file and line.

A desktop window (`vault_ui.py`) and a terminal CLI (`vault_core.py`) open the same vault with no AI involved. There is no password reset: lose the master password and the file stays unreadable.

Homepage: https://vibedna.ai/store/vault

## Tools (17)

| Tool | What it does |
|---|---|
| `credential_exists(name)` | Check whether an entry exists before asking the user for a key |
| `get_credential(name, key)` | Return one field of one entry |
| `list_credentials()` | Entry names, categories and field names. No values |
| `search_credentials(term)` | Search by name, category or notes |
| `add_credential(name, category, fields, notes)` | Add an entry (`fields` is a JSON object) |
| `edit_credential(name, fields)` | Update fields; an empty value removes that field |
| `delete_credential(name, confirm)` | Delete an entry (`confirm` must equal the name) |
| `export_env(name)` | The entry's fields as `KEY=value` lines |
| `add_with_template(service, name, fields, notes)` | Add an entry from a service template |
| `list_templates()` | The available templates |
| `scan_for_leaks(path)` | Scan a folder for plaintext keys: your vault's values plus known key patterns |
| `leak_history()` | Recent leak-scan results |
| `check_rotation_due(days)` | Entries not rotated in `days` |
| `mark_rotated(name)` | Record a rotation |
| `usage_log(name)` | Recent credential-access events |
| `backup_vault()` | Copy the encrypted file to the backup folder |
| `check_for_update()` | Compare this copy with the published version |

## Install

```bash
git clone https://github.com/marstudio360/vibedna-vault-mcp
cd vibedna-vault-mcp
python -m venv .venv
# Windows: .venv\Scripts\activate    mac/linux: source .venv/bin/activate
pip install -r requirements.txt
python vault_core.py init
```

Store the master password in your system keyring once, so the MCP server can open the vault:

```bash
python -c "import keyring; keyring.set_password('vibedna-vault','master', input('master password: '))"
```

### Claude Code

```bash
claude mcp add vault --scope user -- /absolute/path/to/vibedna-vault-mcp/.venv/bin/python /absolute/path/to/vibedna-vault-mcp/server.py
```

Or in a project's `.mcp.json`:

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

On Windows the interpreter is `.venv\Scripts\python.exe`.

### Cursor

Add the same `mcpServers` block to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).

### Claude Desktop

Add the same `mcpServers` block to `claude_desktop_config.json` (Settings > Developer > Edit Config), then restart Claude Desktop.

[INSTALL.md](./INSTALL.md) is a step-by-step guide written so you can paste it into an AI chat and let the AI do the install. It also covers the desktop window and the CLI.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `VAULT_HOME` | `~/.vibedna-vault` | Folder of the encrypted vault file (`vault.enc`) |
| `VAULT_MASTER_PASSWORD` | (unset) | Master password for machines with no system keyring |
| `VAULT_BACKUP_HOME` | `~/.vibedna-vault/backups` | Where `backup_vault` writes copies (the last 30 are kept) |

The usage log and leak-scan results are written next to the vault file, in `logs/`.

## Network

The vault, the window and the CLI make no network calls. `check_for_update` is the one tool that does: it asks `https://vibedna.ai/api/mcp/latest` for the published version number.

## License

MIT, see [LICENSE](./LICENSE). Copyright (c) 2026 VibeDNA.

Support: admin@vibedna.ai

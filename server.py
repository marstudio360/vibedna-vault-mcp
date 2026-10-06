"""
VibeDNA Vault MCP: a local credential broker.
Gives your AI on-demand access to an encrypted vault file on your machine.
The master password lives in your system keyring (or VAULT_MASTER_PASSWORD), never in plaintext.

Tools:
  credential_exists(name)          - check before asking the user for a key
  get_credential(name, key)        - retrieve a specific key value
  list_credentials()               - all names + categories (no values)
  search_credentials(term)         - find by name or category
  add_credential(name, category, fields, notes) - add new entry
"""

import os
import sys
import json
import keyring
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# El cifrado viaja ADENTRO del paquete. Esto apuntaba a una carpeta cuatro niveles
# arriba, la de la maquina que lo construyo, asi que en la computadora de un comprador
# el MCP arrancaba sin poder abrir absolutamente nada. Ahora es un import local, y el
# mismo archivo es ademas una linea de comandos: el dueno puede leer sus claves sin IA.
sys.path.insert(0, str(Path(__file__).parent))

try:
    import vault_core as _vault_mod
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False

KEYRING_SERVICE = "vibedna-vault"
KEYRING_USER    = "master"

mcp = FastMCP("vault-mcp")

# This copy's version. Bump it when packaging; check_for_update compares it against
# what the site currently publishes, so an installed copy can tell it is behind.
VERSION = "1.1.1"
PRODUCT_SLUG = "vault"


@mcp.tool()
def check_for_update() -> str:
    """Is this copy behind the published version?

    Your copy is a folder on your machine, so it stays exactly as it was the day you
    installed it while fixes keep shipping. This asks what is published now and tells
    you whether to update, and how. It sends nothing about you: just a version number
    comes back."""
    import json as _json
    import urllib.request as _url
    try:
        req = _url.Request(
            "https://vibedna.ai/api/mcp/latest?slug=" + PRODUCT_SLUG,
            headers={"Accept": "application/json"},
        )
        with _url.urlopen(req, timeout=15) as r:
            d = _json.loads(r.read() or b"{}")
    except Exception as e:
        return f"could not reach the update check ({type(e).__name__}). Your copy still works; try later."

    latest = str(d.get("version") or "")
    if not latest:
        return "the update service did not report a version. Nothing to do."

    def parts(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)

    if parts(latest) <= parts(VERSION):
        return f"up to date (you have {VERSION}, published is {latest})."

    return "\n".join([
        f"UPDATE AVAILABLE: you have {VERSION}, published is {latest}.",
        "",
        "To update, from the same email you bought with:",
        f"  1. Download: https://vibedna.ai/api/download?slug={PRODUCT_SLUG}&license=<your key>",
        "     (your key is in your purchase email, and in your library at vibedna.ai/library)",
        "  2. Unzip over your current folder, keeping your own files:",
        "     your .env stays as it is.",
        "  3. Restart your AI so it loads the new tools.",
        "",
        "Your stored credentials are not in this folder: they live in your encrypted",
        "vault file, and your master password lives in your system keyring. An update",
        "replaces code only, never your entries or your password.",
    ])


def _get_password() -> str | None:
    """La clave maestra sale del llavero del sistema, y si no, del entorno.

    Sin el respaldo por entorno, un comprador que corre esto en un servidor sin llavero
    (una caja Linux headless, un contenedor) no tenia forma de darle la clave y el MCP
    quedaba mudo sin decir por que.
    """
    import os as _os
    return (keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
            or _os.environ.get("VAULT_MASTER_PASSWORD", "").strip() or None)


def _load_vault() -> tuple[dict, dict] | tuple[None, None]:
    """Returns (full_data, entries_dict) or (None, None) on failure."""
    if not VAULT_AVAILABLE:
        return None, None
    pwd = _get_password()
    if not pwd:
        return None, None
    try:
        data = _vault_mod.load(pwd)
        entries = data.get("entries", {})
        return data, entries
    except Exception:
        return None, None


def _save_vault(data: dict) -> bool:
    if not VAULT_AVAILABLE:
        return False
    pwd = _get_password()
    if not pwd:
        return False
    try:
        _vault_mod.save(data, pwd)
        return True
    except Exception:
        return False


def _get_fields(entry: dict) -> dict:
    """Normalize entry - vault uses 'fields', our new entries also use 'fields'."""
    return entry.get("fields", {})


@mcp.tool()
def credential_exists(name: str) -> str:
    """[FREE] Check if a named credential exists in the vault before asking the user for it."""
    _, entries = _load_vault()
    if entries is None:
        return "Vault unavailable - check the system keyring has the master password (or set VAULT_MASTER_PASSWORD)."
    if name in entries:
        entry = entries[name]
        field_names = list(_get_fields(entry).keys())
        return f"YES - '{name}' exists. Category: {entry.get('category','?')}. Fields: {field_names}"
    close = [k for k in entries if name.lower() in k.lower()]
    if close:
        return f"NO exact match for '{name}'. Similar entries: {close}"
    return f"NO - '{name}' not in vault."


@mcp.tool()
def get_credential(name: str, key: str = "") -> str:
    """[FREE] Retrieve a credential value from the vault by entry name and field/key name."""
    _, entries = _load_vault()
    if entries is None:
        return "Vault unavailable - check the system keyring has the master password (or set VAULT_MASTER_PASSWORD)."
    if name not in entries:
        close = [k for k in entries if name.lower() in k.lower()]
        hint = f" Did you mean: {close}?" if close else ""
        return f"Entry '{name}' not found.{hint}"
    fields = _get_fields(entries[name])
    if not key:
        if len(fields) == 1:
            only_key = next(iter(fields))
            _log_usage(name, only_key)
            return fields[only_key]
        return f"Multiple fields in '{name}': {list(fields.keys())}. Call get_credential('{name}', key=<field_name>)."
    if key not in fields:
        return f"Field '{key}' not found in '{name}'. Available: {list(fields.keys())}"
    _log_usage(name, key)
    return fields[key]


@mcp.tool()
def list_credentials() -> str:
    """[FREE] List all vault entries - names, categories, field names. No values shown."""
    _, entries = _load_vault()
    if entries is None:
        return "Vault unavailable."
    if not entries:
        return "Vault is empty."
    by_cat: dict[str, list] = {}
    for name, entry in entries.items():
        cat = entry.get("category", "misc")
        field_names = list(_get_fields(entry).keys())
        by_cat.setdefault(cat, []).append((name, field_names))
    lines = [f"Vault - {len(entries)} entries:"]
    for cat, items in sorted(by_cat.items()):
        lines.append(f"\n[{cat.upper()}]")
        for name, field_names in items:
            lines.append(f"  {name}: {field_names}")
    return "\n".join(lines)


@mcp.tool()
def search_credentials(term: str) -> str:
    """[FREE] Search vault entries by name, category, or notes."""
    _, entries = _load_vault()
    if entries is None:
        return "Vault unavailable."
    term_lower = term.lower()
    matches = []
    for name, entry in entries.items():
        searchable = (name + " " + entry.get("category", "") + " " +
                      entry.get("notes", "")).lower()
        if term_lower in searchable:
            field_names = list(_get_fields(entry).keys())
            matches.append(f"  {name} [{entry.get('category','?')}]: {field_names}")
    if not matches:
        return f"No entries matching '{term}'."
    return f"Found {len(matches)} match(es) for '{term}':\n" + "\n".join(matches)


@mcp.tool()
def add_credential(name: str, category: str, fields: str, notes: str = "") -> str:
    """[FREE] Add a new credential. fields = JSON string e.g. '{\"API_KEY\": \"value\"}'."""
    full_data, entries = _load_vault()
    if full_data is None:
        return "Vault unavailable - cannot add credential."
    try:
        field_dict = json.loads(fields)
    except json.JSONDecodeError as e:
        return f"fields must be valid JSON: {e}"
    if name in entries:
        existing = list(_get_fields(entries[name]).keys())
        return f"Entry '{name}' already exists with fields: {existing}. Use get_credential to retrieve."
    import datetime
    now = datetime.datetime.utcnow().isoformat()
    full_data["entries"][name] = {
        "category": category,
        "fields": field_dict,
        "notes": notes,
        "created": now,
        "updated": now,
        "last_rotated": now,
    }
    if _save_vault(full_data):
        return f"Added '{name}' [{category}] to vault. Fields stored: {list(field_dict.keys())}"
    return "Failed to save vault."


# ============= Phase 2: extended tools =============

# El archivo cifrado y donde van los respaldos. Los dos salian de rutas de la maquina
# que construyo esto: una carpeta suya y un disco suyo. En la
# computadora de un comprador ninguna de las dos existe, asi que respaldaba al vacio.
VAULT_FILE_PATH = _vault_mod.VAULT if VAULT_AVAILABLE else Path.home() / ".vibedna-vault" / "vault.enc"
DEFAULT_BACKUP_HOME = Path.home() / ".vibedna-vault" / "backups"
BACKUP_RETAIN = 30


def _backup_dir() -> Path:
    return Path(os.environ.get("VAULT_BACKUP_HOME") or DEFAULT_BACKUP_HOME)


def _do_backup() -> tuple[bool, str]:
    """Copy encrypted vault file to backup home. No password needed - file is encrypted."""
    import shutil, datetime
    if not VAULT_FILE_PATH.exists():
        return False, f"Vault file not found at {VAULT_FILE_PATH}"
    home = _backup_dir()
    try:
        home.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = home / f".vault_{ts}"
        shutil.copy2(VAULT_FILE_PATH, dest)
        backups = sorted(home.glob(".vault_*"))
        for old in backups[:-BACKUP_RETAIN]:
            try:
                old.unlink()
            except Exception:
                pass
        return True, str(dest)
    except Exception as e:
        return False, f"Backup failed: {e}"


@mcp.tool()
def backup_vault() -> str:
    """[FREE] Trigger an encrypted backup of the vault now. Returns destination path."""
    ok, info = _do_backup()
    return f"Backup saved: {info}" if ok else info


@mcp.tool()
def edit_credential(name: str, fields: str) -> str:
    """[FREE] Update fields on an existing entry. fields = JSON dict.
    Pass an empty string '' as the value to delete that field."""
    import datetime
    full_data, entries = _load_vault()
    if full_data is None:
        return "Vault unavailable."
    if name not in entries:
        close = [k for k in entries if name.lower() in k.lower()]
        hint = f" Did you mean: {close}?" if close else ""
        return f"Entry '{name}' not found.{hint}"
    try:
        updates = json.loads(fields)
    except json.JSONDecodeError as e:
        return f"fields must be valid JSON: {e}"
    entry = entries[name]
    current = entry.setdefault("fields", {})
    changed, removed = [], []
    for k, v in updates.items():
        if v == "":
            if k in current:
                del current[k]
                removed.append(k)
        else:
            current[k] = v
            changed.append(k)
    now_iso = datetime.datetime.utcnow().isoformat()
    entry["updated"] = now_iso
    if changed:
        entry["last_rotated"] = now_iso
    if _save_vault(full_data):
        parts = []
        if changed:
            parts.append(f"updated {changed} (rotation timestamp refreshed)")
        if removed:
            parts.append(f"removed {removed}")
        return f"'{name}': " + ("; ".join(parts) if parts else "no changes")
    return "Failed to save vault."


@mcp.tool()
def delete_credential(name: str, confirm: str) -> str:
    """[FREE] Delete an entry. confirm must equal name exactly (safety check)."""
    full_data, entries = _load_vault()
    if full_data is None:
        return "Vault unavailable."
    if name not in entries:
        return f"Entry '{name}' not found."
    if confirm != name:
        return f"Confirmation mismatch - pass confirm='{name}' to delete."
    del full_data["entries"][name]
    if _save_vault(full_data):
        return f"Deleted '{name}'."
    return "Failed to save vault."


@mcp.tool()
def export_env(name: str) -> str:
    """[FREE] Return an entry's fields formatted as KEY=value lines for env loading.
    Field names are upper-cased and hyphens/spaces become underscores."""
    _, entries = _load_vault()
    if entries is None:
        return "Vault unavailable."
    if name not in entries:
        return f"Entry '{name}' not found."
    fields = _get_fields(entries[name])
    if not fields:
        return f"'{name}' has no fields."
    lines = []
    for k, v in fields.items():
        env_key = k.upper().replace("-", "_").replace(" ", "_")
        lines.append(f"{env_key}={v}")
    return "\n".join(lines)


@mcp.tool()
def scan_for_leaks(path: str = "") -> str:
    """[FREE] Scan a codebase for plaintext credentials. Checks against vault values
    AND known API key patterns (Anthropic, Stripe, GitHub, Meta, Google, Cloudflare,
    Vercel, Supabase, Resend, Notion). path = directory to scan; defaults to the current working directory."""
    import re
    _, entries = _load_vault()
    if entries is None:
        return "Vault unavailable."
    root = Path(path) if path else Path.cwd()
    if not root.exists():
        return f"Path not found: {root}"
    known = set()
    for entry in entries.values():
        for v in _get_fields(entry).values():
            v = str(v).strip()
            if len(v) > 12 and v not in ("DELETE", ""):
                known.add(v)
    PATTERNS = [
        (r"sk-ant-api[0-9a-zA-Z\-]+", "Anthropic API key"),
        (r"sk_live_[0-9a-zA-Z]+", "Stripe live secret"),
        (r"rk_live_[0-9a-zA-Z]+", "Stripe live restricted"),
        (r"ghp_[0-9a-zA-Z]+", "GitHub PAT"),
        (r"EAAL[0-9a-zA-Z]+", "Meta/Facebook token"),
        (r"AIzaSy[0-9a-zA-Z\-_]+", "Google/Gemini key"),
        (r"cfut_[0-9a-zA-Z]+", "Cloudflare token"),
        (r"vcp_[0-9a-zA-Z]+", "Vercel token"),
        (r"sb_secret_[0-9a-zA-Z\-_]+", "Supabase service key"),
        (r"sbp_[0-9a-zA-Z]+", "Supabase access key"),
        (r"re_[0-9a-zA-Z]{20,}", "Resend API key"),
        (r"ntn_[0-9a-zA-Z]+", "Notion token"),
    ]
    SKIP = {".git", "node_modules", "__pycache__", ".vault", "backups",
            "venv", ".env", ".next", "build", "dist", ".dart_tool"}
    EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".env", ".txt", ".yaml",
            ".yml", ".toml", ".sh", ".ps1", ".json"}
    findings = []
    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        if any(p in SKIP for p in fp.parts):
            continue
        if fp.suffix.lower() not in EXTS:
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = fp.relative_to(root)
        for secret in known:
            if secret in content:
                ln = next((i + 1 for i, l in enumerate(content.splitlines()) if secret in l), 0)
                findings.append((str(rel), ln, "vault match"))
        for pat, label in PATTERNS:
            for m in re.finditer(pat, content):
                ln = content[:m.start()].count("\n") + 1
                findings.append((str(rel), ln, label))
    seen, uniq = set(), []
    for f in findings:
        k = (f[0], f[1], f[2])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    _log_leak_scan(str(root), uniq)
    if not uniq:
        return f"[CLEAN] No plaintext secrets in {root}"
    lines = [f"[WARNING] {len(uniq)} leak(s) in {root}:"]
    for fp, ln, label in sorted(uniq)[:50]:
        lines.append(f"  {fp}:{ln}  [{label}]")
    if len(uniq) > 50:
        lines.append(f"  ... +{len(uniq) - 50} more")
    return "\n".join(lines)


# ============= Phase 3: intelligence layer =============

LOG_DIR = VAULT_FILE_PATH.parent / "logs"
USAGE_LOG = LOG_DIR / "usage.jsonl"
LEAK_LOG = LOG_DIR / "leaks.jsonl"

TEMPLATES = {
    # ── Logins (site + service accounts) ──
    "login":            ["site_url", "username", "email", "password", "recovery_codes", "totp_secret"],
    "bank":             ["bank_name", "account_holder", "account_number", "routing_number", "swift_code", "online_login_email", "online_login_password"],
    "email":            ["provider", "email", "password", "app_password", "recovery_email"],
    "domain_registrar": ["provider", "login_email", "password", "totp_secret", "recovery_codes"],
    "vps":              ["host", "user", "port", "ssh_key_path", "password", "root_password"],

    # ── Payments ──
    "stripe":        ["publishable_key", "secret_key", "webhook_secret", "account_id"],
    "gumroad":       ["access_token"],
    "paypal":        ["client_id", "client_secret", "login_email"],
    "lemon_squeezy": ["api_key", "store_id"],

    # ── Hosting / Infra ──
    "supabase":     ["url", "anon_key", "service_key", "project_ref"],
    "vercel":       ["token", "team_id"],
    "netlify":      ["auth_token", "site_id"],
    "fly":          ["api_token", "app_name"],
    "render":       ["api_key"],
    "railway":      ["api_token"],
    "cloudflare":   ["token", "account_id", "zone_id"],
    "digitalocean": ["api_token", "ssh_key_id"],
    "aws":          ["access_key_id", "secret_access_key", "region", "account_id"],

    # ── Databases ──
    "postgres": ["host", "port", "database", "user", "password", "connection_string"],
    "redis":    ["host", "port", "password", "connection_string"],

    # ── Dev tools ──
    "github":      ["token"],
    "huggingface": ["api_token"],
    "ngrok":       ["auth_token"],
    "figma":       ["login_email", "password", "personal_access_token"],
    "linear":      ["api_key", "team_id"],
    "notion":      ["token"],

    # ── AI providers ──
    "anthropic":  ["api_key"],
    "openai":     ["api_key"],
    "gemini":     ["api_key"],
    "replicate":  ["api_token"],
    "mistral":    ["api_key"],
    "groq":       ["api_key"],
    "together":   ["api_key"],

    # ── AI media (image/video/voice) ──
    "midjourney": ["discord_account", "login_email", "password"],
    "elevenlabs": ["api_key", "voice_id"],
    "runway":     ["api_key"],

    # ── Research / scraping ──
    "exa":       ["api_key"],
    "firecrawl": ["api_key"],

    # ── Email marketing ──
    "resend":     ["api_key", "audience_id"],
    "mailchimp":  ["api_key", "list_id", "server_prefix"],
    "convertkit": ["api_key", "api_secret"],
    "beehiiv":    ["api_key", "publication_id"],

    # ── Analytics ──
    "plausible": ["api_key", "site_id"],
    "posthog":   ["api_key", "project_id", "host"],
    "google":    ["client_id", "client_secret", "refresh_token"],

    # ── Social (logins + APIs) ──
    "twitter":   ["bearer_token", "api_key", "api_secret", "access_token", "access_token_secret"],
    "meta":      ["app_id", "app_secret", "access_token"],
    "linkedin":  ["login_email", "password", "app_client_id", "app_client_secret", "access_token"],
    "reddit":    ["username", "password", "client_id", "client_secret", "refresh_token"],
    "tiktok":    ["login_email", "password", "app_id", "app_secret", "access_token"],
    "discord":   ["bot_token", "client_id", "client_secret"],
    "telegram":  ["bot_token", "chat_id"],

    # ── Crypto ──
    "kraken":  ["api_key", "api_secret"],
    "binance": ["api_key", "api_secret"],
}


def _log_usage(entry_name: str, field: str) -> None:
    """Append a JSONL audit record. Silent on failure - never blocks credential access."""
    try:
        import datetime
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "name": entry_name,
            "field": field,
            "cwd": os.getcwd(),
            "session": os.environ.get("CLAUDE_SESSION_ID", ""),
        }
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _log_leak_scan(root: str, findings: list) -> None:
    """Append a leak-scan event. Stores counts + file/line metadata, never raw secret values."""
    try:
        import datetime
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "root": root,
            "count": len(findings),
            "hits": [{"file": fp, "line": ln, "label": label} for fp, ln, label in findings[:200]],
        }
        with LEAK_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _tail_jsonl(path: Path, last_n: int) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        out = []
        for line in lines[-last_n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
    except Exception:
        return []


@mcp.tool()
def check_rotation_due(days: int = 90) -> str:
    """[FREE] List credentials whose last_rotated timestamp is older than `days`.
    Entries with no last_rotated field are flagged as 'unknown' (created before Phase 3)."""
    import datetime
    _, entries = _load_vault()
    if entries is None:
        return "Vault unavailable."
    if not entries:
        return "Vault is empty."
    now = datetime.datetime.utcnow()
    threshold = datetime.timedelta(days=days)
    overdue, unknown = [], []
    for name, entry in entries.items():
        lr = entry.get("last_rotated")
        cat = entry.get("category", "?")
        if not lr:
            unknown.append((name, cat))
            continue
        try:
            ts = datetime.datetime.fromisoformat(lr)
            age = now - ts
            if age > threshold:
                overdue.append((name, cat, age.days))
        except Exception:
            unknown.append((name, cat))
    lines = []
    if overdue:
        lines.append(f"OVERDUE (>{days} days):")
        for name, cat, age in sorted(overdue, key=lambda x: -x[2]):
            lines.append(f"  [{cat}] {name} - {age} days since last rotation")
    if unknown:
        lines.append(f"\nUNKNOWN (no rotation timestamp - created before tracking):")
        for name, cat in sorted(unknown):
            lines.append(f"  [{cat}] {name}")
    if not lines:
        return f"All {len(entries)} entries within {days}-day rotation window."
    return "\n".join(lines)


@mcp.tool()
def mark_rotated(name: str) -> str:
    """[FREE] Manually flag a credential as just-rotated. Updates the last_rotated timestamp
    without changing the actual values. Use after rotating a key in the provider's dashboard."""
    import datetime
    full_data, entries = _load_vault()
    if full_data is None:
        return "Vault unavailable."
    if name not in entries:
        return f"Entry '{name}' not found."
    now = datetime.datetime.utcnow().isoformat()
    entries[name]["last_rotated"] = now
    entries[name]["updated"] = now
    if _save_vault(full_data):
        return f"'{name}' rotation timestamp refreshed."
    return "Failed to save vault."


@mcp.tool()
def usage_log(name: str = "", last_n: int = 20) -> str:
    """[FREE] Show recent credential-access events. Pass name to filter by entry."""
    events = _tail_jsonl(USAGE_LOG, max(last_n * 4, 100) if name else last_n)
    if name:
        events = [e for e in events if e.get("name") == name][-last_n:]
    else:
        events = events[-last_n:]
    if not events:
        return f"No usage events{' for ' + name if name else ''}."
    lines = [f"Last {len(events)} usage event(s):"]
    for e in events:
        ts = e.get("ts", "?")[:19].replace("T", " ")
        lines.append(f"  {ts}  {e.get('name','?')}.{e.get('field','?')}  cwd={e.get('cwd','?')}")
    return "\n".join(lines)


@mcp.tool()
def leak_history(last_n: int = 10) -> str:
    """[FREE] Show recent leak-scan results from the leak ledger."""
    events = _tail_jsonl(LEAK_LOG, last_n)
    if not events:
        return "No leak scans recorded yet. Run scan_for_leaks to populate."
    lines = [f"Last {len(events)} leak scan(s):"]
    for e in events:
        ts = e.get("ts", "?")[:19].replace("T", " ")
        cnt = e.get("count", 0)
        root = e.get("root", "?")
        marker = "CLEAN" if cnt == 0 else f"{cnt} hit(s)"
        lines.append(f"  {ts}  [{marker}]  {root}")
    return "\n".join(lines)


@mcp.tool()
def list_templates() -> str:
    """[FREE] List available service templates for add_with_template."""
    lines = [f"{len(TEMPLATES)} templates available:"]
    for service in sorted(TEMPLATES.keys()):
        fields = TEMPLATES[service]
        lines.append(f"  {service:<12} → {', '.join(fields)}")
    return "\n".join(lines)


@mcp.tool()
def add_with_template(service: str, name: str, fields: str, notes: str = "") -> str:
    """[FREE] Add a credential using a service template. service = key from list_templates
    (e.g. 'stripe', 'supabase'). Missing template fields are allowed but flagged."""
    if service not in TEMPLATES:
        close = [s for s in TEMPLATES if service.lower() in s.lower()]
        hint = f" Did you mean: {close}?" if close else f" Run list_templates for options."
        return f"Unknown service '{service}'.{hint}"
    try:
        field_dict = json.loads(fields)
    except json.JSONDecodeError as e:
        return f"fields must be valid JSON: {e}"
    expected = TEMPLATES[service]
    missing = [f for f in expected if f not in field_dict]
    extra = [f for f in field_dict if f not in expected]
    result = add_credential(name, service, fields, notes)
    notes_out = []
    if missing:
        notes_out.append(f"missing expected fields: {missing}")
    if extra:
        notes_out.append(f"extra fields (kept): {extra}")
    if notes_out:
        return result + "\n  ⚠ " + "; ".join(notes_out)
    return result


if __name__ == "__main__":
    if "--backup" in sys.argv:
        ok, info = _do_backup()
        if not ok:
            print(f"[vault-backup] {info}", file=sys.stderr)
        sys.exit(0)
    if os.environ.get("PORT"):
        import uvicorn
        uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=int(os.environ["PORT"]))
    else:
        mcp.run()  # stdio for local .mcp.json

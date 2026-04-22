# 🛡️ Security

eVera implements defense-in-depth security across multiple layers.

---

## API Authentication

All REST and WebSocket endpoints are protected by API key authentication when `VERA_SERVER_API_KEY` is configured.

**How it works:**
- Set `VERA_SERVER_API_KEY=my-secret-key` in `.env`
- Include `Authorization: Bearer my-secret-key` header in requests
- Or pass `?api_key=my-secret-key` as query parameter
- Public endpoints exempt: `/`, `/health`, `/static/*`

**WebSocket authentication:**
- Pass API key as query parameter: `ws://localhost:8000/ws?api_key=my-secret-key`

---

## Safety Policy Engine

**File:** `vera/safety/policy.py`

Every agent action is evaluated against a rule-based policy before execution.

### Policy Actions

| Action | Meaning |
|--------|---------|
| `ALLOW` | Execute immediately without asking |
| `CONFIRM` | Ask user for explicit approval before executing |
| `DENY` | Block the action entirely |

### Rule Evaluation Order

1. **Specific rule** — Match `agent.tool` exactly (e.g., `operator.execute_script`)
2. **Wildcard rule** — Match `agent.*` (e.g., `companion.*`)
3. **Config denied list** — `VERA_SAFETY_DENIED_ACTIONS`
4. **Config confirm list** — `VERA_SAFETY_CONFIRM_ACTIONS`
5. **Config allowed list** — `VERA_SAFETY_ALLOWED_ACTIONS`
6. **Default** — `CONFIRM` (unknown actions require approval)

### Example Rules

| Pattern | Action | Reason |
|---------|--------|--------|
| `companion.*` | ALLOW | Chat is always safe |
| `operator.open_application` | ALLOW | Opening apps is low risk |
| `operator.execute_script` | CONFIRM | Scripts could be dangerous |
| `operator.manage_process` | CONFIRM | Process management is sensitive |
| `income.smart_trade` | CONFIRM | Real money trades need approval |
| `income.transfer_money` | DENY | Money transfers always blocked |
| `browser.login` | CONFIRM | Login actions need approval |

---

## PII Detection & Privacy

**File:** `vera/safety/privacy.py`

The PrivacyGuard detects and anonymizes Personally Identifiable Information before sending transcripts to cloud LLMs.

### Detected PII Types

| Type | Pattern | Replacement |
|------|---------|-------------|
| Email | `user@domain.com` | `[EMAIL]` |
| Phone | `(555) 123-4567` | `[PHONE]` |
| SSN | `123-45-6789` | `[SSN]` |
| Credit Card | `4111-1111-1111-1111` | `[CARD]` |
| IP Address | `192.168.1.1` | `[IP]` |

### Local Processing

If the transcript contains sensitive content, the PrivacyGuard forces processing to Tier 1 (local LLM) to prevent PII from reaching cloud providers.

---

## Path Sandboxing

File operations (read, write, edit, delete) are restricted to safe directories:

### Allowed Paths
- User's home directory (`~`)
- Current working directory
- Explicit project paths

### Blocked Paths
- `~/.ssh/` — SSH keys
- `~/.env` — Environment files
- `~/.aws/` — AWS credentials
- `~/.gnupg/` — GPG keys
- System directories (`/etc/`, `C:\Windows\`, etc.)

---

## Command Blocking

The `execute_script` tool blocks 30+ dangerous shell patterns:

| Category | Blocked Patterns |
|----------|------------------|
| Destructive | `rm -rf`, `rmdir /s`, `del /s`, `format c:`, `mkfs`, `shred` |
| Fork bombs | `:(){ :\|: & };:` |
| Pipe injection | `curl\|bash`, `wget\|sh`, `base64 -d\|` |
| Network | `nc -e`, `ncat -e`, `netcat` |
| Permissions | `chmod 777 /`, `chown root` |
| System | `shutdown`, `reboot`, `halt` |
| Registry | `reg delete`, `reg add`, `bcdedit` |
| PowerShell | `Remove-Item C:\`, `Remove-Item -Recurse -Force` |

### Shell Injection Prevention
- Python and PowerShell commands are checked for metacharacter injection (`;`, `&&`, `||`, `` ` ``, `$(`)
- Shell commands use `shlex.split()` instead of `shell=True` where possible

---

## Encrypted Storage

**File:** `vera/memory/secure.py`

Sensitive data is encrypted with Fernet symmetric encryption:

- **Browser credentials** — Passwords stored by the Browser Agent
- **Session cookies** — Stored alongside encrypted vault
- **Key derivation** — Automatic key generation and storage
- **File location** — `data/vault.enc` (configurable)

---

## Trade Safety

Real broker trades (Alpaca, IBKR) have additional safety measures:

| Measure | Details |
|---------|---------|
| Confirmation required | All real trades require explicit user approval |
| Auto-trade limit | Maximum $500 per automatic trade (configurable) |
| Audit log | All trades logged to `data/trade_log.json` |
| Paper trading default | New users start with $100k virtual portfolio |
| Webhook verification | TradingView webhooks require `X-Webhook-Secret` |

---

## Server Hardening

| Setting | Default | Description |
|---------|---------|-------------|
| `VERA_SERVER_HOST` | `127.0.0.1` | Localhost only (not network accessible) |
| `VERA_SERVER_CORS_ORIGINS` | `["http://localhost:8000"]` | Strict CORS policy |
| `VERA_SERVER_API_KEY` | (empty) | API key authentication |
| `VERA_SERVER_WEBHOOK_SECRET` | (empty) | Webhook verification secret |

---

## RBAC (Role-Based Access Control)

**File:** `vera/rbac.py`

Enterprise-grade user management:

| Role | Permissions |
|------|-------------|
| `admin` | Full access — manage users, view audit log, all endpoints |
| `user` | Standard access — chat, agents, memory, workflows |
| `viewer` | Read-only — view status, agents, memory facts |

- Password hashing: PBKDF2 with SHA-256
- Full audit logging of all user actions
- Per-user API key generation

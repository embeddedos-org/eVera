# eVera — Production Deployment Guide

This guide covers deploying eVera to a production server with HTTPS, nginx reverse proxy, and Docker.

---

## Quick Start (Cloud / VPS)

### 1. Prerequisites

- A Linux server (Ubuntu 22.04+ recommended) with Docker and Docker Compose installed
- A domain name pointing to your server (e.g., `evera.yourdomain.com`)
- At least one LLM API key (OpenAI, Gemini, Anthropic, or Groq)

### 2. Clone and Configure

```bash
git clone https://github.com/embeddedos-org/eVera.git
cd eVera
cp .env.example .env
```

Edit `.env` and set:

```env
# Required: at least one LLM provider
VERA_LLM_OPENAI_API_KEY=sk-...

# Required for production security
VERA_SERVER_API_KEY=your-strong-random-key-here

# Your production domain
VERA_SERVER_CORS_ORIGINS=["https://evera.yourdomain.com"]
```

### 3. Configure Nginx

Edit `deploy/nginx/conf.d/evera.conf` and replace `evera.embeddedos.org` with your domain.

### 4. Obtain TLS Certificate

```bash
# First, start nginx in HTTP-only mode to get the cert
docker compose up -d nginx

# Get certificate
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d evera.yourdomain.com \
  --email your@email.com \
  --agree-tos --no-eff-email

# Restart nginx with TLS enabled
docker compose restart nginx
```

### 5. Start All Services

```bash
docker compose up -d
```

### 6. Verify

```bash
curl https://evera.yourdomain.com/health
# Expected: {"status": "ok", ...}
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `VERA_SERVER_HOST` | `0.0.0.0` | Bind address (`0.0.0.0` for all interfaces) |
| `VERA_SERVER_PORT` | `8000` | Internal port (nginx proxies to this) |
| `VERA_SERVER_API_KEY` | _(empty)_ | API key for authentication — **set this in production** |
| `VERA_SERVER_CORS_ORIGINS` | `["https://evera.embeddedos.org",...]` | Allowed CORS origins |
| `VERA_SERVER_ZONE_WWW_ENABLED` | `true` | Allow public internet connections |
| `VERA_SERVER_ZONE_WWW_AUTH_REQUIRED` | `true` | Require API key for public connections |
| `VERA_SERVER_ZONE_WWW_RATE_LIMIT_RPM` | `60` | Rate limit: requests per minute per IP |
| `VERA_LLM_OPENAI_API_KEY` | _(empty)_ | OpenAI API key |
| `VERA_LLM_GEMINI_API_KEY` | _(empty)_ | Google Gemini API key |
| `VERA_LLM_ANTHROPIC_API_KEY` | _(empty)_ | Anthropic Claude API key |
| `VERA_LLM_GROQ_API_KEY` | _(empty)_ | Groq API key (fast inference) |
| `VERA_LLM_FALLBACK_ORDER` | `ollama,openai,gemini` | LLM provider fallback order |

---

## Network Zones

eVera uses a three-zone security model:

| Zone | Source | Auth Required | Rate Limited |
|---|---|---|---|
| **LOCAL** | `127.0.0.1`, `::1` | No | No |
| **LAN** | `10.x`, `172.16-31.x`, `192.168.x` | Yes (API key) | No |
| **WWW** | Public internet | Yes (API key) | Yes (60 rpm) |

---

## Chrome Extension

The extension defaults to `https://evera-api.embeddedos.org`. Users can change the server URL in the extension Options page.

To use your own server:
1. Open extension Options
2. Set **Server URL** to `https://evera.yourdomain.com`
3. Set **API Key** if authentication is enabled
4. Click **Save**

---

## Mobile App

The mobile app defaults to `evera-api.embeddedos.org:443` with HTTPS.

To use your own server:
1. Open the app Settings screen
2. Set **Server IP / Hostname** to your domain
3. Enable **Use HTTPS/WSS**
4. Tap **Test & Connect**

---

## GPS / Location Support

eVera supports GPS location for location-aware agents (weather, travel, nearby search).

- **Web**: The browser will prompt for location permission on first visit. Location is sent to `/location/update` and stored in semantic memory.
- **Mobile**: The app requests foreground location permission and sends updates automatically.
- **Privacy**: Location data is stored only in the server's in-memory semantic store and is not persisted to disk by default.

---

## i18n / Language Support

eVera supports 19 languages:

| Code | Language | Code | Language |
|---|---|---|---|
| `en` | English | `ar` | Arabic |
| `es` | Spanish | `de` | German |
| `fr` | French | `pt` | Portuguese |
| `hi` | Hindi | `ja` | Japanese |
| `zh` | Chinese | `ko` | Korean |
| `ru` | Russian | `it` | Italian |
| `te` | Telugu | `ta` | Tamil |
| `nl` | Dutch | `pl` | Polish |
| `tr` | Turkish | `vi` | Vietnamese |
| `th` | Thai | | |

The UI language is auto-detected from the browser's `navigator.language` setting and can be changed via the language selector in the header.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web UI |
| `/health` | GET | Health check |
| `/info` | GET | Server information |
| `/status` | GET | Detailed status |
| `/docs` | GET | Interactive API docs (Swagger) |
| `/ws` | WS | Real-time chat WebSocket |
| `/chat` | POST | REST chat endpoint |
| `/agents` | GET | List all agents |
| `/models` | GET | List available LLM models |
| `/location/update` | POST | Update GPS location |
| `/location/current` | GET | Get current GPS location |
| `/i18n/languages` | GET | List supported languages |
| `/i18n/strings/{lang}` | GET | Get UI strings for a language |
| `/events/stream` | GET | SSE event stream |
| `/agents/stream` | GET | SSE agent status stream |

---

## Security Checklist

- [ ] Set `VERA_SERVER_API_KEY` to a strong random value
- [ ] Configure TLS with Let's Encrypt
- [ ] Set `VERA_SERVER_CORS_ORIGINS` to your domain only
- [ ] Keep `VERA_SERVER_ZONE_WWW_AUTH_REQUIRED=true`
- [ ] Regularly rotate API keys
- [ ] Monitor `/alerts` endpoint for anomalies
- [ ] Keep Docker images updated

---

## Monitoring

- **Health**: `GET /health` — deep health check of all subsystems
- **Metrics**: `GET /metrics` — request counts, latency, error rates
- **Alerts**: `GET /alerts` — active and resolved alert conditions
- **Network**: `GET /network/zones` — zone configuration and your IP's zone

---

## Troubleshooting

**Connection refused from mobile/extension:**
- Ensure `VERA_SERVER_HOST=0.0.0.0` in `.env`
- Check firewall allows port 443 (HTTPS) or 8000 (direct)
- Verify nginx is running: `docker compose ps`

**Authentication errors (403):**
- Set `VERA_SERVER_API_KEY` in `.env`
- Pass the key as `Authorization: Bearer <key>` header or `?api_key=<key>` query param

**WebSocket disconnects:**
- Check nginx `proxy_read_timeout` is set to at least 3600s
- Ensure `Upgrade` and `Connection` headers are forwarded by nginx

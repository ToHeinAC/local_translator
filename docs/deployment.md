# Deployment

The app runs on the server behind the nginx reverse proxy of `ai.brenk.com`, next to the
summarizer. This repo holds only the app side (`.streamlit/config.toml`, `tunnel.sh`); the
orchestrator and nginx files live in `local_app-orchestrator` and are changed there by the admin.

| Item | Value | Defined in |
|---|---|---|
| Port | 8560 | `.streamlit/config.toml` |
| Base path | `trns` (public URL `https://ai.brenk.com/trns/`, trailing slash) | `.streamlit/config.toml` |
| Entry point | `uv run streamlit run src/app/ui.py` | [IMPLEMENTATION.md](../IMPLEMENTATION.md) |
| Secrets | `.env` (`SEED_PW_*`), users in `data/users.json` | [.env.example](../.env.example) |

`tests/test_deployment.py` keeps the two snippets below consistent with the Streamlit config.

## 1. Orchestrator registry

Append to `apps.toml` in `local_app-orchestrator`:

```toml
[[apps]]
name = "KI-Übersetzer"
hint = "Lokale KI-Übersetzung von Dokumenten mit Fachglossar"
icon = "🌐"
port = 8560
url  = "https://ai.brenk.com/trns/"
```

The trailing slash matters: it makes Streamlit's relative asset links resolve inside the app's
own path. The orchestrator's `load_apps` accepts this entry.

## 2. nginx

Add to the `server` block in `deploy/ai.brenk.com.conf`, after the `/smrz/` pair:

```nginx
    # --- KI-Übersetzer — baseUrlPath = "trns" ---
    location = /trns { return 308 /trns/; }
    location /trns/ {
        proxy_pass http://172.16.4.112:8560;   # no trailing slash: keep the /trns/ prefix
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade           $http_upgrade;
        proxy_set_header Connection        $connection_upgrade;
        proxy_read_timeout 1000;
        proxy_send_timeout 1000;
    }
```

Then `nginx -t && systemctl reload nginx`. `proxy_read_timeout 1000` covers long jobs because the
progress fragment polls every second, which keeps the WebSocket busy.

## 3. Start, stop, tunnel

- Start on the server: `uv run streamlit run src/app/ui.py --server.headless true`.
- `./tunnel.sh` starts the app if port 8560 is free and opens a Cloudflare quick tunnel (copied
  from the summarizer; it writes the public URL, including `/trns/`, to
  `/tmp/translator-app-url.txt`). `./tunnel.sh stop` stops both. It needs GNU `grep` (`-P`) and
  `setsid`, so it is meant for the Linux server, not macOS.
- "App beenden" in the sidebar (admins only) sends SIGTERM to the app. There is no automatic
  restart; the landing page then shows the app as stopped.

## 4. Smoke test

1. `curl -s -o /dev/null -w '%{http_code}\n' https://ai.brenk.com/trns/_stcore/health` prints 200.
2. The landing page shows "KI-Übersetzer" as running; Open leads to the login.
3. After a restart of the app, the card turns green within one page reload.

## 5. Acceptance run (manual, needs the user's files)

Put a real DE→EN DOCX (5–15 pages, tables, header) and a real glossary in `data/acceptance/`
(gitignored). Translate with `gemma4:e4b` and check layout, structure, terms and readability by
hand. Record the outcome in the phase table of [IMPLEMENTATION.md](../IMPLEMENTATION.md).

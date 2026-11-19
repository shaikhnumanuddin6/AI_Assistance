# AI Assistance

A browser-based assistant using the Ollama model already installed on the backend PC. The Streamlit UI sends chats to a token-protected FastAPI service, which calls the local Ollama API. The Ollama port is never exposed to Bilal's computer.

## Architecture

```text
Browser → Streamlit (local to each user) → FastAPI (owner's PC)
        → Ollama at http://localhost:11434 → qwen2.5:3b
```

For remote access, Streamlit runs on Bilal's computer and reaches the FastAPI port over the private Tailscale network. Ollama remains bound to the owner's computer. The backend stores no conversations; each Streamlit browser session keeps its own chat history in memory, and that history is lost when the session ends.

## Project structure

```text
AI_development_pro/
├── backend/
│   ├── __init__.py
│   ├── main.py              # Authenticated FastAPI endpoints
│   └── run.py               # Starts the backend using .env host/port
├── data/
│   └── sample.txt
├── frontend/
│   ├── __init__.py
│   ├── api_client.py        # HTTP client and backend URL validation
│   └── app.py               # Streamlit chat interface
├── src/
│   ├── __init__.py
│   └── ai_service.py        # Ollama integration and error handling
├── tests/
│   ├── test_api.py
│   └── test_app.py
├── .env.example
├── .gitignore
├── app.py                   # Existing terminal CLI
├── README.md
└── requirements.txt
```

## Prerequisites

- Windows 11 and Python 3.10 or later (use the same Python installation for the venv and Streamlit).
- Ollama installed on the computer that hosts the backend.
- `qwen2.5:3b` available in Ollama. The existing embedding model is not needed by this chat app.
- Tailscale installed on both computers only if Bilal will connect remotely.

## Ollama setup

Check Ollama and the existing model from PowerShell:

```powershell
ollama --version
ollama list
```

If `qwen2.5:3b` is already listed, do not download it again. Only if it is missing, install that model:

```powershell
ollama pull qwen2.5:3b
```

Keep Ollama on its default local API address, `http://localhost:11434`. Do not bind it to a public or network interface, create a router port-forward, or allow inbound access to port 11434.

## Install and configure (backend owner)

Open PowerShell in the project folder:

```powershell
Set-Location D:\automation_ai\AI_development_pro
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Generate a unique API token locally and write it into `.env` without displaying it:

```powershell
$token = (& .\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
$content = [System.IO.File]::ReadAllText((Resolve-Path .env))
$content = [regex]::Replace($content, '(?m)^API_AUTH_TOKEN=.*$', "API_AUTH_TOKEN=$token")
Set-Content -Path .env -Value $content -NoNewline -Encoding utf8
Remove-Variable token, content
```

The `.env` file is ignored by Git. Keep it private. Do not paste the token into chat, commit it, or put it in a shared project file. The API starts with protected endpoints disabled if no token is configured.

For local-only use, leave `BACKEND_HOST=127.0.0.1` and `BACKEND_URL=http://127.0.0.1:8000`. Configure Ollama variables in `.env` only if you need to change the defaults:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=180
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
BACKEND_URL=http://127.0.0.1:8000
API_AUTH_TOKEN=<your-private-random-token>
```

Do not actually put angle brackets around the token. `.env.example` contains no real credentials.

## Start the backend and frontend

In the backend owner's PowerShell window:

```powershell
Set-Location D:\automation_ai\AI_development_pro
.\venv\Scripts\Activate.ps1
python -m backend.run
```

The local health check is `http://127.0.0.1:8000/health`. It reports backend liveness only; it deliberately does not reveal the model or claim Ollama is available. Authenticated endpoints are `GET /models` and `POST /chat`.

In a second PowerShell window on the computer where you want to use the GUI:

```powershell
Set-Location D:\automation_ai\AI_development_pro
.\venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

Streamlit opens the browser, normally at `http://localhost:8501`. The sidebar shows backend status and the configured model. It also lets you override the backend URL for the current browser session; set `BACKEND_URL` in `.env` to save a default. The API token is read from `.env` and is never displayed in the UI. Messages and Markdown/code responses render in the chat interface. The root `app.py` terminal client remains available with `python app.py`.

## Connect Bilal's computer with Tailscale

Tailscale creates an encrypted private network between approved devices. Do not use a public tunnel, Tailscale Funnel, router port-forwarding, or expose Ollama.

### 1. Install and sign in on both computers

Install Tailscale from [tailscale.com/download](https://tailscale.com/download) on the owner's PC and Bilal's PC. Sign both devices into the same tailnet (or configure an explicit tailnet sharing/ACL policy that permits Bilal's device to reach this API). Confirm both machines show as connected in the Tailscale admin console.

On the owner's PC, find its Tailscale IPv4 address:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -like '*Tailscale*' } |
    Select-Object InterfaceAlias, IPAddress
```

Use the address shown for the Tailscale interface (usually in `100.64.0.0/10`). On Bilal's PC, run the same command to find his Tailscale IP if you want to restrict the firewall to only his device.

### 2. Bind the backend only to the owner's Tailscale address

On the owner's PC, edit `.env` and set `BACKEND_HOST` to the owner's Tailscale IP (not `0.0.0.0`), for example:

```dotenv
BACKEND_HOST=100.x.y.z
BACKEND_PORT=8000
```

Replace the example address with the actual address. Restart `python -m backend.run` after changing it. This exposes the API only on that local interface, not on all network interfaces. If the Tailscale address changes, update `.env` and restart the backend.

Optionally restrict Windows Firewall to Bilal's Tailscale IP. Run PowerShell as Administrator and substitute his actual IP:

```powershell
$bilalTailscaleIP = '100.x.y.z'
New-NetFirewallRule `
    -DisplayName 'AI Assistance API from Bilal over Tailscale' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 `
    -RemoteAddress $bilalTailscaleIP -Profile Any
```

Do not add a firewall rule for port 11434. Ensure your tailnet access policy permits TCP port 8000 between these devices.

### 3. Run the owner's backend

Keep the owner's PC awake, connected to Tailscale, with Ollama and the backend running. It is the only computer generating answers. GitHub shares the source code, not the owner's locally installed Ollama model.

### 4. Set up Bilal's frontend

Bilal clones/pulls the project and creates an independent environment:

```powershell
git clone https://github.com/shaikhnumanuddin6/AI_Assistance.git
Set-Location AI_Assistance
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Bilal should set `BACKEND_URL` in his local `.env` to the owner's Tailscale address and port:

```dotenv
BACKEND_URL=http://100.x.y.z:8000
API_AUTH_TOKEN=
```

Replace `100.x.y.z` with the owner's actual Tailscale IP. Provide Bilal the same API token through a trusted password manager or another secure, private channel; he must put it in his own ignored `.env` as `API_AUTH_TOKEN=...`. Never send the token in source code, a public issue, or a GitHub commit. The token grants access to the model endpoint, so rotate it if it is exposed.

Then Bilal starts only the frontend on his own PC:

```powershell
streamlit run frontend/app.py
```

He opens the local Streamlit page in his browser. His browser's Streamlit server sends requests over Tailscale to the owner's FastAPI service. He does not install or download a model, and does not run Ollama. The owner and Bilal have separate browser sessions and conversation histories.

## API authentication and endpoints

- `GET /health`: unauthenticated liveness check only.
- `GET /models`: requires `Authorization: Bearer <API_AUTH_TOKEN>`.
- `POST /chat`: requires the same bearer token and accepts a bounded list of `user`/`assistant` messages. The latest message must be from the user.

Do not put the API token in a URL or query parameter. Keep API port 8000 accessible only on the owner's Tailscale interface and through the tailnet's access policy/firewall. Ollama port 11434 remains local to the backend PC.

## Run automated tests

From the project directory with the venv activated:

```powershell
python -m pytest -q
```

The tests mock Ollama and backend HTTP calls; they do not generate model responses or download a model.

## Troubleshooting

- **Backend says authentication is not configured:** check that `.env` exists beside `README.md` and contains a non-empty `API_AUTH_TOKEN`; restart the backend.
- **Invalid API token:** confirm both machines use the same token. Keep it out of Git and rotate it if shared insecurely.
- **Backend connection refused locally:** start `python -m backend.run`; check that `BACKEND_HOST` and `BACKEND_PORT` match `BACKEND_URL`.
- **Bilal cannot reach the backend:** confirm both Tailscale devices are connected to the expected tailnet, the owner's backend is running, `BACKEND_HOST` is the owner's current Tailscale IP, Bilal's `BACKEND_URL` uses that IP and port 8000, and the tailnet ACL/Windows Firewall permits the connection.
- **Ollama connection error:** on the backend PC run `ollama list` and verify `OLLAMA_BASE_URL=http://localhost:11434`. Do not change Ollama to listen publicly to solve a network issue.
- **Model not found:** run `ollama list`; if the configured model is absent, pull only that configured model with `ollama pull qwen2.5:3b`.
- **Slow model response:** increase `OLLAMA_TIMEOUT_SECONDS` in `.env` and restart the backend; large prompts can take longer on local hardware.
- **Port already in use:** choose an unused `BACKEND_PORT` in `.env` and update `BACKEND_URL`, firewall rules, and Bilal's URL to match.

## Git changes

No changes are pushed automatically. Review the working tree before committing, and never stage `.env`.
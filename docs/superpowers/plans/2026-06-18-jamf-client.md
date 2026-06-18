# jamf_client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the shared Jamf API layer (auth + HTTP helpers) from duplicated per-project copies into a single installable local package.

**Architecture:** Single flat package — one `__init__.py` containing all exported functions and the `JAMF_URL` constant. Installed as a local editable package via `pip install -e`. Consuming scripts replace their local `jamf_credential.py` and HTTP helper copies with `from jamf_client import ...`.

**Tech Stack:** Python 3.11+, `requests`, `python-dotenv`, `urllib3`, `truststore` (optional), `hatchling` (build backend)

## Global Constraints

- No unit tests — functions are thin wrappers over `requests` and env vars; mock-based tests add noise without value
- Stateless functions only — no client class
- Scope: `get_token`, `invalidate_token`, `check_token_expiration`, `make_session`, `jamf_get`, `jamf_patch`, `JAMF_URL` — nothing else
- `.env` lives in each consuming script's directory, not in this package
- `truststore` is a soft dependency — imported only if installed, never required

---

### Task 1: Rename directory and scaffold package

**Files:**
- Rename: `~/Scripts/jamf_master` → `~/Scripts/jamf_client`
- Create: `~/Scripts/jamf_client/pyproject.toml`
- Create: `~/Scripts/jamf_client/.env.example`
- Create: `~/Scripts/jamf_client/jamf_client/__init__.py` (empty)

**Interfaces:**
- Produces: installable package skeleton; `from jamf_client import` resolves after Task 2

- [ ] **Step 1: Rename the directory**

```bash
mv ~/Scripts/jamf_master ~/Scripts/jamf_client
cd ~/Scripts/jamf_client
```

- [ ] **Step 2: Create the inner package directory**

```bash
mkdir jamf_client
touch jamf_client/__init__.py
```

- [ ] **Step 3: Write `pyproject.toml`**

Create `~/Scripts/jamf_client/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "jamf_client"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "requests",
    "python-dotenv",
    "urllib3",
    "truststore",
]
```

- [ ] **Step 4: Write `.env.example`**

Create `~/Scripts/jamf_client/.env.example`:

```
CLIENT_ID=
CLIENT_SECRET=
JAMF_URL=https://yourinstance.jamfcloud.com
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example jamf_client/__init__.py
git commit -m "feat: scaffold jamf_client package"
```

---

### Task 2: Implement all functions and verify install

**Files:**
- Modify: `~/Scripts/jamf_client/jamf_client/__init__.py`

**Interfaces:**
- Consumes: `pyproject.toml` from Task 1
- Produces:
  - `JAMF_URL: str`
  - `get_token() -> tuple[str, int]` — returns `(access_token, expires_in)`
  - `invalidate_token(token: str) -> None`
  - `check_token_expiration(access_token: str, token_expiration_epoch: int) -> tuple[str, int]`
  - `make_session() -> requests.Session`
  - `jamf_get(endpoint: str, token: dict, session: requests.Session) -> requests.Response`
  - `jamf_patch(payload: dict, endpoint: str, token: dict, session: requests.Session) -> requests.Response`
  - `token` dict shape: `{"t": str, "expiration": int}` where `expiration` is a Unix epoch timestamp

- [ ] **Step 1: Write `jamf_client/__init__.py`**

```python
from dotenv import load_dotenv
import os
import requests
import sys
import time
import urllib3

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
JAMF_URL = os.getenv("JAMF_URL")

_missing = [
    name for name, val in [
        ("CLIENT_ID", CLIENT_ID),
        ("CLIENT_SECRET", CLIENT_SECRET),
        ("JAMF_URL", JAMF_URL),
    ]
    if not val
]
if _missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(_missing)}\n"
        f"Check that a .env file exists in the calling script's directory."
    )

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


def get_token():
    url = f"{JAMF_URL}/api/oauth/token"
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "client_credentials",
        "client_secret": CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=data, headers=headers)
    response.raise_for_status()
    token_data = response.json()
    return token_data["access_token"], token_data["expires_in"]


def invalidate_token(token):
    url = f"{JAMF_URL}/api/v1/auth/invalidate-token"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Warning: Failed to invalidate token: {e}", file=sys.stderr)


def check_token_expiration(access_token, token_expiration_epoch):
    current_epoch = int(time.time())
    if current_epoch > token_expiration_epoch - 15:
        access_token, expires_in = get_token()
        token_expiration_epoch = current_epoch + expires_in
    return access_token, token_expiration_epoch


def make_session():
    session = requests.Session()
    retry = urllib3.util.retry.Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "PATCH"],
        raise_on_status=False,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def jamf_get(endpoint, token, session):
    token["t"], token["expiration"] = check_token_expiration(token["t"], token["expiration"])
    url = f"{JAMF_URL}{endpoint}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token['t']}",
    }
    return session.get(url, headers=headers)


def jamf_patch(payload, endpoint, token, session):
    token["t"], token["expiration"] = check_token_expiration(token["t"], token["expiration"])
    url = f"{JAMF_URL}{endpoint}"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token['t']}",
    }
    return session.patch(url, json=payload, headers=headers)
```

- [ ] **Step 2: Install the package as editable**

Run from `~/Scripts/jamf_client/`:

```bash
pip install -e .
```

Expected output contains: `Successfully installed jamf-client-0.1.0`

- [ ] **Step 3: Smoke-test the import**

Run from any directory that has a `.env` with `CLIENT_ID`, `CLIENT_SECRET`, and `JAMF_URL` set:

```bash
python -c "
from jamf_client import (
    get_token, invalidate_token, check_token_expiration,
    make_session, jamf_get, jamf_patch, JAMF_URL
)
print('JAMF_URL:', JAMF_URL)
print('All imports OK')
"
```

Expected output:
```
JAMF_URL: https://yourinstance.jamfcloud.com
All imports OK
```

If run from a directory without a `.env`, expect:
```
EnvironmentError: Missing required environment variables: CLIENT_ID, CLIENT_SECRET, JAMF_URL
```

- [ ] **Step 4: Commit**

```bash
git add jamf_client/__init__.py
git commit -m "feat: implement jamf_client auth and HTTP helpers"
```

---

## Migration Checklist (per consuming script)

Once `jamf_client` is installed, update each existing script:

- [ ] Run `pip install -e ~/Scripts/jamf_client` in the script's venv
- [ ] Replace `from jamf_credential import JAMF_URL, get_token, invalidate_token, check_token_expiration` with `from jamf_client import JAMF_URL, get_token, invalidate_token, check_token_expiration`
- [ ] If the script has a local `make_session` / `jamf_get` / `jamf_patch`: add them to the import line above and delete the local definitions
- [ ] Delete the local `jamf_credential.py`
- [ ] Run the script to confirm it works
- [ ] Commit

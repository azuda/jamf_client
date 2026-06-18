# jamf_client — Design Spec

**Date:** 2026-06-18
**Status:** Approved

## Problem

Auth logic and HTTP helpers (`jamf_credential.py`, `make_session`, `jamf_get`, `jamf_patch`) are copy-pasted across every Jamf script project (`jamf_laps`, `jamf_purchasing_import`, `jamf_ipad_names`, `jamf_site_fix`, `rundle_jamf_report`, `jamf_api_template`). Changes must be manually propagated to each copy.

## Goal

Extract the shared Jamf API layer into a single installable local package (`jamf_client`) so all scripts import from one source of truth.

## Out of Scope

- POST, DELETE, or pagination helpers
- A CLI interface
- Stateful client class
- Tests (functions are thin wrappers; no meaningful logic to unit-test)

---

## Structure

```
jamf_client/           ← rename of jamf_master/
  jamf_client/
    __init__.py        ← all exported functions and JAMF_URL
  pyproject.toml
  .env.example
```

The consuming scripts each run `pip install -e ~/Scripts/jamf_client` once. The `.env` file continues to live in each script's own directory.

---

## API

All symbols live in `jamf_client/__init__.py` and are importable as `from jamf_client import ...`.

### Auth

| Function | Signature | Notes |
|---|---|---|
| `get_token` | `() → (str, int)` | Returns `(access_token, expires_in)` |
| `invalidate_token` | `(token: str) → None` | Silently logs on failure |
| `check_token_expiration` | `(access_token: str, expiry: int) → (str, int)` | Renews if expiry within 15s |

### HTTP

| Function | Signature | Notes |
|---|---|---|
| `make_session` | `() → requests.Session` | Retry on 429/500/502/503/504, 3 attempts, 0.5s backoff |
| `jamf_get` | `(endpoint: str, token: dict, session: Session) → Response` | Checks token expiry before request |
| `jamf_patch` | `(payload: dict, endpoint: str, token: dict, session: Session) → Response` | Checks token expiry before request |

### Constants

| Name | Type | Source |
|---|---|---|
| `JAMF_URL` | `str` | `.env` via `python-dotenv` |

The `token` dict passed to `jamf_get`/`jamf_patch` has the shape `{"t": str, "expiration": int}` where `expiration` is a Unix epoch timestamp. Scripts construct it after calling `get_token()`.

`truststore.inject_into_ssl()` is called once on import if `truststore` is installed (soft dependency).

`.env.example` documents the three required variables:
```
CLIENT_ID=
CLIENT_SECRET=
JAMF_URL=https://yourinstance.jamfcloud.com
```

---

## Dependencies

Declared in `pyproject.toml`:

- `requests`
- `python-dotenv`
- `urllib3`
- `truststore` (optional)

---

## Migration Path

For each existing script:

1. `pip install -e ~/Scripts/jamf_client` (once per venv)
2. Replace `from jamf_credential import ...` → `from jamf_client import ...`
3. Remove the local `jamf_credential.py`
4. Remove local copies of `make_session`, `jamf_get`, `jamf_patch` if present

# Converting Scripts to use `jamf_client`

## 1. Install the package

From the script's project directory (or its virtualenv):

```bash
pip install -e /path/to/Scripts/jamf_client
# or with truststore for macOS system cert support:
pip install -e "/path/to/Scripts/jamf_client[truststore]"
```

## 2. Set up `.env`

`jamf_client` loads env vars via `python-dotenv`. The variable names it expects:

```
CLIENT_ID=
CLIENT_SECRET=
JAMF_URL=https://yourinstance.jamfcloud.com
```

> **Note:** `assetsonar_master` uses `JAMF_CLIENT_ID` / `JAMF_CLIENT_SECRET` — rename those vars in `.env` to `CLIENT_ID` / `CLIENT_SECRET`.

## 3. Delete the local `jamf_credential.py`

Each script directory has its own copy of auth boilerplate. Once you've installed the package, delete it:

```bash
rm run_lookup/jamf_credential.py
rm rundle_jamf_report/jamf_credential.py
rm assetsonar_master/jamf_credential.py
```

## 4. Update imports

**Before:**
```python
from jamf_credential import JAMF_URL, get_token, invalidate_token, check_token_expiration
import requests
import urllib3
```

**After:**
```python
from jamf_client import JAMF_URL, get_token, invalidate_token, make_session, jamf_get, jamf_patch
import time
```

## 5. Change token handling

Old scripts pass `access_token` and `token_expiration_epoch` as separate variables that get threaded through every function call. `jamf_client` uses a single mutable dict instead — `jamf_get` / `jamf_patch` update it in-place.

**Before:**
```python
access_token, expires_in = get_token()
token_expiration_epoch = int(time.time()) + expires_in

# every call returns updated token state
response, access_token, token_expiration_epoch = get(endpoint, access_token, token_expiration_epoch)
```

**After:**
```python
access_token, expires_in = get_token()
token = {"t": access_token, "expiration": int(time.time()) + expires_in}
session = make_session()

# token dict is updated in-place; no return values to unpack
response = jamf_get(endpoint, token, session)
```

Then at the end:
```python
invalidate_token(token["t"])
```

## 6. Replace inline `get()` / `requests.get()` wrappers

Old scripts define a local `get()` that manually sets auth headers and calls `check_token_expiration`. Replace the whole function and its callers with `jamf_get`.

**Before:**
```python
def get(endpoint, access_token, token_expiration_epoch, session):
    access_token, token_expiration_epoch = check_token_expiration(access_token, token_expiration_epoch)
    url = f"{JAMF_URL}{endpoint}"
    headers = {"accept": "application/json", "authorization": f"Bearer {access_token}"}
    response = session.get(url, headers=headers)
    return response, access_token, token_expiration_epoch

response, access_token, token_expiration_epoch = get("/api/v1/users", access_token, token_expiration_epoch, session)
```

**After:**
```python
response = jamf_get("/api/v1/users", token, session)
```

For PATCH requests, replace `requests.patch(...)` / `session.patch(...)` with `jamf_patch(payload, endpoint, token, session)`.

## 7. Drop `verify=False`

`rundle_jamf_report` and `assetsonar_master` pass `verify=False` to suppress SSL warnings. The `jamf_client` package uses `truststore` (if installed) to inject macOS system certificates instead. Remove `verify=False` from any remaining `requests` calls and remove `urllib3.disable_warnings(...)` from the bottom of scripts.

## 8. Remove duplicate `make_session()`

Old scripts define their own `make_session()` with retry logic. Delete the local definition and use the one from `jamf_client`.

---

## Complete before/after example

**Before (`run_lookup/query.py` pattern):**
```python
from jamf_credential import JAMF_URL, check_token_expiration, get_token, invalidate_token
import requests, time, urllib3
import truststore
truststore.inject_into_ssl()

def make_session(): ...  # local copy

def get(endpoint, access_token, token_expiration_epoch, session):
    access_token, token_expiration_epoch = check_token_expiration(access_token, token_expiration_epoch)
    url = f"{JAMF_URL}{endpoint}"
    headers = {"accept": "application/json", "authorization": f"Bearer {access_token}"}
    response = session.get(url, headers=headers)
    return response, access_token, token_expiration_epoch

def main():
    access_token, expires_in = get_token()
    token_expiration_epoch = int(time.time()) + expires_in
    session = make_session()
    try:
        response, access_token, token_expiration_epoch = get("/api/v1/users?page=0&page-size=1000", access_token, token_expiration_epoch, session)
        data = response.json()
    finally:
        invalidate_token(access_token)
```

**After:**
```python
from jamf_client import get_token, invalidate_token, make_session, jamf_get
import time

def main():
    access_token, expires_in = get_token()
    token = {"t": access_token, "expiration": int(time.time()) + expires_in}
    session = make_session()
    try:
        response = jamf_get("/api/v1/users?page=0&page-size=1000", token, session)
        data = response.json()
    finally:
        invalidate_token(token["t"])
```

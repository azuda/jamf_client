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

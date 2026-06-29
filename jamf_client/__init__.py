from contextlib import contextmanager
from dataclasses import dataclass
from dotenv import load_dotenv
import os
import requests
import sys
import time
import urllib3

_CLIENT_ID = None
_CLIENT_SECRET = None
_JAMF_URL = None
_auth_session = None

__all__ = [
    "Token",
    "init",
    "get_token",
    "invalidate_token",
    "make_session",
    "jamf_session",
    "jamf_get",
    "jamf_patch",
]


@dataclass
class Token:
    access_token: str
    expiration: int  # unix epoch

    @classmethod
    def fetch(cls) -> "Token":
        access_token, expires_in = get_token()
        return cls(access_token=access_token, expiration=int(time.time()) + expires_in)


def init():
    global _CLIENT_ID, _CLIENT_SECRET, _JAMF_URL
    load_dotenv()
    _CLIENT_ID = os.getenv("CLIENT_ID")
    _CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    _JAMF_URL = os.getenv("JAMF_URL")

    missing = [
        name for name, val in [
            ("CLIENT_ID", _CLIENT_ID),
            ("CLIENT_SECRET", _CLIENT_SECRET),
            ("JAMF_URL", _JAMF_URL),
        ]
        if not val
    ]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Check that a .env file exists in the calling script's directory."
        )

    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass


def _get_auth_session():
    global _auth_session
    if _auth_session is None:
        _auth_session = make_session()
    return _auth_session


def get_token():
    url = f"{_JAMF_URL}/api/oauth/token"
    data = {
        "client_id": _CLIENT_ID,
        "grant_type": "client_credentials",
        "client_secret": _CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = _get_auth_session().post(url, data=data, headers=headers)
    response.raise_for_status()
    token_data = response.json()
    return token_data["access_token"], token_data["expires_in"]


def invalidate_token(token: str):
    url = f"{_JAMF_URL}/api/v1/auth/invalidate-token"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = _get_auth_session().post(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Warning: Failed to invalidate token: {e}", file=sys.stderr)


def _refresh_token_if_needed(token: "Token"):
    if int(time.time()) > token.expiration - 15:
        token.access_token, expires_in = get_token()
        token.expiration = int(time.time()) + expires_in


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
    session.mount("http://", adapter)
    return session


@contextmanager
def jamf_session():
    """Context manager yielding a ready-to-use (token, session) pair.

    Invalidates the token and closes the session on exit.

    Usage::

        with jamf_session() as (token, session):
            response = jamf_get("/api/v1/computers", token, session)
    """
    token = Token.fetch()
    session = make_session()
    try:
        yield token, session
    finally:
        invalidate_token(token.access_token)
        session.close()


def jamf_get(endpoint, token: "Token", session, *, raise_for_status=True):
    _refresh_token_if_needed(token)
    url = f"{_JAMF_URL}{endpoint}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token.access_token}",
    }
    response = session.get(url, headers=headers)
    if raise_for_status:
        response.raise_for_status()
    return response


def jamf_patch(payload, endpoint, token: "Token", session, *, raise_for_status=True):
    _refresh_token_if_needed(token)
    url = f"{_JAMF_URL}{endpoint}"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token.access_token}",
    }
    response = session.patch(url, json=payload, headers=headers)
    if raise_for_status:
        response.raise_for_status()
    return response

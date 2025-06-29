from argparse import ArgumentParser
import os
import sys
import json
import base64
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
from requests.utils import requote_uri

SECRETS_PATH = os.path.expanduser("~/.config/fitbit/.secrets")
SCOPES_PATH = os.path.expanduser("~/.config/fitbit/.scopes")
REQUIRED_KEYS = ["CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI"]

def load_secrets():
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    secrets = {}
    if os.path.isfile(SECRETS_PATH):
        with open(SECRETS_PATH) as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    secrets[key] = value
    missing = False
    for key in REQUIRED_KEYS:
        if not secrets.get(key):
            secrets[key] = input(f"{key.replace('_', ' ').title()}: ").strip()
            missing = True
    if missing:
        with open(SECRETS_PATH, 'w') as f:
            for key in REQUIRED_KEYS:
                f.write(f"{key}={secrets[key]}\n")
    return secrets['CLIENT_ID'], secrets['CLIENT_SECRET'], secrets['REDIRECT_URI']

def load_scopes():
    os.makedirs(os.path.dirname(SCOPES_PATH), exist_ok=True)
    scopes = []
    if os.path.isfile(SCOPES_PATH):
        with open(SCOPES_PATH) as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith('#'):
                    scopes.append(s)
    if not scopes:
        print("Scopes config not found — let's set it up.")
        while True:
            s = input("Enter a scope (blank to finish): ").strip()
            if not s:
                break
            if not s.startswith('#'):
                scopes.append(s)
        with open(SCOPES_PATH, 'w') as f:
            for sc in scopes:
                f.write(sc + "\n")
    return scopes

def main():
    parser = ArgumentParser(description='Fetch Fitbit OAuth2 token')
    parser.add_argument('code', nargs='?', help='Authorization code')
    args = parser.parse_args()

    client_id, client_secret, redirect_uri = load_secrets()
    code = args.code
    if not code:
        scopes_list = load_scopes()
        scope_param = requote_uri(' '.join(scopes_list))
        auth_url = (
            f"https://www.fitbit.com/oauth2/authorize"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={requote_uri(redirect_uri)}"
            f"&scope={scope_param}"
        )
        print(f"Open this URL in your browser and complete login:\n{auth_url}")
        webbrowser.open(auth_url)
        redirect_url = input('After approval, paste the full redirect URL: ').strip()
        code = parse_qs(urlparse(redirect_url).query).get('code', [None])[0]
        if not code:
            print('Failed to extract authorization code')
            sys.exit(1)

    credentials = f"{client_id}:{client_secret}"
    token_resp = requests.post(
        'https://api.fitbit.com/oauth2/token',
        headers={
            'Authorization': f"Basic {base64.b64encode(credentials.encode()).decode()}",
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data={
            'client_id': client_id,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'code': code
        }
    )
    if token_resp.status_code != 200:
        print(f"Error fetching token: {token_resp.status_code}\n{token_resp.text}")
        sys.exit(1)

    try:
        data = token_resp.json()
    except json.JSONDecodeError:
        print('Received non-JSON response:')
        print(token_resp.text)
        sys.exit(1)

    for key, value in data.items():
        print(key)
        print(value)
        print()

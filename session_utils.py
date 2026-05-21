import os
import json
import secrets

SESSIONS_FILE = "data/sessions.json"

def _load_sessions():
    if os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE) as f:
            return json.load(f)
    return {}

def _save_sessions(sessions):
    os.makedirs("data", exist_ok=True)
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f)

def create_session(email):
    token = secrets.token_urlsafe(32)
    sessions = _load_sessions()
    sessions[token] = email
    _save_sessions(sessions)
    return token

def get_session(token):
    return _load_sessions().get(token)

def delete_session(token):
    sessions = _load_sessions()
    sessions.pop(token, None)
    _save_sessions(sessions)

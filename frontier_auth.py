"""
Frontier OAuth2 Auth Server

Handles the OAuth2 callback from Frontier's authorization flow.
Exchanges authorization code for access + refresh tokens.

Usage:
  python frontier_auth.py --client-id CLIENT_ID [--port 18080]

Environment:
  FRONTIER_CLIENT_ID — your Frontier app client ID
  FRONTIER_CLIENT_SECRET — your Frontier app shared key
  FRONTIER_REDIRECT_URI — must match what's registered in Frontier developer console
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from typing import Any

AUTH_API = "https://auth.frontierstore.net"
SCOPE = "auth capi"
AUDIENCE = "frontier"

CLIENT_ID = os.environ.get("FRONTIER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("FRONTIER_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get(
    "FRONTIER_REDIRECT_URI",
    "http://localhost:18080/callback",
)
PORT = int(os.environ.get("PORT", "18080"))


def generate_pkce() -> tuple[str, str, str]:
    """Generate PKCE code verifier, challenge, and state."""
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(32)
    return verifier, challenge, state


def build_auth_url(challenge: str, state: str) -> str:
    """Build the Frontier OAuth2 authorization URL."""
    params = urllib.parse.urlencode({
        "audience": AUDIENCE,
        "scope": SCOPE,
        "response_type": "code",
        "client_id": CLIENT_ID,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "redirect_uri": REDIRECT_URI,
    })
    return f"{AUTH_API}/auth?{params}"


def exchange_code(code: str, verifier: str) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    data = urllib.parse.urlencode({
        "redirect_uri": REDIRECT_URI,
        "code": code,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
        "client_id": CLIENT_ID,
    }).encode()

    req = urllib.request.Request(
        f"{AUTH_API}/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def save_tokens(tokens: dict[str, Any]) -> None:
    """Save tokens to .env file."""
    env_path = os.environ.get("ENV_PATH", "/opt/data/profiles/elite/.env")

    # Read existing .env
    env_content = ""
    if os.path.exists(env_path):
        with open(env_path) as f:
            env_content = f.read()

    # Update or add FRONTIER_TOKEN
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    token_type = tokens.get("token_type", "Bearer")
    expires_in = tokens.get("expires_in", "")

    lines = env_content.splitlines(keepends=True)
    updated = {"FRONTIER_TOKEN": False, "FRONTIER_REFRESH_TOKEN": False,
               "FRONTIER_TOKEN_TYPE": False, "FRONTIER_TOKEN_EXPIRES": False}

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("FRONTIER_TOKEN=") and not updated["FRONTIER_TOKEN"]:
            new_lines.append(f"FRONTIER_TOKEN={access_token}\n")
            updated["FRONTIER_TOKEN"] = True
        elif stripped.startswith("FRONTIER_REFRESH_TOKEN=") and not updated["FRONTIER_REFRESH_TOKEN"]:
            new_lines.append(f"FRONTIER_REFRESH_TOKEN={refresh_token}\n")
            updated["FRONTIER_REFRESH_TOKEN"] = True
        elif stripped.startswith("FRONTIER_TOKEN_TYPE=") and not updated["FRONTIER_TOKEN_TYPE"]:
            new_lines.append(f"FRONTIER_TOKEN_TYPE={token_type}\n")
            updated["FRONTIER_TOKEN_TYPE"] = True
        elif stripped.startswith("FRONTIER_TOKEN_EXPIRES=") and not updated["FRONTIER_TOKEN_EXPIRES"]:
            new_lines.append(f"FRONTIER_TOKEN_EXPIRES={expires_in}\n")
            updated["FRONTIER_TOKEN_EXPIRES"] = True
        else:
            new_lines.append(line)

    # Append missing vars
    if not updated["FRONTIER_TOKEN"]:
        new_lines.append(f"\n# Frontier CAPI tokens (OAuth2)\n")
        new_lines.append(f"FRONTIER_TOKEN={access_token}\n")
        new_lines.append(f"FRONTIER_REFRESH_TOKEN={refresh_token}\n")
        new_lines.append(f"FRONTIER_TOKEN_TYPE={token_type}\n")
        new_lines.append(f"FRONTIER_TOKEN_EXPIRES={expires_in}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    print(f"✅ Tokens saved to {env_path}")
    print(f"   Access token: {access_token[:40]}...")
    print(f"   Refresh token: {refresh_token[:40]}...")
    print(f"   Expires in: {expires_in}s")


def refresh_access_token() -> bool:
    """Refresh the access token using the stored refresh token.

    Silent operation — logs to stderr only (visible in docker logs).
    Returns True on success, False on failure.
    """
    env_path = os.environ.get("ENV_PATH", "/opt/data/profiles/elite/.env")
    if not os.path.exists(env_path):
        sys.stderr.write("[auth] No .env file found, skipping refresh\n")
        return False

    # Read current tokens
    tokens = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                tokens[k] = v

    refresh_token = tokens.get("FRONTIER_REFRESH_TOKEN", "")
    if not refresh_token:
        sys.stderr.write("[auth] No refresh token found, skipping refresh\n")
        return False

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    }).encode()

    req = urllib.request.Request(
        f"{AUTH_API}/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            new_tokens = json.loads(resp.read())
        save_tokens(new_tokens)
        sys.stderr.write(
            f"[auth] Token refreshed silently — expires in {new_tokens.get('expires_in', '?')}s\n"
        )
        return True
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.stderr.write(f"[auth] Token refresh failed: HTTP {e.code} {body[:200]}\n")
        return False
    except Exception as e:
        sys.stderr.write(f"[auth] Token refresh error: {e}\n")
        return False


def background_refresh_loop() -> None:
    """Background thread: silently refreshes the token every 3 hours."""
    REFRESH_INTERVAL = 10800  # 3 hours (token expires in 4h, gives 1h buffer)
    while True:
        time.sleep(REFRESH_INTERVAL)
        refresh_access_token()


# ── HTTP Server ──────────────────────────────────────────────────────

PKCE_STATE: dict[str, Any] = {}


class AuthHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for OAuth2 callback."""

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)

        # Health check
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # Manual token refresh endpoint
        if parsed.path == "/refresh":
            success = refresh_access_token()
            if success:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Token refreshed.\n")
            else:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Refresh failed.\n")
            return

        # Auth URL generator page
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            auth_url = build_auth_url(
                PKCE_STATE["challenge"],
                PKCE_STATE["state"],
            )
            self.wfile.write(f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:2em">
<h1>🛸 Frontier OAuth2 Auth Server</h1>
<p>Client ID: <code>{CLIENT_ID}</code></p>
<p>Redirect URI: <code>{REDIRECT_URI}</code></p>
<p><a href="{auth_url}" style="display:inline-block;padding:1em 2em;background:#4a90d9;color:white;text-decoration:none;border-radius:6px;font-size:1.2em">
  🔗 Click here to authorize</a></p>
<hr>
<p>After authorizing, you'll be redirected back here and the tokens will be saved.</p>
</body></html>""".encode())
            return

        # OAuth2 callback
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                self._respond_error(f"Authorization error: {error}")
                return

            if not code:
                self._respond_error("No authorization code received")
                return

            if state != PKCE_STATE.get("state"):
                self._respond_error("State mismatch — possible CSRF attack")
                return

            try:
                tokens = exchange_code(code, PKCE_STATE["verifier"])
                save_tokens(tokens)

                # Also test the token with CAPI profile endpoint
                access = tokens.get("access_token", "")
                self._respond_success(tokens)

            except Exception as e:
                self._respond_error(f"Token exchange failed: {e}")
            return

        self.send_error(404)

    def _respond_success(self, tokens: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:2em">
<h1>✅ Authorization Successful!</h1>
<p>Access token obtained. You can close this window.</p>
<pre style="background:#f5f5f5;padding:1em;border-radius:4px;font-size:0.9em">
access_token:  {tokens.get('access_token','')[:50]}...
refresh_token: {tokens.get('refresh_token','')[:50]}...
expires_in:    {tokens.get('expires_in','')}s
token_type:    {tokens.get('token_type','')}
</pre>
<p>The tokens have been saved to the .env file.</p>
</body></html>""".encode())

    def _respond_error(self, message: str) -> None:
        self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:2em">
<h1>❌ Error</h1>
<p>{message}</p>
</body></html>""".encode())

    def log_message(self, format, *args):
        sys.stderr.write(f"[auth] {format % args}\n")


def main() -> None:
    global CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, PORT

    # CLI args override env
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--client-id" and i + 1 < len(args):
            CLIENT_ID = args[i + 1]
        elif arg == "--client-secret" and i + 1 < len(args):
            CLIENT_SECRET = args[i + 1]
        elif arg == "--redirect-uri" and i + 1 < len(args):
            REDIRECT_URI = args[i + 1]
        elif arg == "--port" and i + 1 < len(args):
            PORT = int(args[i + 1])

    if not CLIENT_ID:
        print("ERROR: FRONTIER_CLIENT_ID not set. Provide via env or --client-id")
        sys.exit(1)

    # Generate PKCE values
    verifier, challenge, state = generate_pkce()
    PKCE_STATE["verifier"] = verifier
    PKCE_STATE["challenge"] = challenge
    PKCE_STATE["state"] = state

    auth_url = build_auth_url(challenge, state)

    # Start background token refresh thread (silent, daemon)
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()
    sys.stderr.write("[auth] Background token refresh thread started (every 3h)\n")

    # Do an initial refresh if tokens already exist
    env_path = os.environ.get("ENV_PATH", "/opt/data/profiles/elite/.env")
    if os.path.exists(env_path):
        refresh_access_token()

    print("=" * 60)
    print("🛸  Frontier OAuth2 Auth Server")
    print("=" * 60)
    print(f"  Client ID:     {CLIENT_ID}")
    print(f"  Redirect URI:  {REDIRECT_URI}")
    print(f"  Port:          {PORT}")
    print()
    print(f"  Open in browser:")
    print(f"  → http://localhost:{PORT}")
    print(f"  Or use the auth URL directly:")
    print(f"  → {auth_url}")
    print()
    print("  Waiting for callback...")
    print("=" * 60)

    server = http.server.HTTPServer(("0.0.0.0", PORT), AuthHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()

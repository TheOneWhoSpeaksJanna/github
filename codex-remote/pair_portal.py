"""Private, account-authorized Codex Remote setup on a Windows GitHub runner.

Codes never go to GitHub logs or artifacts. Use Tailscale and HTTP Basic Auth.
This tool does not access or store ChatGPT account passwords or tokens.
"""
from __future__ import annotations

import argparse
import base64
import hmac
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
DEVICE_CODE = re.compile(r"[A-Za-z0-9]{4,8}(?:-[A-Za-z0-9]{4,8}){0,2}")
AUTH_URL = "https://auth.openai.com/codex/device"
STATUS_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-store">
<title>Codex Remote pairing</title>
<style>
:root{color-scheme:dark;font-family:system-ui,Arial,sans-serif}
body{margin:0;background:#0c1422;color:#ecf3ff}
main{max-width:630px;margin:auto;padding:28px 18px}
section{border:1px solid #334e67;background:#17253a;padding:20px;border-radius:16px;margin:15px 0}
h1{font-size:27px}h2{font-size:19px}
p{line-height:1.5;color:#d5deed}
code{font-size:24px;font-weight:bold;letter-spacing:2px;overflow-wrap:anywhere;display:block}
button,a.cta{cursor:pointer;background:#91d0fa;color:#07203a;padding:12px 16px;border:0;border-radius:9px;
font-size:15px;font-weight:650;display:inline-block;text-decoration:none}
button:disabled{opacity:.5}#error{color:#ffbdad}
.small{font-size:13px;color:#b8cbdf}#pair-section{display:none}
</style></head><body><main><h1>Codex Remote — GitHub VM</h1>
<p>This page works only through your private Tailscale network. Codes are never published to Actions logs.</p>
<section><h2>1. Authorize this VM</h2><p id="login-status">Checking authorization…</p>
<code id="login-code"></code><p><a id="auth-link" class="cta"
href="https://auth.openai.com/codex/device" target="_blank" rel="noopener noreferrer">Open ChatGPT sign-in page</a></p>
<p class="small">Sign in to your own ChatGPT account and enter the displayed device code. Never share your password or account token.</p></section>
<section id="pair-section"><h2>2. Pair ChatGPT on Android</h2>
<p>Open ChatGPT → Codex / Remote → Add host → Enter code manually.</p>
<code id="pair-code"></code><p id="pair-expiry" class="small"></p>
<button id="refresh" type="button">Create a fresh pairing code</button></section>
<section><h2>Status</h2><p id="state">Starting…</p><p class="small" id="model"></p>
<p id="error"></p></section>
<p class="small">The remote Codex worker runs on this temporary Windows VM. It stops when the GitHub Actions session ends. Ollama stays on 127.0.0.1; this is not a public model endpoint.</p></main>
<script>
const get=id=>document.getElementById(id);
async function update(){
 try{
  const res=await fetch("/api/status",{cache:"no-store"});
  const s=await res.json();
  get("login-status").textContent=s.authenticated?"Authorized with ChatGPT":
    s.auth_error||"Waiting for ChatGPT device authorization…";
  get("login-code").textContent=s.authenticated?"":s.device_code||"Requesting a device code…";
  get("auth-link").hidden=s.authenticated;
  get("pair-section").style.display=s.authenticated?"block":"none";
  get("pair-code").textContent=s.pair_code||"Pairing code not available yet";
  get("pair-expiry").textContent=s.expires_at?"Expires: "+s.expires_at:"Pairing codes are short-lived.";
  get("state").textContent=s.stage;
  get("model").textContent="Configured local Ollama model: "+s.model;
  get("error").textContent=s.error||"";
 }catch(e){get("error").textContent="Private VM connection unavailable."}
}
get("refresh").addEventListener("click",async()=>{
 get("refresh").disabled=true;
 try{
  const response=await fetch("/api/refresh",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
  if(!response.ok)throw new Error("Could not refresh pairing code");
 }catch(e){get("error").textContent=e.message}
 finally{get("refresh").disabled=false;update()}
});
update();setInterval(update,3500);
</script></body></html>"""


def extract_device_prompt(text: str):
    """Only select a device code after Codex's explanatory line, not random words."""
    clean = ANSI.sub("", text)
    lines = [s.strip() for s in clean.replace("\r", "\n").splitlines()]
    url = next((x for line in lines for x in re.findall(r"https://[^\s)]+", line)
                if x.rstrip(".,") == AUTH_URL), None)
    candidate = None
    for i, line in enumerate(lines):
        if "one-time code" not in line.lower() and "enter this code" not in line.lower():
            continue
        for next_line in lines[i + 1:i + 5]:
            if DEVICE_CODE.fullmatch(next_line) and (any(c.isdigit() for c in next_line) or "-" in next_line):
                candidate = next_line
                break
    return url, candidate


class Status:
    def __init__(self, model):
        self.lock = threading.RLock()
        self.data = {
            "stage": "Starting Codex authentication",
            "model": model,
            "authenticated": False, "device_code": None,
            "pair_code": None, "expires_at": None,
            "auth_error": None, "error": None,
        }
        self.codex = "codex"
        self.home = None
        self.env = None
        self.pair_lock = threading.Lock()

    def set(self, **fields):
        with self.lock:
            self.data.update(fields)

    def snapshot(self):
        with self.lock:
            return dict(self.data)

    def pair(self):
        if not self.snapshot()["authenticated"]:
            return
        if not self.pair_lock.acquire(False):
            return
        try:
            proc = subprocess.run(
                [self.codex, "remote-control", "pair", "--json"],
                env=self.env, capture_output=True, text=True, timeout=40)
            if proc.returncode != 0:
                self.set(stage="Codex Remote not paired yet",
                         error="Codex Remote enrollment is unavailable. Check ChatGPT Remote access and device permissions.")
                return
            info = json.loads(proc.stdout)
            code = info.get("manualPairingCode") or info.get("manual_pairing_code")
            if not isinstance(code, str) or not (4 <= len(code) <= 32):
                self.set(error="Codex did not return a manual pairing code.")
                return
            expiry = info.get("expiresAt") or info.get("expires_at")
            if isinstance(expiry, (int, float)):
                expiry = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(expiry))
            self.set(stage="Ready to pair from ChatGPT Android", pair_code=code,
                     expires_at=expiry, error=None)
        except (ValueError, OSError, subprocess.TimeoutExpired):
            self.set(error="Codex pairing request failed.")
        finally:
            self.pair_lock.release()


def login_and_pair(st: Status):
    """Run only after the authorized user starts this GitHub VM."""
    st.set(stage="Requesting device sign-in from official Codex CLI")
    try:
        proc = subprocess.Popen([st.codex, "login", "--device-auth"],
                                env=st.env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, encoding="utf-8",
                                errors="replace", bufsize=1,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        parts = []
        assert proc.stdout is not None
        for line in proc.stdout:
            # NEVER print the code, user account, token or auth response.
            parts.append(line[:600])
            if len(parts) > 35:
                parts.pop(0)
            url, code = extract_device_prompt("".join(parts))
            if code and not st.snapshot()["device_code"]:
                st.set(device_code=code, stage="Complete device login from Android")
            if proc.poll() is not None:
                break
        rc = proc.wait(timeout=5)
        if rc != 0:
            st.set(stage="Device authorization failed or expired",
                   auth_error="Device login was rejected. Check whether ChatGPT device-code login is enabled in Settings.",
                   error="Restart the temporary VM to request a new login code.")
            return
        # Auth is stored only in the ephemeral per-run CODEX_HOME; no repo artifacts.
        st.set(authenticated=True, device_code=None, stage="Starting remote-control relay",
               error=None)
        command = subprocess.run([st.codex, "remote-control", "start", "--json"],
                                 env=st.env, capture_output=True, text=True, timeout=120)
        if command.returncode != 0:
            st.set(stage="Remote control could not start",
                   error="The Codex remote-control daemon could not start on this VM.")
            return
        # Enrollment can take extra time; retry without disclosing daemon logs.
        for i in range(12):
            st.pair()
            if st.snapshot()["pair_code"]:
                return
            time.sleep(10)
        st.set(stage="Signed in but remote enrollment is unavailable",
               error="Remote pairing could not complete. Account access, MFA or Windows daemon support may be blocking it.")
    except (OSError, subprocess.TimeoutExpired, AssertionError):
        st.set(stage="Codex could not authenticate", error="Device-login process failed.")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, password, status):
        super().__init__(address, Handler)
        self.password, self.status = password, status


class Handler(BaseHTTPRequestHandler):
    server: Server
    def log_message(self, *args):
        # Suppress URL/IP/cookie logs in a public Github repo.
        pass

    def respond(self, status, text, mimetype="application/json", authenticate=False):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mimetype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        if authenticate:
            self.send_header("WWW-Authenticate", 'Basic realm="Private Codex Remote pairing"')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        try:
            data = base64.b64decode(auth[6:], validate=True).decode("utf-8")
            username, password = data.split(":", 1)
            return (hmac.compare_digest(username, "owner")
                    and hmac.compare_digest(password, self.server.password))
        except (ValueError, UnicodeError):
            return False

    def do_GET(self):
        if self.path == "/health":
            return self.respond(200, '{"status":"ok"}')
        if not self.authorized():
            return self.respond(401, "Authorization required", "text/plain", authenticate=True)
        if self.path == "/":
            return self.respond(200, STATUS_HTML, "text/html; charset=utf-8")
        if self.path == "/api/status":
            return self.respond(200, json.dumps(self.server.status.snapshot()))
        self.respond(404, '{"error":"Not found"}')

    def do_POST(self):
        if not self.authorized():
            return self.respond(401, "Authorization required", "text/plain", authenticate=True)
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
            return self.respond(403, '{"error":"Origin mismatch"}')
        if self.path != "/api/refresh" or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.respond(404, '{"error":"Unknown operation"}')
        if self.headers.get("Content-Length") != "2":
            return self.respond(400, '{"error":"Bad request"}')
        self.rfile.read(2)
        threading.Thread(target=self.server.status.pair, daemon=True).start()
        return self.respond(202, '{"status":"requested"}')


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--ip", required=True)
    a.add_argument("--port", type=int, default=9130)
    a.add_argument("--model", required=True)
    a.add_argument("--codex", default="codex")
    args = a.parse_args()
    pw = os.environ.get("PAIR_PORTAL_PASSWORD", "")
    if len(pw) < 14:
        a.error("PAIR_PORTAL_PASSWORD must be at least 14 chars")
    st = Status(args.model)
    st.codex = shutil.which(args.codex) or args.codex
    # Codex must never inherit the web password or GitHub token.
    st.env = {k: v for k, v in os.environ.items()
              if k not in {"PAIR_PORTAL_PASSWORD", "GH_TOKEN", "GITHUB_TOKEN",
                           "TAILSCALE_AUTHKEY", "TS_AUTHKEY"}}
    server = Server((args.ip, args.port), pw, st)
    thread = threading.Thread(target=login_and_pair, args=(st,), daemon=True)
    thread.start()
    print("PRIVATE CODEX PAIRING PORTAL READY (Tailscale-only, password required)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

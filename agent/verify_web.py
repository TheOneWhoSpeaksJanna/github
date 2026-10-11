"""Real model + real private web app HTTP integration, bound only to loopback."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--ollama", type=Path, required=True)
    p.add_argument("--port", type=int, default=19120)
    args = p.parse_args()
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    env["OLLAMA_CONTEXT_LENGTH"] = "4096"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"
    env["AGENT_PASSWORD"] = "this-is-a-test-password-only"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    auth = "Basic " + base64.b64encode(b"owner:this-is-a-test-password-only").decode()
    base = "http://127.0.0.1:" + str(args.port)
    with tempfile.TemporaryDirectory() as td:
        workspace = Path(td) / "files"
        log = open(Path(td) / "ollama.out", "w")
        log2 = open(Path(td) / "ollama.err", "w")
        blog = open(Path(td) / "agent.out", "w")
        berr = open(Path(td) / "agent.err", "w")
        ollama = subprocess.Popen([str(args.ollama), "serve"], env=env, stdout=log, stderr=log2,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        server = None
        try:
            for _ in range(45):
                try:
                    with urlopen("http://127.0.0.1:11434/api/tags", timeout=3):
                        break
                except Exception:
                    time.sleep(2)
            else:
                raise RuntimeError("Ollama never started")
            server = subprocess.Popen([
                sys.executable, str(Path(__file__).with_name("file_agent.py")),
                "--bind", "127.0.0.1", "--port", str(args.port),
                "--workspace", str(workspace), "--model", args.model,
            ], env=env, stdout=blog, stderr=berr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for _ in range(45):
                try:
                    with urlopen(base + "/health", timeout=3):
                        break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError("Private agent HTTP server never started")

            def req(path, body=None, headers=None):
                headers = headers or {}
                if body is not None:
                    headers["Content-Type"] = "application/json"
                return urlopen(Request(base + path, headers=headers,
                                       data=json.dumps(body).encode() if body is not None else None),
                               timeout=8)

            with HTTPErrorTest(401):
                req("/")
            with req("/", headers={"Authorization": auth}) as r:
                html = r.read().decode()
            assert "Pocket File Agent" in html
            with req("/app.js", headers={"Authorization": auth}) as r:
                assert b"Create files" not in r.read()
            with req("/style.css", headers={"Authorization": auth}) as r:
                assert b"background" in r.read()
            with HTTPErrorTest(403):
                req("/api/tasks", body={"goal": "Make file"}, headers={
                    "Authorization": auth, "Origin": "http://external.example"})

            started = time.monotonic()
            with req("/api/tasks", body={"goal":
                     "Create a file named hello.md containing the heading Local Agent and a sentence about downloading files to Android."},
                     headers={"Authorization": auth}) as r:
                job = json.load(r)["id"]
            state = {}
            for _ in range(95):
                with req("/api/tasks/" + job, headers={"Authorization": auth}) as r:
                    state = json.load(r)
                if state["status"] != "running":
                    break
                time.sleep(2)
            assert state.get("status") == "complete", state.get("message", "no response")
            assert any(f["path"] == "hello.md" for f in state["created"])
            with req("/download/hello.md", headers={"Authorization": auth}) as r:
                data = r.read()
                assert r.headers["Content-Disposition"].startswith("attachment")
            assert b"Local Agent" in data
            with req("/download-all.zip", headers={"Authorization": auth}) as r:
                with zipfile.ZipFile(io.BytesIO(r.read())) as z:
                    assert z.read("hello.md") == data
            print("PASSED: Authenticated private Android dashboard, same-origin guard, real Ollama file-creation task and downloaded ZIP.")
            print("Elapsed seconds:", round(time.monotonic() - started, 2))
            print("Downloaded bytes:", len(data))
        finally:
            if server:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
            ollama.terminate()
            try:
                ollama.wait(timeout=15)
            except subprocess.TimeoutExpired:
                ollama.kill()
            log.close(); log2.close(); blog.close(); berr.close()


class HTTPErrorTest:
    def __init__(self, code):
        self.code = code
    def __enter__(self):
        return self
    def __exit__(self, etype, value, tb):
        if etype is HTTPError and value.code == self.code:
            return True
        if etype is None:
            raise AssertionError("Expected HTTP status " + str(self.code))
        return False


if __name__ == "__main__":
    main()

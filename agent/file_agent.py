"""Pocket File Agent: bounded local-model task agent for a private Android dashboard.

No general-purpose shell executor, arbitrary remote URL fetcher, or broad filesystem
access. Only text file creation/revision in the designated output directory.
"""
from __future__ import annotations

import argparse
import base64
import hmac
import io
import json
import logging
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_INPUT = 2500
MAX_RESPONSE = 512 * 1024
MAX_FILE_BYTES = 96 * 1024
MAX_FILES_PER_TASK = 6
MAX_FILE_COUNT = 120
MAX_TOTAL_BYTES = 3 * 1024 * 1024
MAX_STEPS = 2
EXTENSIONS = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".html",
              ".css", ".json", ".csv", ".xml", ".yml", ".yaml", ".svg",
              ".sql", ".java", ".c", ".cpp", ".h", ".sh", ".ps1", ".ini"}
DENIED_PARTS = {".env", ".git", ".ssh", ".aws", ".azure", ".gnupg",
                "secrets", "credentials", "private_key", "__pycache__", "node_modules"}
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                    *(f"lpt{i}" for i in range(1, 10))}
SYSTEM = (
    "You are a LOCAL FILE-CREATING AGENT, not a conversational chatbot. "
    "Complete the user's file task by returning JSON that conforms exactly to the schema. "
    "Generate useful real file content, not a plan or placeholders. "
    "You may create and modify UTF-8 text files only within the provided workspace. "
    "Prefer concise high-quality output, at most 6 files. "
    "Give each file a simple relative filename with extension, e.g. notes.md or site/index.html. "
    "Don't claim to have executed scripts or sent files elsewhere. "
    "The application will write the files and give the user downloadable links. "
    "Respect existing file summaries; don't overwrite unrelated files."
)
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["message", "files"],
    "additionalProperties": False,
}
logger = logging.getLogger("pocket-agent")


class AgentError(ValueError):
    pass


def safe_path(root: Path, filename: str) -> Path:
    if not isinstance(filename, str) or len(filename) > 140 or not filename.strip():
        raise AgentError("Invalid file name")
    if "\\" in filename or "\x00" in filename or filename.startswith("/"):
        raise AgentError("Only relative forward-slash file names are supported")
    posix = PurePosixPath(filename)
    if any(part in ("..", ".") or part.startswith(".") or part.lower() in DENIED_PARTS
           for part in filename.split("/")):
        raise AgentError("Private, hidden or parent folder paths are not permitted")
    if len(posix.parts) > 4 or any(not re.fullmatch(r"[a-zA-Z0-9 _().-]{1,80}", part) for part in posix.parts):
        raise AgentError("Unsafe file name")
    if any(part.split(".")[0].lower() in WINDOWS_RESERVED for part in posix.parts):
        raise AgentError("Reserved Windows file name")
    if posix.suffix.lower() not in EXTENSIONS:
        raise AgentError("Only supported text file extensions may be created")
    root = root.resolve()
    target = root.joinpath(*posix.parts)
    if any(p.is_symlink() for p in [target, *target.parents] if p != root and root in p.parents):
        raise AgentError("Symbolic link is not allowed")
    if not target.resolve().is_relative_to(root):
        raise AgentError("Path escapes workspace")
    return target


def workspace_files(root: Path):
    root = root.resolve()
    result = []
    if not root.exists():
        return result
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            try:
                rel = path.relative_to(root).as_posix()
                safe_path(root, rel)
                result.append({"path": rel, "size": path.stat().st_size})
            except AgentError:
                pass
    return sorted(result, key=lambda d: d["path"])[:MAX_FILE_COUNT]


def write_files(root: Path, entries: list):
    root = root.resolve()
    if not isinstance(entries, list) or len(entries) > MAX_FILES_PER_TASK:
        raise AgentError("Model returned too many files")
    existing = workspace_files(root)
    existing_bytes = sum(x["size"] for x in existing)
    targets, seen, total_new = [], set(), 0
    for obj in entries:
        if not isinstance(obj, dict) or not isinstance(obj.get("content"), str):
            raise AgentError("Model produced invalid file content")
        target = safe_path(root, obj.get("path"))
        if str(target).casefold() in seen:
            raise AgentError("Duplicate file name")
        seen.add(str(target).casefold())
        data = obj["content"].encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise AgentError("A generated file exceeds the 96 KB size limit")
        total_new += len(data)
        targets.append((target, data))
    if len(existing) + len(targets) > MAX_FILE_COUNT:
        raise AgentError("Maximum workspace file count exceeded")
    replaced_bytes = sum(t.stat().st_size for t, _ in targets if t.is_file())
    if existing_bytes - replaced_bytes + total_new > MAX_TOTAL_BYTES:
        raise AgentError("Workspace exceeds the 3 MB automatic backup limit")
    # Validate every path and byte count before writing anything.
    saved = []
    for path, data in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Recheck after directory creation to prevent accidental symlink traversal.
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise AgentError("Unsafe path")
        temp = path.with_suffix(path.suffix + ".tmpagent")
        try:
            with temp.open("wb") as out:
                out.write(data)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        saved.append({"path": path.relative_to(root).as_posix(), "size": len(data)})
    return saved


def make_zip(root: Path) -> bytes:
    root = root.resolve()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for info in workspace_files(root):
            path = safe_path(root, info["path"])
            z.write(path, info["path"])
    if output.tell() > 4 * 1024 * 1024:
        raise AgentError("ZIP exceeds 4 MB")
    return output.getvalue()


class OllamaModel:
    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.url = base_url.rstrip("/") + "/api/chat"

    def generate(self, goal: str, files: list, contents: list):
        state = json.dumps({"existing_files": files[:50], "selected_file_contents": contents},
                           ensure_ascii=False)
        prompt = (
            "Task: " + goal + "\n"
            "Current workspace: " + state + "\n"
            "Return JSON with message and files. Create actual file content now."
        )
        request = {
            "model": self.model, "stream": False, "format": OUTPUT_SCHEMA,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": prompt}],
            "options": {"num_ctx": 4096, "num_predict": 2048, "temperature": 0.1},
            "keep_alive": "30m",
        }
        try:
            raw = json.dumps(request).encode("utf-8")
            r = urllib.request.Request(self.url, raw, {"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=180) as response:
                data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise AgentError("Model response exceeds 512 KB")
            payload = json.loads(data.decode("utf-8"))
            parsed = json.loads(payload.get("message", {}).get("content", ""))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            raise AgentError("Local model did not produce usable structured output: " + type(e).__name__) from e
        if not isinstance(parsed, dict) or not isinstance(parsed.get("message"), str) or not isinstance(parsed.get("files"), list):
            raise AgentError("Model output did not contain a valid action list")
        return parsed, {
            "prompt_tokens": payload.get("prompt_eval_count"),
            "generated_tokens": payload.get("eval_count"),
            "generation_seconds": round(payload.get("eval_duration", 0) / 1e9, 2),
        }


class FileAgent:
    def __init__(self, workspace: Path, model):
        self.root = workspace.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.tasks = {}
        self.lock = threading.Lock()
        self.busy = threading.Lock()

    def run(self, goal: str, selected: list | None = None):
        if not isinstance(goal, str) or not goal.strip() or len(goal) > MAX_INPUT:
            raise AgentError("Provide a task of up to 2500 characters")
        existing = workspace_files(self.root)
        excerpts = []
        for name in (selected or [])[:3]:
            path = safe_path(self.root, name)
            if path.is_file() and path.stat().st_size <= 12000:
                excerpts.append({"path": name, "content": path.read_text(encoding="utf-8", errors="replace")})
        started = time.monotonic()
        structured, stats = self.model.generate(goal.strip(), existing, excerpts)
        saved = write_files(self.root, structured["files"])
        return {
            "message": structured["message"][:2000],
            "created": saved,
            "duration_seconds": round(time.monotonic() - started, 2),
            "metrics": stats,
        }

    def submit(self, goal: str, selected: list | None = None):
        if not isinstance(goal, str) or not goal.strip() or len(goal) > MAX_INPUT:
            raise AgentError("Task must contain 1-2500 characters")
        if not isinstance(selected, list):
            raise AgentError("Selected files must be a list")
        if not self.busy.acquire(blocking=False):
            raise AgentError("The agent is already creating files; finish that task first")
        task_id = secrets.token_hex(9)
        with self.lock:
            if len(self.tasks) >= 40:
                for old in list(self.tasks)[:20]:
                    self.tasks.pop(old)
            self.tasks[task_id] = {"id": task_id, "status": "running"}
        def work():
            try:
                result = self.run(goal, selected)
                status = {"id": task_id, "status": "complete", **result}
            except Exception as exc:
                logger.warning("Task %s failed: %s", task_id, type(exc).__name__)
                status = {"id": task_id, "status": "failed",
                          "message": str(exc) if isinstance(exc, AgentError) else "The agent failed to complete the task"}
            finally:
                self.busy.release()
            with self.lock:
                self.tasks[task_id] = status
        threading.Thread(target=work, daemon=True).start()
        return task_id


class AgentServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, agent: FileAgent, password: str, html: str,
                 js: str = "", css: str = ""):
        super().__init__(address, AgentHandler)
        self.agent, self.password, self.html, self.js, self.css = agent, password, html, js, css


class AgentHandler(BaseHTTPRequestHandler):
    server: AgentServer
    def log_message(self, fmt, *args):
        # Do not publish user tasks, downloads or private Tailscale IPs in logs.
        logger.info("HTTP request processed: %s", self.command)

    def _headers(self, code, content_type="application/json", n=0, auth=False):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(n))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if auth:
            self.send_header("WWW-Authenticate", 'Basic realm="Private File Agent", charset="UTF-8"')
        self.end_headers()

    def _reply(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(code, n=len(data))
        self.wfile.write(data)

    def _authorized(self):
        value = self.headers.get("Authorization", "")
        if not value.startswith("Basic "):
            return False
        try:
            userpass = base64.b64decode(value[6:].encode("ascii"), validate=True).decode("utf-8")
            user, pw = userpass.split(":", 1)
            return hmac.compare_digest(user, "owner") and hmac.compare_digest(pw, self.server.password)
        except (ValueError, UnicodeError):
            return False

    def _guard(self):
        if not self._authorized():
            data = b"Authentication required"
            self._headers(401, "text/plain; charset=utf-8", len(data), auth=True)
            self.wfile.write(data)
            return False
        return True

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path == "/health":
            # No private details; used for local health checks.
            return self._reply(200, {"status": "ok"})
        if not self._guard():
            return
        if path in ("/", "/index.html"):
            data = self.server.html.encode("utf-8")
            self._headers(200, "text/html; charset=utf-8", len(data))
            return self.wfile.write(data)
        if path in ("/app.js", "/style.css"):
            content = self.server.js if path == "/app.js" else self.server.css
            data = content.encode("utf-8")
            mime = "text/javascript; charset=utf-8" if path == "/app.js" else "text/css; charset=utf-8"
            self._headers(200, mime, len(data))
            return self.wfile.write(data)
        if path == "/api/files":
            return self._reply(200, {"files": workspace_files(self.server.agent.root)})
        if path.startswith("/api/tasks/"):
            task_id = path.rsplit("/", 1)[-1]
            with self.server.agent.lock:
                task = self.server.agent.tasks.get(task_id)
            return self._reply(200, task) if task else self._reply(404, {"error": "Task not found"})
        if path.startswith("/download/"):
            name = urllib.parse.unquote(path[len("/download/"):])
            try:
                file = safe_path(self.server.agent.root, name)
                if not file.is_file() or file.stat().st_size > MAX_FILE_BYTES:
                    return self._reply(404, {"error": "File not found"})
                data = file.read_bytes()
            except (AgentError, OSError):
                return self._reply(404, {"error": "File not found"})
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''" + urllib.parse.quote(file.name, safe=""))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/download-all.zip":
            try:
                data = make_zip(self.server.agent.root)
            except (AgentError, OSError):
                return self._reply(500, {"error": "Could not create ZIP"})
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="AgentFiles.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return self.wfile.write(data)
        return self._reply(404, {"error": "Not found"})

    def do_POST(self):
        if not self._guard():
            return
        if self.path != "/api/tasks":
            return self._reply(404, {"error": "Not found"})
        # Same-origin request protection; JSON-only requests avoid drive-by forms.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and urllib.parse.urlsplit(origin).netloc != host:
            return self._reply(403, {"error": "Cross-origin actions are blocked"})
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            return self._reply(415, {"error": "JSON requests only"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 8192:
                return self._reply(413, {"error": "Request size invalid"})
            data = json.loads(self.rfile.read(size).decode("utf-8"))
            selected = data.get("selected", [])
            task = self.server.agent.submit(data.get("goal", ""), selected)
        except (ValueError, UnicodeError, KeyError, AgentError) as e:
            return self._reply(400, {"error": str(e)})
        return self._reply(202, {"id": task, "status": "running"})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9120)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--html", type=Path, default=Path(__file__).with_name("index.html"))
    args = p.parse_args()
    password = os.environ.get("AGENT_PASSWORD", "")
    if len(password) < 14:
        p.error("AGENT_PASSWORD must be at least 14 characters")
    agent = FileAgent(args.workspace, OllamaModel(args.model))
    server = AgentServer(
        (args.bind, args.port), agent, password,
        args.html.read_text(encoding="utf-8"),
        args.html.with_name("app.js").read_text(encoding="utf-8"),
        args.html.with_name("style.css").read_text(encoding="utf-8"),
    )
    logger.warning("PRIVATE FILE AGENT STARTED, model set, port %d (Tailscale-only access)", args.port)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

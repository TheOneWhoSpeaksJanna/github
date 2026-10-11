"""Offline integration tests: no Ollama downloads, secrets, private chats or Tailscale."""
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from file_agent import AgentError, AgentServer, FileAgent, make_zip, safe_path, write_files


class FakeModel:
    def generate(self, goal, files, contents):
        return {
            "message": "Created a useful local project.",
            "files": [
                {"path": "demo/hello.py", "content": "print('Hello Android')\n"},
                {"path": "demo/README.md", "content": "# Local demo\nRun hello.py.\n"},
            ],
        }, {"prompt_tokens": 10, "generated_tokens": 40}


class TestWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.agent = FileAgent(self.root, FakeModel())

    def test_real_file_task_and_zip(self):
        result = self.agent.run("Create a Python project with README")
        self.assertEqual(len(result["created"]), 2)
        self.assertIn("Hello Android", (self.root / "demo/hello.py").read_text())
        data = make_zip(self.root)
        with zipfile.ZipFile(io.BytesIO(data)) as zip_file:
            self.assertEqual(zip_file.namelist(), ["demo/README.md", "demo/hello.py"])
            self.assertIn("Run hello.py", zip_file.read("demo/README.md").decode())

    def test_reject_unsafe_or_hidden_file_paths(self):
        for name in ["../escape.txt", "/etc/password.txt", r"c:\windows\system.ini",
                     ".env", ".git/config.py", "sub/../evil.py", "bad.exe",
                     "CON.txt", "sub/.secret.txt", "a" * 180 + ".py"]:
            with self.subTest(name=name), self.assertRaises(AgentError):
                safe_path(self.root, name)

    def test_all_files_validate_before_saving(self):
        with self.assertRaises(AgentError):
            write_files(self.root, [
                {"path": "okay.md", "content": "safe"},
                {"path": "../../bad.txt", "content": "no"},
            ])
        self.assertFalse((self.root / "okay.md").exists())

    def test_file_size_and_extension_limits(self):
        with self.assertRaises(AgentError):
            write_files(self.root, [{"path": "large.txt", "content": "a" * 110000}])
        self.assertFalse((self.root / "large.txt").exists())

    def test_typed_text_file_update(self):
        write_files(self.root, [{"path": "notes.md", "content": "first"}])
        write_files(self.root, [{"path": "notes.md", "content": "updated"}])
        self.assertEqual((self.root / "notes.md").read_text(), "updated")

    def test_authenticated_web_task_and_download(self):
        html = "<h1>Mobile File Agent</h1>"
        server = AgentServer(("127.0.0.1", 0), self.agent, "fixture-test-password-strong",
                             html, "console.log('test');", "body{color:white}")
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:" + str(server.server_port)
        credentials = "Basic " + base64.b64encode(b"owner:fixture-test-password-strong").decode()

        def fetch(path, body=None, credentials_header=None, origin=None):
            headers = {}
            if credentials_header:
                headers["Authorization"] = credentials_header
            if body is not None:
                headers["Content-Type"] = "application/json"
            if origin:
                headers["Origin"] = origin
            req = Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                          headers=headers)
            return urlopen(req, timeout=15)

        with self.assertRaises(HTTPError) as no_login:
            fetch("/")
        self.assertEqual(no_login.exception.code, 401)
        self.assertIn("Mobile File Agent", fetch("/", credentials_header=credentials).read().decode())
        self.assertIn("console.log", fetch("/app.js", credentials_header=credentials).read().decode())
        self.assertIn("color:white", fetch("/style.css", credentials_header=credentials).read().decode())
        with self.assertRaises(HTTPError) as no_cross_origin:
            fetch("/api/tasks", {"goal": "Create files"}, credentials,
                  origin="http://outside.example")
        self.assertEqual(no_cross_origin.exception.code, 403)

        submission = json.load(fetch("/api/tasks", {"goal": "Make two files"}, credentials))
        task_id = submission["id"]
        import time
        for i in range(40):
            state = json.load(fetch("/api/tasks/" + task_id, credentials_header=credentials))
            if state["status"] != "running":
                break
            time.sleep(.1)
        self.assertEqual(state["status"], "complete")
        file_bytes = fetch("/download/demo/README.md", credentials_header=credentials).read()
        self.assertIn(b"Run hello.py", file_bytes)
        with zipfile.ZipFile(io.BytesIO(fetch("/download-all.zip", credentials_header=credentials).read())) as z:
            self.assertEqual(len(z.namelist()), 2)
        with self.assertRaises(HTTPError) as traversal:
            fetch("/download/%2e%2e/other.txt", credentials_header=credentials)
        self.assertIn(traversal.exception.code, (400, 404))


if __name__ == "__main__":
    unittest.main(verbosity=2)

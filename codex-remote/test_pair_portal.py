"""Offline tests for Codex Remote private account pairing page."""
import base64
import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pair_portal import Server, Status, extract_device_prompt, AUTH_URL


class Tests(unittest.TestCase):
    def test_one_time_code_recognition(self):
        sample = "1. Visit " + AUTH_URL + "\n2. Enter this one-time code (expires in 15 minutes)\n \u001b[94mABCD-1234\u001b[0m\n"
        url, code = extract_device_prompt(sample)
        self.assertEqual(url, AUTH_URL)
        self.assertEqual(code, "ABCD-1234")
        self.assertEqual(extract_device_prompt("do not trust this random word: ABCD-1234"), (None, None))

    def test_private_code_endpoints(self):
        status = Status("local-model-name")
        status.set(device_code="TEST-1234", stage="Waiting for authorization")
        server = Server(("127.0.0.1", 0), "fixture-strong-password", status)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            addr = "http://127.0.0.1:" + str(server.server_port)
            auth = "Basic " + base64.b64encode(b"owner:fixture-strong-password").decode()
            with self.assertRaises(HTTPError) as denied:
                urlopen(addr + "/api/status")
            self.assertEqual(denied.exception.code, 401)
            with urlopen(Request(addr + "/api/status", headers={"Authorization": auth})) as reply:
                obj = json.load(reply)
            self.assertEqual(obj["device_code"], "TEST-1234")
            self.assertFalse(obj["authenticated"])
            with urlopen(addr + "/health") as reply:
                obj = json.load(reply)
            self.assertNotIn("device_code", obj)
            request = Request(addr + "/api/refresh", method="POST", data=b"{}",
                              headers={"Authorization": auth,
                                       "Origin": "http://attacker.example",
                                       "Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as rejected:
                urlopen(request)
            self.assertEqual(rejected.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

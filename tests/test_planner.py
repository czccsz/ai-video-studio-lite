import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from aivideo.planner import plan
from aivideo.storyboard import demo


class Handler(BaseHTTPRequestHandler):
    mode = "success"
    received = None

    def do_POST(self):
        type(self).received = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.mode == "error":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"sensitive-provider-error")
            return
        if self.mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "/should-not-follow")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        content = "invalid json" if self.mode == "malformed" else "```json\n" + json.dumps(demo()) + "\n```"
        self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    def log_message(self, *_):
        pass


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_real_http_request_and_fenced_json(self):
        Handler.mode = "success"
        result = plan("测试主题", base_url=self.base, model="test", api_key="")
        self.assertEqual(result["title"], demo()["title"])
        self.assertEqual(Handler.received["messages"][1]["content"], "测试主题")
        self.assertEqual(Handler.received["model"], "test")

    def test_errors_do_not_echo_provider_body(self):
        Handler.mode = "error"
        with self.assertRaisesRegex(RuntimeError, "401") as caught:
            plan("测试", base_url=self.base, model="test", api_key="test-key")
        self.assertNotIn("sensitive-provider-error", str(caught.exception))
        self.assertNotIn("test-key", str(caught.exception))

    def test_bad_model_output(self):
        Handler.mode = "malformed"
        with self.assertRaisesRegex(ValueError, "格式不正确"):
            plan("测试", base_url=self.base, model="test")

    def test_redirect_is_not_followed(self):
        Handler.mode = "redirect"
        with self.assertRaisesRegex(RuntimeError, "302"):
            plan("测试", base_url=self.base, model="test")

    def test_remote_plain_http_rejected_before_request(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            plan("测试", base_url="http://example.com", model="test", api_key="secret")

    def test_missing_model(self):
        with self.assertRaisesRegex(ValueError, "模型名称"):
            plan("测试", base_url=self.base, model="")

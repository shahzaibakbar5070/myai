import hmac
import json
import os
from http.server import BaseHTTPRequestHandler

from instagram_bot import generate_ai_reply


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send_json(200, {"status": "online", "endpoint": "/api/chat"})

    def do_POST(self):
        test_token = os.environ.get("CHAT_TEST_TOKEN", "")
        supplied_token = self.headers.get("Authorization", "").removeprefix(
            "Bearer "
        )
        if not test_token:
            self._send_json(404, {"error": "Chat test endpoint is disabled"})
            return
        if not hmac.compare_digest(supplied_token, test_token):
            self._send_json(401, {"error": "Unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 65536:
                self._send_json(400, {"error": "Invalid request size"})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "Request body must be a JSON object"})
                return
            message = payload.get("message", "")
            if not isinstance(message, str) or not message.strip():
                self._send_json(400, {"error": "A message is required"})
                return
            conversation_id = payload.get("conversation_id", "chat-test")
            if (
                not isinstance(conversation_id, str)
                or not conversation_id
                or len(conversation_id) > 128
            ):
                self._send_json(400, {"error": "Invalid conversation_id"})
                return
            reply = generate_ai_reply(message.strip(), conversation_id)
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be valid JSON"})
            return
        except RuntimeError as error:
            print("Chat test failed: " + str(error))
            self._send_json(502, {"error": "Could not generate a reply"})
            return

        self._send_json(200, {"reply": reply})

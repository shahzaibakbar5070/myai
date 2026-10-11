import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from instagram_bot import generate_ai_reply, send_instagram_message


class handler(BaseHTTPRequestHandler):
    def _send_text(self, status, body):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        mode = params.get("hub.mode", [""])[0]
        token = params.get("hub.verify_token", [""])[0]
        challenge = params.get("hub.challenge", [""])[0]
        expected_token = os.environ.get("VERIFY_TOKEN", "")

        if mode == "subscribe" and expected_token and hmac.compare_digest(
            token, expected_token
        ):
            self._send_text(200, challenge)
        else:
            self._send_text(403, "Verification failed")

    def _signature_is_valid(self, body):
        app_secret = os.environ.get("META_APP_SECRET", "")
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not app_secret or not signature.startswith("sha256="):
            return False

        expected = hmac.new(
            app_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature[7:], expected)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_text(400, "Invalid content length")
            return

        if length < 1 or length > 1048576:
            self._send_text(400, "Invalid request size")
            return

        body = self.rfile.read(length)
        if not self._signature_is_valid(body):
            self._send_text(401, "Invalid webhook signature")
            return

        try:
            event = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_text(400, "Invalid JSON")
            return

        if not isinstance(event, dict):
            self._send_text(400, "Webhook body must be a JSON object")
            return
        if event.get("object") != "instagram":
            self._send_text(200, "EVENT_RECEIVED")
            return

        entries = event.get("entry", [])
        if not isinstance(entries, list):
            self._send_text(200, "EVENT_RECEIVED")
            return

        account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
        try:
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if account_id and entry.get("id") != account_id:
                    continue
                updates = entry.get("messaging", [])
                if not isinstance(updates, list):
                    continue
                for update in updates:
                    if not isinstance(update, dict):
                        continue
                    message = update.get("message", {})
                    sender = update.get("sender", {})
                    if not isinstance(message, dict) or not isinstance(sender, dict):
                        continue
                    sender_id = sender.get("id")
                    text = message.get("text", "")

                    if (
                        not sender_id
                        or not isinstance(text, str)
                        or not text.strip()
                        or message.get("is_echo")
                        or message.get("is_deleted")
                    ):
                        continue

                    reply = generate_ai_reply(text.strip(), str(sender_id))
                    send_instagram_message(sender_id, reply)
        except (RuntimeError, TypeError, AttributeError) as error:
            print("Instagram webhook processing failed: " + str(error))
            self._send_text(500, "Message processing failed")
            return

        self._send_text(200, "EVENT_RECEIVED")

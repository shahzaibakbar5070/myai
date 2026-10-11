import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class handler(BaseHTTPRequestHandler):

def do_GET(self):
    self.send_json(200, {"status": "Chat endpoint is online"})

        mode = params.get("hub.mode", [""])[0]
        token = params.get("hub.verify_token", [""])[0]
        challenge = params.get("hub.challenge", [""])[0]

        expected_token = os.environ.get("VERIFY_TOKEN", "")

        if mode == "subscribe" and token == expected_token and expected_token:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(challenge.encode())
        else:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Verification failed")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            event = json.loads(body)
            print("Instagram webhook event received")
            print(json.dumps(event))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"EVENT_RECEIVED")

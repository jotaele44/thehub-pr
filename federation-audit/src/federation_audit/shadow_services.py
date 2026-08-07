from __future__ import annotations

import argparse
import hashlib
import json
import socketserver
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReceiptStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


class ShadowHTTPHandler(BaseHTTPRequestHandler):
    store: ReceiptStore
    service_name = "shadow-http"

    def _handle(self) -> None:
        length = int(self.headers.get("content-length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        record = {
            "observed_at": utcnow(),
            "service": self.service_name,
            "method": self.command,
            "path": self.path,
            "body_sha256": digest(body),
            "body_size": len(body),
            "authorization_present": "authorization" in {key.lower() for key in self.headers.keys()},
        }
        self.store.append(record)
        payload = json.dumps({"accepted": True, "shadow": True, "request_sha256": record["body_sha256"]}).encode()
        self.send_response(202)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_PATCH = _handle
    do_DELETE = _handle

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class ShadowMessageHandler(ShadowHTTPHandler):
    service_name = "shadow-message"


class SMTPHandler(socketserver.StreamRequestHandler):
    store: ReceiptStore

    def handle(self) -> None:
        self.wfile.write(b"220 shadow-smtp ESMTP\r\n")
        data_mode = False
        message = bytearray()
        envelope: list[str] = []
        while True:
            line = self.rfile.readline()
            if not line:
                break
            stripped = line.rstrip(b"\r\n")
            if data_mode:
                if stripped == b".":
                    self.store.append(
                        {
                            "observed_at": utcnow(),
                            "service": "shadow-smtp",
                            "envelope": envelope,
                            "message_sha256": digest(bytes(message)),
                            "message_size": len(message),
                        }
                    )
                    self.wfile.write(b"250 queued in shadow sink\r\n")
                    data_mode = False
                    message.clear()
                    continue
                message.extend(line)
                continue
            command = stripped.decode("utf-8", errors="replace")
            upper = command.upper()
            if upper.startswith("EHLO") or upper.startswith("HELO"):
                self.wfile.write(b"250-shadow-smtp\r\n250 SIZE 10485760\r\n")
            elif upper.startswith("MAIL FROM:") or upper.startswith("RCPT TO:"):
                envelope.append(command)
                self.wfile.write(b"250 ok\r\n")
            elif upper == "DATA":
                data_mode = True
                self.wfile.write(b"354 end with <CRLF>.<CRLF>\r\n")
            elif upper == "QUIT":
                self.wfile.write(b"221 bye\r\n")
                break
            else:
                self.wfile.write(b"250 ok\r\n")


def run_http(host: str, port: int, artifacts: Path, message: bool = False) -> None:
    handler = ShadowMessageHandler if message else ShadowHTTPHandler
    handler.store = ReceiptStore(artifacts / ("message.jsonl" if message else "http.jsonl"))
    server = ThreadingHTTPServer((host, port), handler)
    server.serve_forever()


def run_smtp(host: str, port: int, artifacts: Path) -> None:
    SMTPHandler.store = ReceiptStore(artifacts / "smtp.jsonl")
    with socketserver.ThreadingTCPServer((host, port), SMTPHandler) as server:
        server.allow_reuse_address = True
        server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=["http", "message", "smtp"])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int)
    parser.add_argument("--artifacts", type=Path, default=Path("/artifacts"))
    args = parser.parse_args(argv)
    ports = {"http": 9080, "message": 9090, "smtp": 2525}
    port = args.port or ports[args.service]
    if args.service == "smtp":
        run_smtp(args.host, port, args.artifacts)
    else:
        run_http(args.host, port, args.artifacts, message=args.service == "message")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

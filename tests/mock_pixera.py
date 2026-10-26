"""Tiny fake Pixera API access point for the transport tests."""

import json
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})
    if method == "Pixera.Utility.outputDebug":
        return {"jsonrpc": "2.0", "id": request["id"], "result": params["message"]}
    if method == "Pixera.Screens.getScreens":
        return {"jsonrpc": "2.0", "id": request["id"], "result": [11, 22, 33]}
    if method == "Pixera.Utility.getLicenseJson":
        # Large reply whose chunks may well end in "}" before the message is complete.
        return {"jsonrpc": "2.0", "id": request["id"], "result": json.dumps([{"k": i} for i in range(5000)])}
    if method == "Pixera.Compound.startFirstTimeline":
        return {"jsonrpc": "2.0", "id": request["id"]}
    return {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "Method not found"}}


class MockTcpServer:
    def __init__(self, framing="pxr1", events_before_reply=0, chunk=7):
        self.framing = framing
        self.events_before_reply = events_before_reply
        self.chunk = chunk
        self.connections = 0
        self.requests = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _frame(self, obj):
        data = json.dumps(obj).encode()
        if self.framing == "pxr1":
            return b"pxr1" + struct.pack("<I", len(data)) + data
        if self.framing == "bare":
            return data
        return data + b"0xPX"

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        buffer = b""
        with conn:
            while True:
                data = conn.recv(4096)
                if not data:
                    return
                buffer += data
                while True:
                    if self.framing in ("pxr1", "bare"):
                        if len(buffer) < 8:
                            break
                        assert buffer[:4] == b"pxr1"
                        size = struct.unpack("<I", buffer[4:8])[0]
                        if len(buffer) < 8 + size:
                            break
                        message, buffer = buffer[8:8 + size], buffer[8 + size:]
                    else:
                        index = buffer.find(b"0xPX")
                        if index == -1:
                            break
                        message, buffer = buffer[:index], buffer[index + 4:]
                    request = json.loads(message)
                    self.requests.append(request)
                    out = b""
                    for n in range(self.events_before_reply):
                        out += self._frame({"jsonrpc": "2.0", "id": -1, "type": "monEvent", "name": "cueAdded",
                                            "entries": [{"handles": [n]}]})
                    out += self._frame(handle_request(request))
                    # Send in small pieces to exercise reassembly.
                    for i in range(0, len(out), self.chunk):
                        conn.sendall(out[i:i + self.chunk])

    def close(self):
        self.sock.close()


class MockHttpServer:
    def __init__(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                reply = json.dumps(handle_request(json.loads(body))).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(reply)))
                self.end_headers()
                self.wfile.write(reply)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()

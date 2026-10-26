#WRITTEN BY: Ted Charles Brown
#Transport rework (framing, persistent connections, monitoring events): MrZapp-LM

import itertools
import json
import select
import socket
import struct
import threading
import urllib.error
import urllib.request
from collections import deque
from typing import Any, Deque, List, Optional


class PixeraError(Exception):
    """Pixera answered with a JSON-RPC error object."""

    def __init__(self, error: dict, request: Optional[dict] = None):
        self.code = error.get("code")
        self.message = error.get("message", "")
        self.data = error.get("data")
        self.request = request
        method = request.get("method") if request else None
        super().__init__(f"{method}: {self.message} (code {self.code})" if method else f"{self.message} (code {self.code})")


class _Connection:
    """One TCP connection to a Pixera API access point.

    framing "pxr1": every message is prefixed with b"pxr1" + uint32 payload size (little endian).
    framing "dl":   every message is followed by the delimiter b"0xPX" (access point mode "JSON/TCP (dl)").
    """

    TAG = b"pxr1"
    DELIMITER = b"0xPX"

    def __init__(self, ip_address: str, port: int, framing: str, timeout: float):
        self.framing = framing
        self.timeout = timeout
        self.sock = socket.create_connection((ip_address, port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buffer = b""

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def write(self, payload: bytes):
        if self.framing == "pxr1":
            self.sock.sendall(self.TAG + struct.pack("<I", len(payload)) + payload)
        else:
            self.sock.sendall(payload + self.DELIMITER)

    def _fill(self):
        chunk = self.sock.recv(65536)
        if not chunk:
            raise ConnectionError("Pixera closed the connection")
        self.buffer += chunk

    def _take_message(self) -> Optional[bytes]:
        """Return one complete message from the buffer, or None if more data is needed."""
        if self.framing == "pxr1":
            if len(self.buffer) < 8:
                return None
            if self.buffer[:4] != self.TAG:
                raise ConnectionError(f"Unexpected data from Pixera (missing pxr1 header): {self.buffer[:32]!r}")
            size = struct.unpack("<I", self.buffer[4:8])[0]
            if len(self.buffer) < 8 + size:
                return None
            message, self.buffer = self.buffer[8:8 + size], self.buffer[8 + size:]
            return message
        index = self.buffer.find(self.DELIMITER)
        if index == -1:
            return None
        message, self.buffer = self.buffer[:index], self.buffer[index + len(self.DELIMITER):]
        return message

    def read(self) -> bytes:
        """Block (up to the timeout) until one complete message has arrived."""
        while True:
            message = self._take_message()
            if message is not None:
                return message
            self._fill()

    def read_available(self, timeout: float = 0) -> List[bytes]:
        """Return all messages that can be read now, waiting up to timeout seconds for the first."""
        messages = []
        while True:
            message = self._take_message()
            if message is not None:
                messages.append(message)
                continue
            readable, _, _ = select.select([self.sock], [], [], 0 if messages else timeout)
            if not readable:
                return messages
            self._fill()


class Pixera:
    """Client for the Pixera JSON API.

    The API access point in Pixera (Settings > API) must match the protocol:
    "TCP" -> JSON/TCP, "TCP_DL" -> JSON/TCP (dl), "HTTP" -> HTTP/TCP.

    By default every call opens and closes its own connection. Pass keep_alive=True (or use
    the client as a context manager) to reuse one connection. That is required for
    monitoring, because Pixera keeps the monitoring state per connection.
    """

    DEFAULT_PORT = 1400
    PROTOCOLS = ("TCP", "TCP_DL", "HTTP", "DIRECT")

    def __init__(self, ip_address="127.0.0.1", port=None, protocol="TCP", timeout=10.0, keep_alive=False):
        if protocol not in self.PROTOCOLS:
            raise ValueError(f"Unknown protocol {protocol!r}, expected one of {self.PROTOCOLS}")
        self.IP_ADDRESS = ip_address
        self.PORT = port if port is not None else self.DEFAULT_PORT
        self.protocol = protocol
        self.timeout = timeout
        self.keep_alive = keep_alive
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self._connection: Optional[_Connection] = None
        self._events: Deque[dict] = deque()

    # ------------------------------ connection handling ----------------------------- #

    def __enter__(self):
        self.keep_alive = True
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    def connect(self):
        """Open the persistent connection (only needed with keep_alive=True)."""
        with self._lock:
            if self._connection is None:
                self._connection = self._open(self.protocol, self.PORT)

    def close(self):
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _open(self, protocol: str, port: int) -> _Connection:
        framing = "dl" if protocol == "TCP_DL" else "pxr1"
        return _Connection(self.IP_ADDRESS, port, framing, self.timeout)

    # ------------------------------------ sending ----------------------------------- #

    def send(self, array=None, protocol=None, port=None, raw_output=False, verbose=False) -> Any:
        """
        Send one API call and return its result.

        :param array: [method, param_names, values] as returned by the API functions,
                      e.g. pixera.send(api.Screens.getScreens()). Empty sends a debug message.
        :param protocol: "TCP", "TCP_DL", "HTTP" or "DIRECT". Defaults to the client's protocol.
        :param port: Port for this call only. Defaults to the client's port.
        :param raw_output: Return the complete JSON-RPC reply instead of only its result.
        :param verbose: Print the request and the reply.
        :return: The "result" of the reply (None for functions without return value).
        :raises PixeraError: if Pixera replies with an error.
        """
        array = list(array) if array else []
        method = array[0] if len(array) >= 1 else None
        params = array[1] if len(array) >= 2 else None
        values = array[2] if len(array) >= 3 else None

        if method is None:
            method = "Pixera.Utility.outputDebug"
            params = params if params is not None else ["message"]
            values = values if values is not None else ["Hello from Python!"]

        protocol = protocol or self.protocol
        if protocol not in self.PROTOCOLS:
            raise ValueError(f"Unknown protocol {protocol!r}, expected one of {self.PROTOCOLS}")
        if protocol == "DIRECT":
            method = self._direct_method(method)

        request = {"jsonrpc": "2.0", "id": next(self._ids), "method": method}
        params_dict = self.create_params_dict(params, values)
        if params_dict:
            request["params"] = params_dict

        if verbose:
            print("Sending:", request)
        if protocol == "HTTP":
            reply = self._send_http(request, port or self.PORT)
        else:
            reply = self._send_tcp(request, protocol, port or self.PORT)
        if verbose:
            print("Received:", reply)

        if raw_output:
            return reply
        return self.parse_data(reply, request)

    def call(self, array) -> Any:
        """Shorthand for send(array)."""
        return self.send(array)

    @staticmethod
    def create_params_dict(params, values) -> dict:
        if not params:
            return {}
        if isinstance(params, str):
            params = params.split(",")
        params = [param.strip() for param in params]
        values = list(values or [])
        if len(values) != len(params):
            raise ValueError(f"{len(params)} parameter names but {len(values)} values")
        return dict(zip(params, values))

    @staticmethod
    def parse_data(reply, request: Optional[dict] = None):
        if isinstance(reply, (bytes, bytearray)):
            reply = json.loads(reply.decode("utf-8"))
        if not isinstance(reply, dict):
            return reply
        if "error" in reply:
            raise PixeraError(reply["error"], request)
        return reply.get("result")

    @staticmethod
    def _direct_method(method: str) -> str:
        """Pixera.X.y -> Pixera.Direct.X.y (legacy behaviour of the DIRECT protocol)."""
        if method.startswith("Pixera.Direct."):
            return method
        parts = method.split(".")
        if parts and parts[0] == "Pixera":
            parts.insert(1, "Direct")
        return ".".join(parts)

    def _send_tcp(self, request: dict, protocol: str, port: int) -> dict:
        payload = json.dumps(request).encode("utf-8")
        with self._lock:
            persistent = self.keep_alive and port == self.PORT and protocol == self.protocol
            if persistent:
                if self._connection is None:
                    self._connection = self._open(protocol, port)
                connection = self._connection
            else:
                connection = self._open(protocol, port)
            try:
                connection.write(payload)
                while True:
                    message = json.loads(connection.read().decode("utf-8"))
                    if isinstance(message, dict) and message.get("id") == request["id"]:
                        return message
                    # Monitoring events and other unsolicited messages.
                    self._events.append(message)
            except (OSError, ConnectionError, ValueError):
                if persistent:
                    self.close()
                raise
            finally:
                if not persistent:
                    connection.close()

    def _send_http(self, request: dict, port: int) -> dict:
        body = json.dumps(request).encode("utf-8")
        http_request = urllib.request.Request(
            f"http://{self.IP_ADDRESS}:{port}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise ConnectionError(f"HTTP {error.code} from Pixera: {error.read()[:200]!r}") from error

    # ---------------------------------- monitoring ---------------------------------- #

    def poll_events(self, timeout: float = 0) -> List[dict]:
        """Return monitoring events received on the persistent connection since the last call.

        Use with keep_alive=True after API.Utility.setMonitoringEventMode("all") has switched the
        connection to event mode. Events look like {"id": -1, "type": "monEvent", "name": "cueAdded",
        "entries": [...]}. With timeout > 0 waits that many seconds for an event if none is queued.
        """
        with self._lock:
            if self._connection is not None:
                wait = 0 if self._events else timeout
                for message in self._connection.read_available(wait):
                    self._events.append(json.loads(message.decode("utf-8")))
            events = list(self._events)
            self._events.clear()
            return events

    # ------------------------------------ helpers ----------------------------------- #

    def return_array(self, input):
        """Turn a list result (or its string form "[1,2,3]") into a list of strings."""
        if isinstance(input, list):
            return [str(item) for item in input]
        output = str(input)[1:-1].split(",")
        return [item.strip() for item in output if item.strip()]

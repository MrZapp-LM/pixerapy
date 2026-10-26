import json

import pytest

from PixeraPy import API, Pixera, PixeraError

from mock_pixera import MockHttpServer, MockTcpServer


@pytest.fixture(params=[("TCP", "pxr1"), ("TCP_DL", "dl")], ids=["pxr1", "dl"])
def server_and_protocol(request):
    protocol, framing = request.param
    server = MockTcpServer(framing=framing)
    yield server, protocol
    server.close()


def test_result_is_returned(server_and_protocol):
    server, protocol = server_and_protocol
    pixera = Pixera("127.0.0.1", server.port, protocol=protocol)
    assert pixera.send(API.outputDebug("Hello")) == "Hello"
    assert pixera.send(API.Screens.getScreens()) == [11, 22, 33]


def test_large_fragmented_reply(server_and_protocol):
    server, protocol = server_and_protocol
    pixera = Pixera("127.0.0.1", server.port, protocol=protocol)
    result = pixera.send(API.getLicenseJson())
    assert len(json.loads(result)) == 5000


def test_function_without_result_returns_none(server_and_protocol):
    server, protocol = server_and_protocol
    assert Pixera("127.0.0.1", server.port, protocol=protocol).send(API.startFirstTimeline()) is None


def test_error_raises(server_and_protocol):
    server, protocol = server_and_protocol
    with pytest.raises(PixeraError) as info:
        Pixera("127.0.0.1", server.port, protocol=protocol).send(["Pixera.Nope.nothing"])
    assert info.value.code == -32601


def test_optional_parameters_are_omitted(server_and_protocol):
    server, protocol = server_and_protocol
    pixera = Pixera("127.0.0.1", server.port, protocol=protocol)
    with pytest.raises(PixeraError):
        pixera.send(API.Screens.Screen.setPosition(5, 1.0))
    assert server.requests[-1]["params"] == {"handle": 5, "xPos": 1.0}


def test_protocol_and_port_override_per_call():
    pxr1, dl = MockTcpServer("pxr1"), MockTcpServer("dl")
    pixera = Pixera("127.0.0.1", pxr1.port)
    assert pixera.send(API.outputDebug("a"), protocol="TCP_DL", port=dl.port) == "a"
    assert pixera.PORT == pxr1.port  # the override does not stick
    assert pixera.send(API.outputDebug("b")) == "b"


def test_keep_alive_reuses_connection():
    server = MockTcpServer()
    with Pixera("127.0.0.1", server.port) as pixera:
        for i in range(5):
            assert pixera.send(API.outputDebug(str(i))) == str(i)
    assert server.connections == 1
    ids = [r["id"] for r in server.requests]
    assert ids == sorted(set(ids))


def test_unsolicited_messages_become_events():
    server = MockTcpServer(events_before_reply=2)
    with Pixera("127.0.0.1", server.port) as pixera:
        assert pixera.send(API.outputDebug("x")) == "x"
        events = pixera.poll_events()
    assert [e["entries"][0]["handles"] for e in events] == [[0], [1]]
    assert all(e["type"] == "monEvent" for e in events)


def test_default_send_outputs_debug():
    server = MockTcpServer()
    assert Pixera("127.0.0.1", server.port).send() == "Hello from Python!"


def test_http():
    server = MockHttpServer()
    try:
        pixera = Pixera("127.0.0.1", server.port, protocol="HTTP")
        assert pixera.send(API.outputDebug("web")) == "web"
    finally:
        server.close()


def test_direct_method_name():
    assert Pixera._direct_method("Pixera.Screens.Screen.setPosition") == "Pixera.Direct.Screens.Screen.setPosition"
    assert Pixera._direct_method("Pixera.Direct.Screen.setPosition") == "Pixera.Direct.Screen.setPosition"


def test_return_array():
    pixera = Pixera()
    assert pixera.return_array([1, 2]) == ["1", "2"]
    assert pixera.return_array("[1, 2]") == ["1", "2"]


def test_reply_without_pxr1_header_is_accepted():
    """In case Pixera answers JSON/TCP requests without the size header."""
    server = MockTcpServer(framing="bare", events_before_reply=1)
    with Pixera("127.0.0.1", server.port) as pixera:
        assert pixera.send(API.outputDebug("ü {}")) == "ü {}"
        assert len(json.loads(pixera.send(API.getLicenseJson()))) == 5000
        assert len(pixera.poll_events()) == 2

import socket
import threading

import pytest
from pyasn1.codec.ber import decoder, encoder
from pysnmp.proto import api

from printer_monitor.drivers.snmp import SNMPDriver

_TONER_LEVEL = "1.3.6.1.2.1.43.11.1.1.9.1.1"
_TONER_MAX   = "1.3.6.1.2.1.43.11.1.1.8.1.1"
_DRUM_LEVEL  = "1.3.6.1.2.1.43.11.1.1.9.1.2"
_DRUM_MAX    = "1.3.6.1.2.1.43.11.1.1.8.1.2"
_HR_STATUS   = "1.3.6.1.2.1.25.3.5.1.1.1"


class _FakeAgent:
    """Minimal SNMPv2c agent on localhost answering GETs from a dict.

    Talks to the driver over real UDP so the test exercises the actual pysnmp API
    (a mocked transport hid an ImportError after the pysnmp 7 upgrade).
    """

    def __init__(self, values: dict[str, int]):
        self.values = values
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self):
        p = api.PROTOCOL_MODULES[api.SNMP_VERSION_2C]
        while not self._stop.is_set():
            try:
                raw, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            req, _ = decoder.decode(raw, asn1Spec=p.Message())
            req_pdu = p.apiMessage.get_pdu(req)
            rsp = p.apiMessage.get_response(req)
            rsp_pdu = p.apiMessage.get_pdu(rsp)
            binds = []
            for oid, _val in p.apiPDU.get_varbinds(req_pdu):
                key = str(oid)
                if key in self.values:
                    binds.append((oid, p.Integer(self.values[key])))
                else:
                    binds.append((oid, p.NoSuchObject()))
            p.apiPDU.set_varbinds(rsp_pdu, binds)
            self.sock.sendto(encoder.encode(rsp), addr)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        self.sock.close()


def _fetch(values: dict[str, int]):
    with _FakeAgent(values) as agent:
        return SNMPDriver(host="127.0.0.1", port=agent.port).fetch()


def test_fetch_idle_with_toner_and_drum():
    data = _fetch({_TONER_LEVEL: 400, _TONER_MAX: 1000,
                   _DRUM_LEVEL: 880, _DRUM_MAX: 1000, _HR_STATUS: 3})
    assert data.toner_pct == 40
    assert data.drum_pct == 88
    assert data.status == "idle"


def test_fetch_printing_status():
    data = _fetch({_TONER_LEVEL: 500, _TONER_MAX: 1000,
                   _DRUM_LEVEL: 900, _DRUM_MAX: 1000, _HR_STATUS: 4})
    assert data.status == "printing"


def test_fetch_drum_unlimited():
    """When drum max is -1 (unlimited), drum_pct should be 100."""
    data = _fetch({_TONER_LEVEL: 400, _TONER_MAX: 1000,
                   _DRUM_LEVEL: -1, _DRUM_MAX: -1, _HR_STATUS: 3})
    assert data.drum_pct == 100


def test_fetch_missing_drum_oids_still_reports_status():
    data = _fetch({_TONER_LEVEL: 250, _TONER_MAX: 1000, _HR_STATUS: 3})
    assert data.toner_pct == 25
    assert data.status == "idle"


def test_fetch_offline_when_no_agent():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    data = SNMPDriver(host="127.0.0.1", port=port).fetch()
    assert data.status == "offline"


@pytest.mark.parametrize("exc", [OSError("boom"), RuntimeError("x")])
def test_fetch_offline_on_exception(monkeypatch, exc):
    driver = SNMPDriver(host="127.0.0.1")

    def _raise(_oids):
        raise exc

    monkeypatch.setattr(driver, "_get_oids", _raise)
    assert driver.fetch().status == "offline"

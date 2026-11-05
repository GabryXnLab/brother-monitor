# printer_monitor/drivers/snmp.py
from __future__ import annotations

import asyncio

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData, ContextData, ObjectIdentity, ObjectType, SnmpEngine,
    UdpTransportTarget, get_cmd,
)

from printer_monitor.drivers.base import PrinterData, PrinterDriver

# Standard Printer MIB v2 OIDs (RFC 3805)
_OID_TONER_LEVEL    = "1.3.6.1.2.1.43.11.1.1.9.1.1"
_OID_TONER_MAX      = "1.3.6.1.2.1.43.11.1.1.8.1.1"
_OID_DRUM_LEVEL     = "1.3.6.1.2.1.43.11.1.1.9.1.2"
_OID_DRUM_MAX       = "1.3.6.1.2.1.43.11.1.1.8.1.2"
_OID_PRINTER_STATUS = "1.3.6.1.2.1.25.3.5.1.1.1"

_ALL_OIDS = (_OID_TONER_LEVEL, _OID_TONER_MAX, _OID_DRUM_LEVEL, _OID_DRUM_MAX,
             _OID_PRINTER_STATUS)

# hrPrinterStatus values
_HR_STATUS = {3: "idle", 4: "printing", 5: "sleep"}


def _pct(level: int | None, max_val: int | None) -> int:
    """Convert raw level/max to percentage. -1 max means unlimited (return 100)."""
    if level is None or max_val is None:
        return 0
    if max_val <= 0:          # -1 = unlimited supply
        return 100
    return max(0, min(100, round(level * 100 / max_val)))


def _as_int(value) -> int | None:
    # SNMPv2c reports a missing OID as a NoSuchObject/NoSuchInstance value, not as an error.
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class SNMPDriver(PrinterDriver):
    """Driver for any printer that supports the standard Printer MIB via SNMP v2c."""

    def __init__(self, host: str, community: str = "public", port: int = 161):
        self.host      = host
        self.community = community
        self.port      = port

    async def _get_oids_async(self, oids: tuple[str, ...]) -> dict[str, int | None]:
        engine = SnmpEngine()
        try:
            target = await UdpTransportTarget.create(
                (self.host, self.port), timeout=3, retries=1)
            error_indication, error_status, _, var_binds = await get_cmd(
                engine,
                CommunityData(self.community),
                target,
                ContextData(),
                *(ObjectType(ObjectIdentity(oid)) for oid in oids),
            )
        finally:
            engine.close_dispatcher()
        if error_indication or error_status:
            return {oid: None for oid in oids}
        return {str(name): _as_int(value) for name, value in var_binds}

    def _get_oids(self, oids: tuple[str, ...]) -> dict[str, int | None]:
        """Single SNMP GET for all OIDs; missing or failed values are None."""
        # pysnmp >= 7 only offers an asyncio API; the Qt main thread has no running loop.
        return asyncio.run(self._get_oids_async(oids))

    def fetch(self) -> PrinterData:
        try:
            values = self._get_oids(_ALL_OIDS)
        except Exception:
            return PrinterData(status="offline")

        hr_status = values.get(_OID_PRINTER_STATUS)
        if hr_status is None:
            return PrinterData(status="offline")
        data = PrinterData()
        data.toner_pct = _pct(values.get(_OID_TONER_LEVEL), values.get(_OID_TONER_MAX))
        data.drum_pct  = _pct(values.get(_OID_DRUM_LEVEL),  values.get(_OID_DRUM_MAX))
        data.status    = _HR_STATUS.get(hr_status, "idle")
        return data

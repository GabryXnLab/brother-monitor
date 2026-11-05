# printer_monitor/drivers/brother_http.py
from __future__ import annotations
import re

import requests
from bs4 import BeautifulSoup

from printer_monitor.drivers.base import PrinterData, PrinterDriver

_TIMEOUT = 5


class BrotherHTTPDriver(PrinterDriver):
    """Driver for Brother printers that expose a web UI at /general/*.html."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> PrinterData:
        try:
            info_resp = requests.get(
                f"{self.base_url}/general/information.html",
                params={"kind": "item"},
                timeout=_TIMEOUT,
            )
            status_resp = requests.get(
                f"{self.base_url}/general/status.html",
                timeout=_TIMEOUT,
            )
            data = _parse_info(info_resp.text)
            _parse_status(status_resp.text, data)
            return data
        except requests.exceptions.RequestException:
            return PrinterData(status="offline")


def _parse_info(html: str) -> PrinterData:
    data = PrinterData()
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    def _find(pattern: str, group: int = 1, default=None):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(group) if m else default

    raw_model = _find(r"Model\s+Name\s+(Brother[^\n]{3,40}?)(?:\s{2,}|Serial|$)")
    if raw_model:
        data.model = re.sub(r"\s+", " ", raw_model.replace("\xa0", " ")).strip()

    data.serial   = _find(r"Serial\s+no\.\s+(\S+)") or ""
    data.firmware = _find(r"Main\s+Firmware\s+Version\s+(\S+)") or ""

    mem = _find(r"Memory\s+Size\s+(\d+)\s+MB")
    if mem:
        data.memory_mb = int(mem)

    pc = _find(r"Page\s+Counter\s+(\d+)")
    if pc:
        data.page_count = int(pc)

    cov = _find(r"Average\s+Coverage[*\s]*([\d.]+)%")
    if cov:
        data.avg_coverage = float(cov)

    drum = _find(r"Drum\s+Unit[*\s]*([\d]+)%")
    if drum:
        data.drum_pct = int(drum)

    toner = _find(r"Toner[*\s]*([\d]+)%")
    if toner:
        data.toner_pct = int(toner)

    jams: dict[str, int] = {}
    for key, pat in [
        ("total",  r"Total\s+Paper\s+Jams\s+(\d+)"),
        ("tray1",  r"Jam\s+Tray\s+1\s+(\d+)"),
        ("inside", r"Jam\s+Inside\s+(\d+)"),
        ("rear",   r"Jam\s+Rear\s+(\d+)"),
        ("duplex", r"Jam\s+2-sided\s+(\d+)"),
    ]:
        v = _find(pat)
        if v is not None:
            jams[key] = int(v)
    data.jams = jams

    rc = re.search(
        r"Replace\s+Count\s+Toner\s+(\d+)\s+Drum\s+Unit\s+(\d+)", text, re.IGNORECASE
    )
    if rc:
        data.replace_counts = {"toner": int(rc.group(1)), "drum": int(rc.group(2))}

    errors = []
    for m in re.finditer(
        r"\d+\s+([\w\s.'àèìòùÀÈÌÒÙ.-]{3,40}?)\s+Page\s*[:\s]+(\d+)", text
    ):
        desc = m.group(1).strip()
        if desc:
            errors.append({"desc": desc, "page": int(m.group(2))})
    data.errors = errors[:10]
    return data


def _parse_status(html: str, data: PrinterData) -> None:
    soup = BeautifulSoup(html, "html.parser")
    moni = soup.find(class_=re.compile(r"\bmoni\b"))
    if not moni:
        return
    classes = moni.get("class", [])
    text = moni.get_text(strip=True)
    data.status_detail = text
    if any(c in classes for c in ("moniError", "moniWarn")):
        data.status = "error"
    elif "moniOk" in classes:
        low = text.lower()
        if any(k in low for k in ("print", "stampa")):
            data.status = "printing"
        elif any(k in low for k in ("sleep", "risparmio")):
            data.status = "sleep"
        else:
            data.status = "idle"

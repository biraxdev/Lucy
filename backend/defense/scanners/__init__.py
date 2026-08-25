"""Authorized defensive scanners for internal network and host assessment."""

from .port_scan_defensive import run as port_scan
from .file_integrity import run as file_integrity
from .process_anomaly import run as process_anomaly

SCANNERS = {
    "port_scan": port_scan,
    "file_integrity": file_integrity,
    "process_anomaly": process_anomaly,
}

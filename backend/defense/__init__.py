"""
Lucy Defense Platform — defensive security module.

Provides a lightweight SIEM/EDR-style ingestion pipeline, anomaly detection,
and authorized scanning modules for authorized internal networks only.
"""

from .detection_engine import DetectionEngine

__all__ = ["DetectionEngine"]

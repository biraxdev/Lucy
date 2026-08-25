"""
CVEProvider — live NVD search + local CVE cache.

Searches NVD via the existing threat_intel module. When a CVE is imported,
it's stored as a Resource (type=cve) with a snapshot of the NVD data in
the content field. This allows tagging, linking, and versioning CVEs.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from peewee import fn

from core.library.base import apply_visibility, compute_content_hash
from database import database
from db.models import Resource, ResourceRelation

logger = logging.getLogger(__name__)


class CVEProvider:
    """Provider for CVE resources — live NVD search + local cache."""

    resource_type = "cve"

    # --- Search (live NVD + local cache) ---

    def search(
        self,
        query: str,
        filters: dict[str, Any],
        tenant_id: Optional[str],
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        """Search local cache first, then live NVD if query looks like a CVE ID or keyword."""
        user = filters.get("_user")

        # 1. Search local cache
        q = Resource.select().where(Resource.resource_type == "cve")
        q = apply_visibility(q, user)

        if query and query.strip():
            tokens = [t.lower() for t in query.strip().split() if t]
            for token in tokens:
                q = q.where(
                    (fn.LOWER(Resource.name).contains(token))
                    | (fn.LOWER(Resource.description).contains(token))
                    | (fn.LOWER(Resource.content).contains(token))
                )

        local_results = [r.to_dict(include_content=False) for r in q.limit(limit).offset(offset)]
        local_total = q.count()

        # 2. If query looks like a CVE ID or keyword and we have room, search NVD live
        if query and query.strip() and len(local_results) < limit:
            try:
                from core.threat_intel import search_cve_by_keyword
                live_cves = search_cve_by_keyword(query.strip(), limit=limit - len(local_results))
                for cve in live_cves:
                    # Check if already in local cache
                    existing = Resource.get_or_none(
                        (Resource.resource_type == "cve")
                        & (Resource.name == cve.get("cve_id", ""))
                    )
                    if not existing:
                        local_results.append({
                            "id": None,  # Not yet cached
                            "resource_type": "cve",
                            "name": cve.get("cve_id", ""),
                            "description": cve.get("description", "")[:256],
                            "status": "live",
                            "metadata": {
                                "cvss": cve.get("cvss"),
                                "severity": cve.get("severity"),
                                "published": cve.get("published"),
                                "url": cve.get("url"),
                                "references": cve.get("references", []),
                            },
                            "source": cve.get("url"),
                            "_live": True,
                        })
                local_total += len(live_cves)
            except Exception as exc:
                logger.debug("Live CVE search failed: %s", exc)

        return local_results, local_total

    # --- Get ---

    def get(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != "cve":
            return None
        return r.to_dict()

    # --- Preview ---

    def preview(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != "cve":
            return None
        d = r.to_dict()
        d["preview_type"] = "cve"
        meta = r.metadata_dict
        d["preview"] = {
            "cve_id": r.name,
            "description": r.description,
            "cvss": meta.get("cvss"),
            "severity": meta.get("severity"),
            "published": meta.get("published"),
            "affected_products": meta.get("affected_products", []),
            "references": meta.get("references", []),
            "kev": meta.get("kev", False),
            "epss": meta.get("epss"),
            "exploit_available": meta.get("exploit_available"),
            "url": meta.get("url", r.source),
        }
        d["preview_fields"] = ["cve_id", "severity", "cvss", "affected_products", "references", "exploit_available"]
        return d

    # --- Metadata ---

    def metadata(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != "cve":
            return None
        meta = r.metadata_dict
        return {
            "id": str(r.id),
            "resource_type": "cve",
            "cve_id": r.name,
            "name": r.name,
            "description": r.description,
            "status": r.status,
            "version": r.version,
            "tags": r.tags_list,
            "visibility": r.visibility,
            "cvss": meta.get("cvss"),
            "severity": meta.get("severity"),
            "published": meta.get("published"),
            "affected_products": meta.get("affected_products", []),
            "references": meta.get("references", []),
            "kev": meta.get("kev", False),
            "epss": meta.get("epss"),
            "exploit_available": meta.get("exploit_available"),
            "url": meta.get("url", r.source),
            "cached_at": meta.get("cached_at"),
            "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
            "updated_at": r.updated_at.isoformat() if hasattr(r.updated_at, "isoformat") else str(r.updated_at),
        }

    # --- Relations ---

    def relations(self, resource_id: str, tenant_id: Optional[str]) -> dict:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r:
            return {"outgoing": [], "incoming": []}

        outgoing = []
        for rel in ResourceRelation.select().where(ResourceRelation.source_id == r.id):
            target = Resource.get_or_none(Resource.id == rel.target_id)
            if target:
                outgoing.append({
                    "relation_id": str(rel.id),
                    "relation_type": rel.relation_type,
                    "target": target.to_dict(include_content=False),
                })

        incoming = []
        for rel in ResourceRelation.select().where(ResourceRelation.target_id == r.id):
            source = Resource.get_or_none(Resource.id == rel.source_id)
            if source:
                incoming.append({
                    "relation_id": str(rel.id),
                    "relation_type": rel.relation_type,
                    "source": source.to_dict(include_content=False),
                })

        return {"outgoing": outgoing, "incoming": incoming}

    # --- Import CVE from NVD ---

    def import_cve(self, cve_id: str, tenant_id: Optional[str], user: dict) -> dict:
        """Import a CVE from NVD into the local cache."""
        cve_id = cve_id.upper().strip()

        # Check if already cached
        existing = Resource.get_or_none(
            (Resource.resource_type == "cve") & (Resource.name == cve_id)
        )
        if existing:
            # Refresh from NVD
            return self._refresh_cve(existing, user)

        # Fetch from NVD
        from core.threat_intel import _nvd_request, NVD_API
        import urllib.parse

        params = urllib.parse.urlencode({"cveId": cve_id})
        url = f"{NVD_API}?{params}"
        data = _nvd_request(url)

        if not data or not data.get("vulnerabilities"):
            raise ValueError(f"CVE {cve_id} not found in NVD")

        cve_data = data["vulnerabilities"][0].get("cve", {})

        # Extract fields
        descriptions = cve_data.get("descriptions", [])
        description = ""
        for d in descriptions:
            if d.get("lang") == "en":
                description = d.get("value", "")
                break

        # CVSS
        cvss_score = None
        severity = "unknown"
        metrics = cve_data.get("metrics", {})
        if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
            cvss_data = metrics["cvssMetricV31"][0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity", "unknown")
        elif "cvssMetricV30" in metrics and metrics["cvssMetricV30"]:
            cvss_data = metrics["cvssMetricV30"][0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity", "unknown")

        # References
        refs = [r.get("url") for r in cve_data.get("references", []) if r.get("url")]

        # Affected products (from configurations)
        affected = []
        for config in cve_data.get("configurations", []):
            for node in config.get("nodes", []):
                for cpe_match in node.get("cpeMatch", []):
                    criteria = cpe_match.get("criteria", "")
                    if criteria:
                        affected.append(criteria)

        # Build snapshot
        snapshot = {
            "cve_id": cve_id,
            "description": description,
            "cvss": cvss_score,
            "severity": severity,
            "published": cve_data.get("published", ""),
            "last_modified": cve_data.get("lastModified", ""),
            "references": refs[:20],
            "affected_products": affected[:20],
            "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        now = datetime.now(timezone.utc)
        with database:
            r = Resource.create(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                resource_type="cve",
                name=cve_id,
                description=description[:500] if description else None,
                status="active",
                version="1.0.0",
                tags=json.dumps(["cve", severity.lower()], ensure_ascii=False),
                source=snapshot["url"],
                content=json.dumps(snapshot, ensure_ascii=False, indent=2),
                content_hash=compute_content_hash(json.dumps(snapshot, sort_keys=True)),
                metadata=json.dumps(snapshot, ensure_ascii=False),
                visibility="internal",
                source_type="cve",
                source_id=cve_id,
                created_by=user.get("username") if user else None,
                created_at=now,
                updated_at=now,
            )

        logger.info("Imported CVE %s into library cache", cve_id)
        return r.to_dict()

    def _refresh_cve(self, resource: Resource, user: dict) -> dict:
        """Refresh an existing CVE cache from NVD."""
        cve_id = resource.name
        from core.threat_intel import _nvd_request, NVD_API
        import urllib.parse

        params = urllib.parse.urlencode({"cveId": cve_id})
        url = f"{NVD_API}?{params}"
        data = _nvd_request(url)

        if not data or not data.get("vulnerabilities"):
            return resource.to_dict()  # Keep existing if NVD fails

        cve_data = data["vulnerabilities"][0].get("cve", {})
        descriptions = cve_data.get("descriptions", [])
        description = ""
        for d in descriptions:
            if d.get("lang") == "en":
                description = d.get("value", "")
                break

        cvss_score = None
        severity = "unknown"
        metrics = cve_data.get("metrics", {})
        if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
            cvss_data = metrics["cvssMetricV31"][0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity", "unknown")
        elif "cvssMetricV30" in metrics and metrics["cvssMetricV30"]:
            cvss_data = metrics["cvssMetricV30"][0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity", "unknown")

        refs = [r.get("url") for r in cve_data.get("references", []) if r.get("url")]
        affected = []
        for config in cve_data.get("configurations", []):
            for node in config.get("nodes", []):
                for cpe_match in node.get("cpeMatch", []):
                    criteria = cpe_match.get("criteria", "")
                    if criteria:
                        affected.append(criteria)

        snapshot = {
            "cve_id": cve_id,
            "description": description,
            "cvss": cvss_score,
            "severity": severity,
            "published": cve_data.get("published", ""),
            "last_modified": cve_data.get("lastModified", ""),
            "references": refs[:20],
            "affected_products": affected[:20],
            "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        with database:
            # Create version snapshot before refresh
            from core.library.base import create_version_snapshot
            create_version_snapshot(resource, change_note="Before NVD refresh", user=user)

            resource.description = description[:500] if description else None
            resource.content = json.dumps(snapshot, ensure_ascii=False, indent=2)
            resource.metadata = json.dumps(snapshot, ensure_ascii=False)
            resource.content_hash = compute_content_hash(json.dumps(snapshot, sort_keys=True))
            resource.updated_at = datetime.now(timezone.utc)
            resource.save()

        return resource.to_dict()

    # --- CRUD not supported for CVE (use import_cve) ---

    def create(self, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        raise NotImplementedError("Use import_cve to add CVEs to the library")

    def update(self, resource_id: str, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        # Allow updating tags/status/visibility but not content (use refresh)
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != "cve":
            raise ValueError("CVE resource not found")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        with database:
            if "tags" in data:
                r.tags_list = data["tags"]
            if "status" in data:
                r.status = data["status"]
            if "visibility" in data:
                r.visibility = data["visibility"]
            if "project" in data:
                r.project = data["project"]
            if "favorite" in data:
                r.favorite = data["favorite"]
            if "pinned" in data:
                r.pinned = data["pinned"]
            r.updated_at = now
            r.save()
        return r.to_dict()

    def delete(self, resource_id: str, tenant_id: Optional[str], user: dict) -> None:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != "cve":
            raise ValueError("CVE resource not found")
        with database:
            ResourceRelation.delete().where(
                (ResourceRelation.source_id == r.id) | (ResourceRelation.target_id == r.id)
            ).execute()
            r.delete_instance()

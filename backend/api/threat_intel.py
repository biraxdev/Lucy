"""
Threat Intelligence API — CVE/NVD lookup, CISA KEV, EPSS, exploit availability,
CVE watch, and finding enrichment.
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.threat_intel import (
    search_cve_by_keyword,
    enrich_finding_with_cves,
    correlate_software_vulns,
    # KEV
    check_kev,
    enrich_cves_with_kev,
    list_kev_by_product,
    # EPSS
    get_epss_scores,
    enrich_cves_with_epss,
    get_high_risk_cves,
    # Exploits
    check_exploit_availability,
    batch_check_exploits,
    enrich_cves_with_exploits,
    # CVE Watch
    update_cve_watch,
    run_cve_watch_check,
    get_cve_watch_status,
    # Full pipeline
    full_cve_enrichment,
)
from dependencies import CurrentUser, OperatorUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/threat-intel", tags=["threat-intel"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CVESearchRequest(BaseModel):
    keyword: str = Field(..., description="Search keyword (e.g., 'Windows LSASS', 'Chrome 120')")
    limit: int = Field(default=10, le=50)


class FindingEnrichRequest(BaseModel):
    finding_id: str
    keywords: list[str] = Field(default_factory=list)


class SoftwareCorrelationRequest(BaseModel):
    software: list[dict] = Field(
        default_factory=list,
        description="List of {name, version} dicts",
    )


class KEVCheckRequest(BaseModel):
    cve_ids: list[str] = Field(default_factory=list)


class KEVProductRequest(BaseModel):
    product: str
    limit: int = Field(default=20, le=100)


class EPSSRequest(BaseModel):
    cve_ids: list[str] = Field(default_factory=list)


class EPSSHighRiskRequest(BaseModel):
    cve_ids: list[str] = Field(default_factory=list)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class ExploitCheckRequest(BaseModel):
    cve_id: str


class BatchExploitCheckRequest(BaseModel):
    cve_ids: list[str] = Field(default_factory=list)


class FullEnrichmentRequest(BaseModel):
    cves: list[dict] = Field(default_factory=list, description="List of CVE dicts from search results")


class CVEWatchUpdateRequest(BaseModel):
    enabled: bool | None = None
    keywords: list[str] | None = None
    products: list[dict] | None = None
    min_cvss: float | None = Field(default=None, ge=0.0, le=10.0)
    epss_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    agent_software: dict | None = None
    check_kev: bool | None = None
    check_epss: bool | None = None


# ---------------------------------------------------------------------------
# Basic CVE search (existing)
# ---------------------------------------------------------------------------


@router.get("/cve/search")
async def cve_search(keyword: str, limit: int = 10, current_user: CurrentUser = None) -> dict:
    """Search NVD for CVEs matching a keyword."""
    cves = search_cve_by_keyword(keyword, limit=min(limit, 50))
    return {"status": "ok", "keyword": keyword, "count": len(cves), "cves": cves}


@router.post("/cve/search")
async def cve_search_post(body: CVESearchRequest, current_user: CurrentUser = None) -> dict:
    """Search NVD for CVEs (POST version for complex keywords)."""
    cves = search_cve_by_keyword(body.keyword, limit=body.limit)
    return {"status": "ok", "keyword": body.keyword, "count": len(cves), "cves": cves}


@router.post("/finding/{finding_id}/enrich")
async def enrich_finding(
    finding_id: str,
    body: FindingEnrichRequest,
    current_user: OperatorUser = None,
) -> dict:
    """Enrich a finding with related CVEs from NVD."""
    if body.finding_id != finding_id:
        body.finding_id = finding_id
    result = enrich_finding_with_cves(finding_id, body.keywords)
    if result.get("status") == "error":
        raise HTTPException(404, result.get("message", "Finding not found"))
    return result


@router.post("/software/correlate")
async def correlate_software(
    body: SoftwareCorrelationRequest,
    current_user: CurrentUser = None,
) -> dict:
    """Correlate a list of installed software with known CVEs from NVD."""
    vulns = correlate_software_vulns(body.software)
    return {
        "status": "ok",
        "software_count": len(body.software),
        "vulns_found": len(vulns),
        "vulnerabilities": vulns,
    }


# ---------------------------------------------------------------------------
# 1. CISA KEV — Known Exploited Vulnerabilities
# ---------------------------------------------------------------------------


@router.post("/kev/check")
async def kev_check(body: KEVCheckRequest, current_user: CurrentUser = None) -> dict:
    """Check if CVEs are in the CISA Known Exploited Vulnerabilities catalog.

    CVEs in the KEV catalog are actively exploited in the wild and require
    immediate remediation per CISA Binding Operational Directive 22-01.
    """
    matches = check_kev(body.cve_ids)
    return {
        "status": "ok",
        "checked": len(body.cve_ids),
        "kev_matches": len(matches),
        "matches": matches,
    }


@router.get("/kev/search")
async def kev_search(product: str, limit: int = 20, current_user: CurrentUser = None) -> dict:
    """Search CISA KEV catalog by product or vendor name."""
    results = list_kev_by_product(product, limit=min(limit, 100))
    return {
        "status": "ok",
        "product": product,
        "count": len(results),
        "results": results,
    }


@router.post("/kev/enrich")
async def kev_enrich(body: KEVCheckRequest, current_user: CurrentUser = None) -> dict:
    """Enrich a list of CVE IDs with KEV status."""
    from core.threat_intel import _load_kev_catalog

    kev_map = _load_kev_catalog()
    enriched = []
    for cve_id in body.cve_ids:
        cve_upper = cve_id.upper()
        if cve_upper in kev_map:
            entry = kev_map[cve_upper]
            entry["in_kev"] = True
            enriched.append(entry)
        else:
            enriched.append({"cve_id": cve_upper, "in_kev": False})
    return {"status": "ok", "enriched": enriched}


# ---------------------------------------------------------------------------
# 2. EPSS — Exploit Prediction Scoring System
# ---------------------------------------------------------------------------


@router.post("/epss/scores")
async def epss_scores(body: EPSSRequest, current_user: CurrentUser = None) -> dict:
    """Get EPSS scores for a list of CVE IDs.

    EPSS estimates the probability (0-1) that a vulnerability will be exploited
    in the wild within 30 days. Score > 0.5 = high risk, > 0.9 = critical.
    """
    scores = get_epss_scores(body.cve_ids)
    return {
        "status": "ok",
        "count": len(scores),
        "scores": list(scores.values()),
    }


@router.get("/epss/{cve_id}")
async def epss_single(cve_id: str, current_user: CurrentUser = None) -> dict:
    """Get EPSS score for a single CVE."""
    scores = get_epss_scores([cve_id])
    return scores.get(cve_id.upper(), {"cve_id": cve_id, "epss": None, "percentile": None})


@router.post("/epss/high-risk")
async def epss_high_risk(body: EPSSHighRiskRequest, current_user: CurrentUser = None) -> dict:
    """Filter CVEs with EPSS score above threshold (high exploitation risk)."""
    high_risk = get_high_risk_cves(body.cve_ids, epss_threshold=body.threshold)
    return {
        "status": "ok",
        "threshold": body.threshold,
        "count": len(high_risk),
        "high_risk_cves": high_risk,
    }


# ---------------------------------------------------------------------------
# 3. Exploit Availability Check
# ---------------------------------------------------------------------------


@router.get("/exploits/{cve_id}")
async def check_exploits(cve_id: str, current_user: CurrentUser = None) -> dict:
    """Check if public exploits exist for a CVE.

    Searches GitHub, ExploitDB, and Metasploit for exploit code.
    """
    result = check_exploit_availability(cve_id)
    return result


@router.post("/exploits/batch")
async def batch_exploits(body: BatchExploitCheckRequest, current_user: CurrentUser = None) -> dict:
    """Batch check exploit availability for multiple CVEs."""
    results = batch_check_exploits(body.cve_ids)
    total_exploits = sum(r["exploit_count"] for r in results)
    cves_with_exploits = sum(1 for r in results if r["has_exploit"])
    return {
        "status": "ok",
        "checked": len(body.cve_ids),
        "cves_with_exploits": cves_with_exploits,
        "total_exploit_references": total_exploits,
        "results": results,
    }


# ---------------------------------------------------------------------------
# 4. CVE Watch — veille automatique
# ---------------------------------------------------------------------------


@router.get("/watch/status")
async def watch_status(current_user: CurrentUser = None) -> dict:
    """Get CVE watch configuration and status."""
    return get_cve_watch_status()


@router.post("/watch/update")
async def watch_update(body: CVEWatchUpdateRequest, current_user: OperatorUser = None) -> dict:
    """Update CVE watch configuration.

    Configure keywords, products, and thresholds for automated CVE monitoring.
    """
    config = update_cve_watch(
        enabled=body.enabled,
        keywords=body.keywords,
        products=body.products,
        min_cvss=body.min_cvss,
        epss_threshold=body.epss_threshold,
        agent_software=body.agent_software,
    )
    return {"status": "ok", "config": {
        "enabled": config.get("enabled", False),
        "keywords": config.get("keywords", []),
        "products": config.get("products", []),
        "min_cvss": config.get("min_cvss", 7.0),
        "epss_threshold": config.get("epss_threshold", 0.5),
        "check_kev": config.get("check_kev", True),
        "check_epss": config.get("check_epss", True),
    }}


@router.post("/watch/run")
async def watch_run(current_user: OperatorUser = None) -> dict:
    """Run a CVE watch check manually.

    Searches for new CVEs matching watch criteria, cross-references with
    CISA KEV and EPSS, and checks exploit availability.
    """
    result = run_cve_watch_check()
    return result


# ---------------------------------------------------------------------------
# Full enrichment pipeline
# ---------------------------------------------------------------------------


@router.post("/cve/enrich-full")
async def enrich_full(body: FullEnrichmentRequest, current_user: CurrentUser = None) -> dict:
    """Full CVE enrichment pipeline: KEV + EPSS + Exploit availability.

    Takes a list of CVE dicts (from search results) and enriches each with:
    - CISA KEV status (actively exploited in the wild)
    - EPSS score (exploitation probability 0-1)
    - Exploit availability (GitHub/ExploitDB/Metasploit)
    - Combined risk score (0-100) and priority (immediate/high/medium/low)
    """
    enriched = full_cve_enrichment(body.cves)
    return {
        "status": "ok",
        "count": len(enriched),
        "cves": enriched,
    }


@router.get("/cve/{cve_id}/full")
async def cve_full_lookup(cve_id: str, current_user: CurrentUser = None) -> dict:
    """Full lookup for a single CVE: NVD details + KEV + EPSS + exploits.

    One endpoint to get everything about a CVE.
    """
    from core.threat_intel import _nvd_request
    import urllib.parse as _urlparse

    # Use NVD cveId API directly (more reliable than keyword search for exact CVE)
    cve_id_upper = cve_id.upper()
    params = _urlparse.urlencode({"cveId": cve_id_upper})
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?{params}"
    data = _nvd_request(url)

    cves = []
    if data and data.get("vulnerabilities"):
        cve_data = data["vulnerabilities"][0].get("cve", {})
        descriptions = cve_data.get("descriptions", [])
        desc = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")
        metrics = cve_data.get("metrics", {})
        cvss_data = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                cvss_data = metrics[key][0].get("cvssData", {})
                break
        cves = [{
            "cve_id": cve_data.get("id", cve_id_upper),
            "description": desc[:500],
            "cvss": cvss_data.get("baseScore", 0.0) if cvss_data else 0.0,
            "severity": cvss_data.get("baseSeverity", "UNKNOWN") if cvss_data else "UNKNOWN",
            "published": cve_data.get("published", ""),
            "references": [r.get("url") for r in cve_data.get("references", [])][:10],
            "url": f"https://nvd.nist.gov/vuln/detail/{cve_data.get('id', cve_id_upper)}",
        }]

    if not cves:
        return {"status": "not_found", "cve_id": cve_id_upper}

    # Full enrichment
    enriched = full_cve_enrichment(cves)
    return {
        "status": "ok",
        "cve_id": cve_id_upper,
        "cve": enriched[0],
    }

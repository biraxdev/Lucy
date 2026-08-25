"""
Threat Intel Engine — CVE/NVD integration and vulnerability correlation.

Queries the NVD API for CVEs matching software discovered on agents,
correlates them with findings, and enriches findings with CVE references.

NVD API is free (no key needed, rate-limited to 5 req/30s without key).
"""
import json
import logging
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from database import database
from db.models import Finding

logger = logging.getLogger(__name__)

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_TIMEOUT = 15
_CACHE: dict[str, dict] = {}  # cpe23 -> cached vuln list


def _nvd_request(url: str) -> dict | None:
    """Make a request to the NVD API with proper error handling."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Lucy-SecOps/1.0"})
        with urllib.request.urlopen(req, timeout=NVD_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("NVD API request failed: %s", exc)
        return None


def search_cve_by_keyword(keyword: str, limit: int = 10) -> list[dict]:
    """Search NVD for CVEs matching a keyword (e.g., 'Windows LSASS', 'Chrome').

    Returns list of CVE dicts with: id, description, cvss, severity, url, published.
    """
    params = urllib.parse.urlencode({
        "keywordSearch": keyword,
        "resultsPerPage": str(limit),
    })
    url = f"{NVD_API}?{params}"
    data = _nvd_request(url)
    if not data or "vulnerabilities" not in data:
        return []

    cves = []
    for vuln in data["vulnerabilities"]:
        cve = vuln.get("cve", {})
        cve_id = cve.get("id", "")
        descriptions = cve.get("descriptions", [])
        desc = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")

        # Extract CVSS
        metrics = cve.get("metrics", {})
        cvss_data = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                cvss_data = metrics[key][0].get("cvssData", {})
                break
        cvss_score = cvss_data.get("baseScore", 0.0) if cvss_data else 0.0
        severity = cvss_data.get("baseSeverity", "UNKNOWN") if cvss_data else "UNKNOWN"

        # Extract references
        refs = [r.get("url") for r in cve.get("references", []) if r.get("url")]

        cves.append({
            "cve_id": cve_id,
            "description": desc[:500],
            "cvss": cvss_score,
            "severity": severity,
            "published": cve.get("published", ""),
            "references": refs[:5],
            "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        })

    return cves


def search_cve_by_cpe(cpe23: str, limit: int = 20) -> list[dict]:
    """Search NVD for CVEs matching a CPE 2.3 string.

    Args:
        cpe23: CPE 2.3 formatted string (e.g., "cpe:2.3:a:google:chrome:120.0:*:*:*:*:*:*:*")
    """
    if cpe23 in _CACHE:
        return _CACHE[cpe23]

    params = urllib.parse.urlencode({"cpeName": cpe23, "resultsPerPage": str(limit)})
    url = f"{NVD_API}?{params}"
    data = _nvd_request(url)
    if not data or "vulnerabilities" not in data:
        return []

    cves = []
    for vuln in data["vulnerabilities"]:
        cve = vuln.get("cve", {})
        cve_id = cve.get("id", "")
        descriptions = cve.get("descriptions", [])
        desc = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")

        metrics = cve.get("metrics", {})
        cvss_data = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                cvss_data = metrics[key][0].get("cvssData", {})
                break
        cvss_score = cvss_data.get("baseScore", 0.0) if cvss_data else 0.0

        cves.append({
            "cve_id": cve_id,
            "description": desc[:500],
            "cvss": cvss_score,
            "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        })

    _CACHE[cpe23] = cves
    return cves


def enrich_finding_with_cves(finding_id: str, keywords: list[str]) -> dict:
    """Enrich a finding with related CVEs from NVD.

    Args:
        finding_id: The Finding UUID
        keywords: Search keywords (e.g., ["Windows LSASS", "Credential Guard"])

    Returns:
        dict with cves found and enrichment status
    """
    finding = Finding.get_or_none(Finding.id == finding_id)
    if not finding:
        return {"status": "error", "message": "Finding not found"}

    all_cves = []
    for kw in keywords[:3]:  # Limit to 3 keyword searches to respect rate limits
        cves = search_cve_by_keyword(kw, limit=5)
        all_cves.extend(cves)

    # Deduplicate by CVE ID
    seen = set()
    unique_cves = []
    for cve in all_cves:
        if cve["cve_id"] not in seen:
            seen.add(cve["cve_id"])
            unique_cves.append(cve)

    if unique_cves:
        # Update finding evidence with CVE references
        try:
            evidence = json.loads(finding.evidence) if finding.evidence else {}
        except Exception:
            evidence = {}

        evidence["cves"] = unique_cves
        evidence["enriched_at"] = datetime.now(timezone.utc).isoformat()

        with database.atomic():
            finding.evidence = json.dumps(evidence, ensure_ascii=False)
            # Update CVSS to max of existing and highest CVE
            if unique_cves:
                max_cvss = max(c.get("cvss", 0) for c in unique_cves)
                try:
                    current_cvss = float(finding.cvss) if finding.cvss else 0
                except (ValueError, TypeError):
                    current_cvss = 0
                if max_cvss > current_cvss:
                    finding.cvss = str(max_cvss)
            finding.updated_at = datetime.now(timezone.utc)
            finding.save()

    return {
        "status": "ok",
        "finding_id": str(finding_id),
        "cves_found": len(unique_cves),
        "cves": unique_cves,
    }


def correlate_software_vulns(software_list: list[dict]) -> list[dict]:
    """Given a list of installed software, correlate with NVD CVEs.

    Args:
        software_list: [{"name": "Chrome", "version": "120.0.6099.71"}, ...]

    Returns:
        List of vulnerabilities found, sorted by CVSS descending.
    """
    all_vulns = []
    for sw in software_list[:10]:  # Limit to 10 products
        name = sw.get("name", "")
        version = sw.get("version", "")
        if not name:
            continue
        keyword = f"{name} {version}".strip()
        cves = search_cve_by_keyword(keyword, limit=5)
        for cve in cves:
            cve["software"] = name
            cve["version"] = version
            all_vulns.append(cve)

    # Sort by CVSS descending
    all_vulns.sort(key=lambda v: v.get("cvss", 0), reverse=True)
    return all_vulns


# ===========================================================================
# 1. CISA KEV Catalog — Known Exploited Vulnerabilities cross-reference
# ===========================================================================

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
_KEV_CACHE: dict[str, dict] | None = None  # cve_id -> KEV entry
_KEV_CACHE_TIME: float = 0
_KEV_CACHE_TTL = 3600  # 1 hour


def _load_kev_catalog() -> dict[str, dict]:
    """Load and cache the CISA KEV catalog (cached for 1 hour)."""
    global _KEV_CACHE, _KEV_CACHE_TIME
    import time

    now = time.time()
    if _KEV_CACHE is not None and (now - _KEV_CACHE_TIME) < _KEV_CACHE_TTL:
        return _KEV_CACHE

    try:
        req = urllib.request.Request(CISA_KEV_URL, headers={"User-Agent": "Lucy-SecOps/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        kev_map = {}
        for vuln in data.get("vulnerabilities", []):
            cve_id = vuln.get("cveID", "").upper()
            if cve_id:
                kev_map[cve_id] = {
                    "cve_id": cve_id,
                    "vendor": vuln.get("vendorProject", ""),
                    "product": vuln.get("product", ""),
                    "vulnerability_name": vuln.get("vulnerabilityName", ""),
                    "date_added": vuln.get("dateAdded", ""),
                    "due_date": vuln.get("dueDate", ""),
                    "required_action": vuln.get("requiredAction", ""),
                    "known_ransomware_use": vuln.get("knownRansomwareCampaignUse", "unknown"),
                    "notes": vuln.get("notes", ""),
                }

        _KEV_CACHE = kev_map
        _KEV_CACHE_TIME = now
        logger.info("CISA KEV catalog loaded: %d entries", len(kev_map))
        return kev_map
    except Exception as exc:
        logger.warning("Failed to load CISA KEV catalog: %s", exc)
        return _KEV_CACHE or {}


def check_kev(cve_ids: list[str]) -> list[dict]:
    """Check if CVEs are in the CISA KEV (Known Exploited Vulnerabilities) catalog.

    Returns list of KEV entries for CVEs that are actively exploited in the wild.
    These require immediate patching per CISA directive.
    """
    kev_map = _load_kev_catalog()
    results = []
    for cve_id in cve_ids:
        cve_upper = cve_id.upper()
        if cve_upper in kev_map:
            entry = kev_map[cve_upper]
            entry["in_kev"] = True
            results.append(entry)
    return results


def enrich_cves_with_kev(cves: list[dict]) -> list[dict]:
    """Add KEV status to a list of CVE dicts."""
    kev_map = _load_kev_catalog()
    for cve in cves:
        cve_id = cve.get("cve_id", "").upper()
        if cve_id in kev_map:
            kev = kev_map[cve_id]
            cve["in_kev"] = True
            cve["kev_due_date"] = kev.get("due_date")
            cve["kev_ransomware_use"] = kev.get("known_ransomware_use")
            cve["kev_required_action"] = kev.get("required_action")
        else:
            cve["in_kev"] = False
    return cves


def list_kev_by_product(product_keyword: str, limit: int = 20) -> list[dict]:
    """List KEV entries matching a product keyword (e.g., 'Chrome', 'Windows', 'Fortinet')."""
    kev_map = _load_kev_catalog()
    results = []
    keyword_lower = product_keyword.lower()
    for entry in kev_map.values():
        if keyword_lower in entry.get("product", "").lower() or keyword_lower in entry.get("vendor", "").lower():
            results.append(entry)
            if len(results) >= limit:
                break
    return results


# ===========================================================================
# 2. EPSS Scoring — Exploit Prediction Scoring System (FIRST.org)
# ===========================================================================

EPSS_API = "https://api.first.org/data/v1/epss"
_EPSS_CACHE: dict[str, dict] = {}
_EPSS_CACHE_TIME: float = 0
_EPSS_CACHE_TTL = 1800  # 30 min


def get_epss_scores(cve_ids: list[str]) -> dict[str, dict]:
    """Get EPSS scores for a list of CVE IDs.

    EPSS (Exploit Prediction Scoring System) from FIRST.org estimates the
    probability (0-1) that a vulnerability will be exploited in the wild
    within 30 days. Higher score = more likely to be exploited.

    Returns: {cve_id: {"epss": 0.95, "percentile": 0.99, "date": "2024-01-15"}}
    """
    global _EPSS_CACHE, _EPSS_CACHE_TIME
    import time

    now = time.time()
    if _EPSS_CACHE and (now - _EPSS_CACHE_TIME) > _EPSS_CACHE_TTL:
        _EPSS_CACHE = {}  # expire
        _EPSS_CACHE_TIME = now

    # Filter out cached entries
    uncached = [c for c in cve_ids if c.upper() not in _EPSS_CACHE]
    results = {}

    if uncached:
        # EPSS API supports bulk queries (up to 100 per request)
        for i in range(0, len(uncached), 100):
            batch = uncached[i:i + 100]
            params = urllib.parse.urlencode({"cve": ",".join(batch)})
            url = f"{EPSS_API}?{params}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Lucy-SecOps/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                for entry in data.get("data", []):
                    cve_id = entry.get("cve", "").upper()
                    score = {
                        "cve_id": cve_id,
                        "epss": float(entry.get("epss", 0)),
                        "percentile": float(entry.get("percentile", 0)),
                        "date": data.get("date", ""),
                    }
                    _EPSS_CACHE[cve_id] = score
                    results[cve_id] = score
            except Exception as exc:
                logger.warning("EPSS API request failed: %s", exc)

    # Return cached + fresh
    for cve_id in cve_ids:
        cve_upper = cve_id.upper()
        if cve_upper in _EPSS_CACHE:
            results[cve_upper] = _EPSS_CACHE[cve_upper]
        elif cve_upper not in results:
            results[cve_upper] = {"cve_id": cve_upper, "epss": None, "percentile": None}

    return results


def enrich_cves_with_epss(cves: list[dict]) -> list[dict]:
    """Add EPSS scores to a list of CVE dicts."""
    cve_ids = [c.get("cve_id", "") for c in cves if c.get("cve_id")]
    if not cve_ids:
        return cves

    scores = get_epss_scores(cve_ids)
    for cve in cves:
        cve_id = cve.get("cve_id", "").upper()
        if cve_id in scores:
            score = scores[cve_id]
            cve["epss"] = score.get("epss")
            cve["epss_percentile"] = score.get("percentile")
            # Risk level based on EPSS
            epss = score.get("epss") or 0
            if epss >= 0.9:
                cve["exploitation_risk"] = "critical"
            elif epss >= 0.5:
                cve["exploitation_risk"] = "high"
            elif epss >= 0.2:
                cve["exploitation_risk"] = "medium"
            elif epss > 0:
                cve["exploitation_risk"] = "low"
            else:
                cve["exploitation_risk"] = "unknown"
    return cves


def get_high_risk_cves(cve_ids: list[str], epss_threshold: float = 0.7) -> list[dict]:
    """Filter CVEs that have EPSS score above threshold (high exploitation risk)."""
    scores = get_epss_scores(cve_ids)
    high_risk = []
    for cve_id, score in scores.items():
        epss = score.get("epss") or 0
        if epss >= epss_threshold:
            high_risk.append(score)
    high_risk.sort(key=lambda x: x.get("epss", 0), reverse=True)
    return high_risk


# ===========================================================================
# 3. Exploit Availability Check — ExploitDB / Metasploit / GitHub
# ===========================================================================

EXPLOITDB_GIT_API = "https://api.github.com/search/code"
METASPloit_MODULES_URL = "https://raw.githubusercontent.com/rapid7/metasploit-framework/master/modules/exploits/"


def check_exploit_availability(cve_id: str) -> dict:
    """Check if public exploits exist for a CVE.

    Checks:
    - NVD references for exploit/exploitdb/packetstorm links
    - GitHub (search for exploit code referencing the CVE, needs GITHUB_TOKEN for reliability)
    - ExploitDB (via GitHub search in exploit-db repo)
    - Metasploit (via module naming convention)

    Returns dict with:
    - has_exploit: bool
    - sources: list of {"source": "github|exploitdb|metasploit|nvd_ref", "url": ..., "description": ...}
    - exploit_count: int
    """
    cve_lower = cve_id.lower()
    sources = []

    # 0. Check NVD references for exploit links (always works, no rate limit)
    try:
        params = urllib.parse.urlencode({"cveId": cve_id})
        url = f"{NVD_API}?{params}"
        data = _nvd_request(url)
        if data and data.get("vulnerabilities"):
            cve_data = data["vulnerabilities"][0].get("cve", {})
            refs = cve_data.get("references", [])
            for ref in refs:
                ref_url = ref.get("url", "")
                ref_tags = ref.get("tags", [])
                # Check if reference indicates an exploit
                is_exploit = (
                    any("exploit" in tag.lower() for tag in ref_tags) or
                    "exploit-db" in ref_url.lower() or
                    "packetstorm" in ref_url.lower() or
                    "metasploit" in ref_url.lower() or
                    "github.com" in ref_url.lower() and "exploit" in ref_url.lower() or
                    "seebug" in ref_url.lower() or
                    "0day" in ref_url.lower()
                )
                if is_exploit:
                    source_type = "nvd_ref"
                    if "exploit-db" in ref_url.lower():
                        source_type = "exploitdb"
                    elif "metasploit" in ref_url.lower():
                        source_type = "metasploit"
                    elif "github.com" in ref_url.lower():
                        source_type = "github"
                    sources.append({
                        "source": source_type,
                        "url": ref_url,
                        "description": f"NVD reference: {', '.join(ref_tags) if ref_tags else 'exploit reference'}",
                    })
    except Exception as exc:
        logger.debug("NVD reference check failed for %s: %s", cve_id, exc)

    # 1. Check GitHub for exploit code (needs GITHUB_TOKEN env var for reliable access)
    github_token = os.environ.get("GITHUB_TOKEN", "")
    try:
        params = urllib.parse.urlencode({
            "q": f"{cve_id} exploit language:python language:c language:cpp language:ruby language:go",
            "per_page": "5",
            "sort": "stars",
        })
        url = f"{EXPLOITDB_GIT_API}?{params}"
        headers = {
            "User-Agent": "Lucy-SecOps/1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        total_count = data.get("total_count", 0)
        if total_count > 0:
            for item in data.get("items", [])[:5]:
                repo_name = item.get("repository", {}).get("full_name", "")
                html_url = item.get("html_url", "")
                sources.append({
                    "source": "github",
                    "url": html_url,
                    "description": f"GitHub: {repo_name}",
                    "repo": repo_name,
                })
    except Exception as exc:
        logger.debug("GitHub exploit search failed for %s: %s", cve_id, exc)

    # 2. Check ExploitDB (via GitHub search in exploit-db repository)
    try:
        params = urllib.parse.urlencode({
            "q": f"{cve_id} repo:exploit-database/exploitdb",
            "per_page": "5",
        })
        url = f"{EXPLOITDB_GIT_API}?{params}"
        headers = {
            "User-Agent": "Lucy-SecOps/1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        total_count = data.get("total_count", 0)
        if total_count > 0:
            for item in data.get("items", [])[:3]:
                path = item.get("path", "")
                html_url = item.get("html_url", "")
                sources.append({
                    "source": "exploitdb",
                    "url": html_url,
                    "description": f"ExploitDB: {path}",
                    "edb_id": path.split("/")[-1].replace(".rb", "").replace(".py", "").replace(".c", ""),
                })
    except Exception as exc:
        logger.debug("ExploitDB search failed for %s: %s", cve_id, exc)

    # 3. Check Metasploit (CVE ID in module filename)
    try:
        params = urllib.parse.urlencode({
            "q": f"{cve_id} repo:rapid7/metasploit-framework path:modules/exploits",
            "per_page": "3",
        })
        url = f"{EXPLOITDB_GIT_API}?{params}"
        headers = {
            "User-Agent": "Lucy-SecOps/1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        total_count = data.get("total_count", 0)
        if total_count > 0:
            for item in data.get("items", [])[:3]:
                path = item.get("path", "")
                html_url = item.get("html_url", "")
                sources.append({
                    "source": "metasploit",
                    "url": html_url,
                    "description": f"Metasploit: {path}",
                    "module": path.split("/")[-1],
                })
    except Exception as exc:
        logger.debug("Metasploit search failed for %s: %s", cve_id, exc)

    # Deduplicate by URL
    seen_urls = set()
    unique_sources = []
    for s in sources:
        if s["url"] not in seen_urls:
            seen_urls.add(s["url"])
            unique_sources.append(s)

    return {
        "cve_id": cve_id,
        "has_exploit": len(unique_sources) > 0,
        "exploit_count": len(unique_sources),
        "sources": unique_sources,
    }


def batch_check_exploits(cve_ids: list[str]) -> list[dict]:
    """Check exploit availability for multiple CVEs."""
    results = []
    for cve_id in cve_ids[:20]:  # Limit to 20 to respect rate limits
        result = check_exploit_availability(cve_id)
        results.append(result)
    return results


def enrich_cves_with_exploits(cves: list[dict]) -> list[dict]:
    """Add exploit availability info to a list of CVE dicts."""
    for cve in cves[:20]:  # Limit to avoid rate limiting
        cve_id = cve.get("cve_id", "")
        if not cve_id:
            continue
        exploit_info = check_exploit_availability(cve_id)
        cve["has_exploit"] = exploit_info["has_exploit"]
        cve["exploit_count"] = exploit_info["exploit_count"]
        cve["exploit_sources"] = exploit_info["sources"]
    return cves


# ===========================================================================
# 4. CVE Watch & Auto-Alert — veille nouveaux CVEs sur software des agents
# ===========================================================================

import os as _os
import threading as _threading

_CVE_WATCH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_CVE_WATCH_FILE = os.path.join(_CVE_WATCH_DIR, "cve_watch.json")
_WATCH_LOCK = _threading.Lock()


def _load_watch_config() -> dict:
    """Load the CVE watch configuration."""
    try:
        if os.path.exists(_CVE_WATCH_FILE):
            with open(_CVE_WATCH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "enabled": False,
        "keywords": [],
        "products": [],
        "min_cvss": 7.0,
        "check_kev": True,
        "check_epss": True,
        "epss_threshold": 0.5,
        "last_check": None,
        "seen_cves": [],
        "agent_software": {},  # agent_id -> [{"name": ..., "version": ...}]
    }


def _save_watch_config(config: dict) -> None:
    """Save the CVE watch configuration."""
    try:
        os.makedirs(_CVE_WATCH_DIR, exist_ok=True)
        with open(_CVE_WATCH_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save CVE watch config: %s", exc)


def update_cve_watch(
    enabled: bool | None = None,
    keywords: list[str] | None = None,
    products: list[dict] | None = None,
    min_cvss: float | None = None,
    epss_threshold: float | None = None,
    agent_software: dict | None = None,
) -> dict:
    """Update CVE watch configuration.

    Args:
        enabled: Enable/disable the watch
        keywords: List of keywords to monitor (e.g., ["Windows LSASS", "Chrome"])
        products: List of {name, version} to monitor
        min_cvss: Minimum CVSS score to alert on
        epss_threshold: Minimum EPSS score to alert on
        agent_software: {agent_id: [{"name": ..., "version": ...}]}
    """
    with _WATCH_LOCK:
        config = _load_watch_config()
        if enabled is not None:
            config["enabled"] = enabled
        if keywords is not None:
            config["keywords"] = keywords
        if products is not None:
            config["products"] = products
        if min_cvss is not None:
            config["min_cvss"] = min_cvss
        if epss_threshold is not None:
            config["epss_threshold"] = epss_threshold
        if agent_software is not None:
            config["agent_software"] = agent_software
        _save_watch_config(config)
        return config


def run_cve_watch_check() -> dict:
    """Run a CVE watch check: search for new CVEs matching watch criteria.

    Returns dict with:
    - new_cves: list of new CVEs matching criteria
    - kev_matches: CVEs in CISA KEV catalog
    - high_epss: CVEs with high EPSS scores
    - total_checked: number of keywords/products checked
    """
    config = _load_watch_config()
    if not config.get("enabled"):
        return {"status": "disabled", "new_cves": [], "total_checked": 0}

    seen = set(config.get("seen_cves", []))
    min_cvss = config.get("min_cvss", 7.0)
    epss_threshold = config.get("epss_threshold", 0.5)
    all_new_cves = []
    total_checked = 0

    # Search by keywords
    for keyword in config.get("keywords", [])[:10]:
        total_checked += 1
        cves = search_cve_by_keyword(keyword, limit=20)
        for cve in cves:
            cve_id = cve.get("cve_id", "")
            if cve_id in seen:
                continue
            cvss = cve.get("cvss", 0)
            if cvss >= min_cvss:
                all_new_cves.append(cve)
                seen.add(cve_id)

    # Search by products
    for product in config.get("products", [])[:10]:
        total_checked += 1
        name = product.get("name", "")
        version = product.get("version", "")
        keyword = f"{name} {version}".strip()
        cves = search_cve_by_keyword(keyword, limit=10)
        for cve in cves:
            cve_id = cve.get("cve_id", "")
            if cve_id in seen:
                continue
            cvss = cve.get("cvss", 0)
            if cvss >= min_cvss:
                cve["monitored_product"] = name
                all_new_cves.append(cve)
                seen.add(cve_id)

    # Search by agent software
    for agent_id, sw_list in config.get("agent_software", {}).items():
        for sw in sw_list[:5]:
            total_checked += 1
            name = sw.get("name", "")
            version = sw.get("version", "")
            keyword = f"{name} {version}".strip()
            cves = search_cve_by_keyword(keyword, limit=5)
            for cve in cves:
                cve_id = cve.get("cve_id", "")
                if cve_id in seen:
                    continue
                cvss = cve.get("cvss", 0)
                if cvss >= min_cvss:
                    cve["agent_id"] = agent_id
                    cve["monitored_product"] = name
                    all_new_cves.append(cve)
                    seen.add(cve_id)

    # Enrich with KEV
    kev_matches = []
    if config.get("check_kev", True) and all_new_cves:
        cve_ids = [c["cve_id"] for c in all_new_cves]
        kev_matches = check_kev(cve_ids)
        for cve in all_new_cves:
            for kev in kev_matches:
                if cve["cve_id"].upper() == kev["cve_id"].upper():
                    cve["in_kev"] = True
                    cve["kev_due_date"] = kev.get("due_date")
                    break

    # Enrich with EPSS
    high_epss = []
    if config.get("check_epss", True) and all_new_cves:
        cve_ids = [c["cve_id"] for c in all_new_cves]
        epss_scores = get_epss_scores(cve_ids)
        for cve in all_new_cves:
            cve_upper = cve["cve_id"].upper()
            if cve_upper in epss_scores:
                epss = epss_scores[cve_upper].get("epss") or 0
                cve["epss"] = epss
                if epss >= epss_threshold:
                    high_epss.append({
                        "cve_id": cve["cve_id"],
                        "epss": epss,
                        "percentile": epss_scores[cve_upper].get("percentile"),
                        "cvss": cve.get("cvss", 0),
                    })

    # Check exploit availability for top CVEs
    for cve in all_new_cves[:10]:
        try:
            exploit_info = check_exploit_availability(cve["cve_id"])
            cve["has_exploit"] = exploit_info["has_exploit"]
            cve["exploit_count"] = exploit_info["exploit_count"]
        except Exception:
            cve["has_exploit"] = False
            cve["exploit_count"] = 0

    # Update config with seen CVEs and last check time
    with _WATCH_LOCK:
        config = _load_watch_config()
        config["seen_cves"] = list(seen)[-500:]  # Keep last 500
        config["last_check"] = datetime.now(timezone.utc).isoformat()
        _save_watch_config(config)

    # Sort by CVSS descending
    all_new_cves.sort(key=lambda x: x.get("cvss", 0), reverse=True)

    return {
        "status": "ok",
        "new_cves": all_new_cves,
        "new_count": len(all_new_cves),
        "kev_matches": kev_matches,
        "high_epss": high_epss,
        "total_checked": total_checked,
        "last_check": config["last_check"],
    }


def get_cve_watch_status() -> dict:
    """Get current CVE watch configuration and status."""
    config = _load_watch_config()
    return {
        "enabled": config.get("enabled", False),
        "keywords": config.get("keywords", []),
        "products": config.get("products", []),
        "min_cvss": config.get("min_cvss", 7.0),
        "epss_threshold": config.get("epss_threshold", 0.5),
        "check_kev": config.get("check_kev", True),
        "check_epss": config.get("check_epss", True),
        "last_check": config.get("last_check"),
        "seen_cves_count": len(config.get("seen_cves", [])),
        "monitored_agents": len(config.get("agent_software", {})),
    }


# ===========================================================================
# Full enrichment pipeline — combine all sources
# ===========================================================================


def full_cve_enrichment(cves: list[dict]) -> list[dict]:
    """Full enrichment pipeline: KEV + EPSS + Exploit availability.

    Transforms a list of basic CVE dicts into fully enriched entries with:
    - in_kev: bool (CISA Known Exploited Vulnerabilities)
    - kev_due_date: str (CISA remediation deadline)
    - kev_ransomware_use: str (known ransomware exploitation)
    - epss: float (exploitation probability 0-1)
    - epss_percentile: float (relative exploitation risk)
    - exploitation_risk: str (critical|high|medium|low|unknown)
    - has_exploit: bool (public exploit code exists)
    - exploit_count: int
    - exploit_sources: list (GitHub/ExploitDB/Metasploit links)
    """
    if not cves:
        return cves

    # Step 1: KEV enrichment
    cves = enrich_cves_with_kev(cves)

    # Step 2: EPSS enrichment
    cves = enrich_cves_with_epss(cves)

    # Step 3: Exploit availability (limit to top 20 by CVSS to respect rate limits)
    sorted_cves = sorted(cves, key=lambda x: x.get("cvss", 0), reverse=True)
    for cve in sorted_cves[:20]:
        cve_id = cve.get("cve_id", "")
        if not cve_id:
            continue
        try:
            exploit_info = check_exploit_availability(cve_id)
            cve["has_exploit"] = exploit_info["has_exploit"]
            cve["exploit_count"] = exploit_info["exploit_count"]
            cve["exploit_sources"] = exploit_info["sources"]
        except Exception:
            cve["has_exploit"] = False
            cve["exploit_count"] = 0
            cve["exploit_sources"] = []

    # Compute combined risk score
    for cve in cves:
        cvss = cve.get("cvss", 0)
        epss = cve.get("epss") or 0
        in_kev = cve.get("in_kev", False)
        has_exploit = cve.get("has_exploit", False)

        # Combined risk: weighted score
        risk_score = cvss * 10  # 0-100 base
        if in_kev:
            risk_score += 30  # Actively exploited = major boost
        if has_exploit:
            risk_score += 20  # Public exploit code = boost
        risk_score += epss * 20  # EPSS adds 0-20
        risk_score = min(risk_score, 100)

        cve["combined_risk_score"] = round(risk_score, 1)

        if risk_score >= 80:
            cve["priority"] = "immediate"
        elif risk_score >= 60:
            cve["priority"] = "high"
        elif risk_score >= 40:
            cve["priority"] = "medium"
        else:
            cve["priority"] = "low"

    return cves

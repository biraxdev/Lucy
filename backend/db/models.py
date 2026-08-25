"""
Peewee ORM models for Project Lucy — all tables with full fields,
JSON helpers, and Agent crypto methods.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
    UUIDField,
)

from database import database

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class BaseModel(Model):
    class Meta:
        database = database

    def to_dict(self) -> dict[str, Any]:
        return self.__data__.copy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_loads(value: Optional[str]) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


# ---------------------------------------------------------------------------
# Tenant — isolated Red Team workspace
# ---------------------------------------------------------------------------


class Tenant(BaseModel):
    """Isolated Red Team workspace. All resources are scoped per tenant."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=128, unique=True)
    description = TextField(null=True)
    slug = CharField(max_length=32, unique=True)  # short identifier e.g. "team-alpha"
    color = CharField(max_length=16, default="#6366f1")  # UI accent
    active = BooleanField(default=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "tenants"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        return d


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(BaseModel):
    """Operator accounts for the admin panel."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    username = CharField(unique=True, max_length=64)
    password_hash = CharField(max_length=128)
    role = CharField(max_length=16, default="viewer")  # superadmin | admin | operator | viewer
    tenant = ForeignKeyField("self", null=True, column_name="tenant_id", backref="+")  # null = superadmin
    api_key = CharField(max_length=64, null=True, index=True)
    totp_secret = CharField(max_length=64, null=True)
    totp_enabled = BooleanField(default=False)
    last_login = DateTimeField(null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "users"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.pop("password_hash", None)
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        return d


# ---------------------------------------------------------------------------
# Agent Group
# ---------------------------------------------------------------------------


class AgentGroup(BaseModel):
    """Static or dynamic collection of agents."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="groups", column_name="tenant_id")
    name = CharField(max_length=64)
    description = TextField(null=True)
    type = CharField(max_length=16, default="static")  # static | dynamic
    members = TextField(null=True)        # JSON array of agent ID strings
    dynamic_query = TextField(null=True)
    color = CharField(max_length=16, default="#22c55e")  # hex color for UI
    tags = TextField(null=True)           # JSON array
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "agent_groups"

    @property
    def members_list(self) -> list:
        return _json_loads(self.members) or []

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @tags_list.setter
    def tags_list(self, value: list) -> None:
        self.tags = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["members"] = self.members_list
        d["tags"] = self.tags_list
        return d


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class Agent(BaseModel):
    """Registered implant running on a target machine."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="agents", column_name="tenant_id")
    hostname = CharField(max_length=128)
    os = CharField(max_length=32)  # windows | linux | darwin
    username = CharField(max_length=64)
    ip_public = CharField(max_length=64, null=True)
    ip_private = CharField(max_length=64, null=True)
    architecture = CharField(max_length=16, null=True)  # x86_64 | arm64
    processor = CharField(max_length=256, null=True)
    ram_total = IntegerField(null=True)      # bytes
    ram_available = IntegerField(null=True)  # bytes
    cpu_percent = FloatField(null=True)      # 0-100, last reported by agent heartbeat
    first_seen = DateTimeField(default=lambda: datetime.now(timezone.utc))
    last_seen = DateTimeField(default=lambda: datetime.now(timezone.utc))
    status = CharField(max_length=16, default="offline")  # online|idle|offline|compromised
    public_key = TextField(null=True)   # PEM — ECDH P-256 agent public key
    aes_key = TextField(null=True)      # AES-256-GCM encrypted session key (stored encrypted)
    group = ForeignKeyField(AgentGroup, null=True, backref="agents", column_name="group_id")
    tags = TextField(null=True)         # JSON array
    metadata = TextField(null=True)   # JSON object (key-value metadata)

    class Meta:
        table_name = "agents"

    # --- JSON helpers ---

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @tags_list.setter
    def tags_list(self, value: list) -> None:
        self.tags = _json_dumps(value)

    @property
    def metadata_dict(self) -> dict:
        return _json_loads(self.metadata) or {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self.metadata = _json_dumps(value)

    # --- Crypto helpers ---

    def _get_aes_key_bytes(self) -> bytes:
        """Retrieve the raw AES session key for this agent from memory/db."""
        if not self.aes_key:
            raise ValueError(f"No AES key available for agent {self.id}")
        import base64
        return base64.b64decode(self.aes_key)

    def encrypt_for_agent(self, plaintext: bytes) -> bytes:
        """AES-256-GCM encrypt a payload destined for this agent."""
        from core.crypto import encrypt
        aes_key = self._get_aes_key_bytes()
        result = encrypt(plaintext, aes_key)
        return result.encode("utf-8")

    def decrypt_from_agent(self, ciphertext: bytes) -> bytes:
        """AES-256-GCM decrypt a payload received from this agent."""
        from core.crypto import decrypt
        aes_key = self._get_aes_key_bytes()
        cipher_b64 = ciphertext.decode("utf-8") if isinstance(ciphertext, bytes) else ciphertext
        return decrypt(cipher_b64, aes_key)

    # --- Serialization ---

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["group_id"] = str(self.group_id) if self.group_id else None
        d["tags"] = self.tags_list
        d["metadata"] = self.metadata_dict
        d.pop("aes_key", None)  # never expose session key
        return d


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


class Task(BaseModel):
    """Unit of work dispatched to an agent."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="tasks", column_name="tenant_id")
    agent = ForeignKeyField(Agent, backref="tasks", column_name="agent_id")
    module = CharField(max_length=64)
    action = CharField(max_length=64)
    params = TextField(null=True)   # JSON dict
    status = CharField(max_length=16, default="queued")  # queued|running|completed|failed
    priority = CharField(max_length=8, default="normal")  # critical|high|normal|low
    result = TextField(null=True)   # JSON blob
    error = TextField(null=True)
    timeline_id = CharField(max_length=64, null=True, index=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    executed_at = DateTimeField(null=True)

    class Meta:
        table_name = "tasks"

    @property
    def params_dict(self) -> dict:
        return _json_loads(self.params) or {}

    @params_dict.setter
    def params_dict(self, value: dict) -> None:
        self.params = _json_dumps(value)

    @property
    def result_dict(self) -> Any:
        return _json_loads(self.result)

    @result_dict.setter
    def result_dict(self, value: Any) -> None:
        self.result = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["agent_id"] = str(self.agent_id)
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["timeline_id"] = self.timeline_id
        d["params"] = self.params_dict
        d["result"] = self.result_dict
        return d


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------


class Module(BaseModel):
    """Downloadable plugin — executed by agent at runtime."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=64, unique=True)
    version = CharField(max_length=16)
    description = TextField(null=True)
    author = CharField(max_length=64, null=True)
    code = TextField()                   # Python source
    dependencies = TextField(null=True)  # JSON array: ["Pillow>=10.0"]
    os_compat = TextField(null=True)     # JSON array: ["windows","linux","darwin"]
    # ---- Plug-and-play descriptor fields ----
    actions = TextField(null=True)          # JSON list of available actions
    params_schema = TextField(null=True)    # JSON schema for action params
    category = CharField(max_length=32, null=True)  # recon, credentials, persistence, ...
    mitre_techniques = TextField(null=True) # JSON list of MITRE technique IDs
    tags = TextField(null=True)             # JSON list of tags
    inputs = TextField(null=True)           # JSON list of expected inputs
    outputs = TextField(null=True)          # JSON list of produced outputs
    expected_duration = IntegerField(null=True)  # estimated duration in seconds
    # -----------------------------------------
    signature = CharField(max_length=128)  # HMAC-SHA256 of code
    enabled = BooleanField(default=True)
    install_count = IntegerField(default=0)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "modules"

    @property
    def dependencies_list(self) -> list:
        return _json_loads(self.dependencies) or []

    @property
    def os_compat_list(self) -> list:
        return _json_loads(self.os_compat) or []

    @property
    def actions_list(self) -> list:
        return _json_loads(self.actions) or []

    @property
    def params_schema_dict(self) -> dict:
        return _json_loads(self.params_schema) or {}

    @property
    def mitre_list(self) -> list:
        return _json_loads(self.mitre_techniques) or []

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @property
    def inputs_list(self) -> list:
        return _json_loads(self.inputs) or []

    @property
    def outputs_list(self) -> list:
        return _json_loads(self.outputs) or []

    def verify_signature(self, hmac_key: bytes) -> bool:
        from core.crypto import verify_signature
        return verify_signature(self.code.encode("utf-8"), self.signature, hmac_key)

    def to_dict(self, include_code: bool = False) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["dependencies"] = self.dependencies_list
        d["os_compat"] = self.os_compat_list
        d["actions"] = self.actions_list
        d["params_schema"] = self.params_schema_dict
        d["category"] = self.category
        d["mitre_techniques"] = self.mitre_list
        d["tags"] = self.tags_list
        d["inputs"] = self.inputs_list
        d["outputs"] = self.outputs_list
        d["expected_duration"] = self.expected_duration
        if not include_code:
            d.pop("code", None)
        return d


# ---------------------------------------------------------------------------
# PocTemplate — documented proof-of-concept playbook
# ---------------------------------------------------------------------------


class PocTemplate(BaseModel):
    """A documented proof-of-concept chain of module steps."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    puid = CharField(max_length=64, unique=True, index=True)  # stable id e.g. "op_nightshade"
    name = CharField(max_length=256)
    description = TextField(null=True)
    icon = CharField(max_length=8, default="🛡")
    category = CharField(max_length=32, default="full")  # recon, credentials, persistence, lateral, exfil, simulation, full
    trigger = CharField(max_length=16, default="manual")  # manual | on_connect | schedule(cron)
    agent_group = TextField(null=True)  # JSON array of group IDs or ["all"]
    mitre_techniques = TextField(null=True)  # JSON list of MITRE technique IDs
    tags = TextField(null=True)  # JSON list
    phases = TextField(null=True)  # JSON list of {label, steps: [int]}
    steps = TextField(null=True)  # JSON list of TimelineStep with action descriptions
    source_file = CharField(max_length=256, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "poc_templates"

    @property
    def agent_group_list(self) -> list:
        return _json_loads(self.agent_group) or ["all"]

    @property
    def mitre_list(self) -> list:
        return _json_loads(self.mitre_techniques) or []

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @property
    def phases_list(self) -> list:
        return _json_loads(self.phases) or []

    @property
    def steps_list(self) -> list[dict]:
        return _json_loads(self.steps) or []

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["agent_group"] = self.agent_group_list
        d["mitre_techniques"] = self.mitre_list
        d["tags"] = self.tags_list
        d["phases"] = self.phases_list
        d["steps"] = self.steps_list
        return d


# ---------------------------------------------------------------------------
# BuildPack — preset agent build configuration
# ---------------------------------------------------------------------------


class BuildPack(BaseModel):
    """A reusable agent build preset: modules + build options."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    bpid = CharField(max_length=64, unique=True, index=True)  # stable id e.g. "recon"
    name = CharField(max_length=128)
    description = TextField(null=True)
    icon = CharField(max_length=8, default="📦")
    tags = TextField(null=True)  # JSON list
    modules = TextField(null=True)  # JSON list of module names
    build_options = TextField(null=True)  # JSON dict of BuildRequest overrides
    source_file = CharField(max_length=256, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "build_packs"

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @property
    def modules_list(self) -> list:
        return _json_loads(self.modules) or []

    @property
    def build_options_dict(self) -> dict:
        return _json_loads(self.build_options) or {}

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tags"] = self.tags_list
        d["modules"] = self.modules_list
        d["build_options"] = self.build_options_dict
        return d


# ---------------------------------------------------------------------------
# Credential
# ---------------------------------------------------------------------------


class Credential(BaseModel):
    """Harvested credential from an agent module."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="credentials", column_name="tenant_id")
    agent = ForeignKeyField(Agent, backref="credentials", column_name="agent_id")
    url = TextField(null=True)
    hostname = CharField(max_length=256, null=True)
    username = CharField(max_length=256)
    password_encrypted = TextField()         # AES-256-GCM encrypted
    source = CharField(max_length=32)        # browser|wifi|ssh|rdp|system
    confidence = CharField(max_length=8, default="medium")  # high|medium|low
    tags = TextField(null=True)              # JSON array e.g. ["domain_admin","weak"]
    metadata = TextField(null=True)          # JSON object (key-value metadata)
    captured_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    version = IntegerField(default=1)
    dedup_hash = CharField(max_length=64, null=True, index=True)  # SHA256(url+username)

    class Meta:
        table_name = "credentials"

    @staticmethod
    def compute_dedup_hash(url: Optional[str], username: str) -> str:
        raw = f"{url or ''}:{username}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @tags_list.setter
    def tags_list(self, value: list) -> None:
        self.tags = _json_dumps(value)

    @property
    def metadata_dict(self) -> dict:
        return _json_loads(self.metadata) or {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self.metadata = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["agent_id"] = str(self.agent_id)
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["tags"] = self.tags_list
        d["metadata"] = self.metadata_dict
        d.pop("password_encrypted", None)  # never expose in list views
        return d

    def to_dict_full(self, master_key: bytes) -> dict[str, Any]:
        """Include decrypted password — use only for detail endpoint."""
        from core.crypto import decrypt
        d = self.to_dict()
        try:
            d["password"] = decrypt(self.password_encrypted, master_key).decode("utf-8")
        except Exception:
            d["password"] = None
        return d


# ---------------------------------------------------------------------------
# FileEvent
# ---------------------------------------------------------------------------


class FileEvent(BaseModel):
    """Record of a file operation performed by an agent."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    agent = ForeignKeyField(Agent, backref="file_events", column_name="agent_id")
    path = TextField()
    action = CharField(max_length=16)  # upload|download|delete|modify|list
    size = IntegerField(null=True)     # bytes
    hash = CharField(max_length=64, null=True)  # SHA-256
    timestamp = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "file_events"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["agent_id"] = str(self.agent_id)
        return d


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------


class Log(BaseModel):
    """Centralized log entry from backend, agent, or module."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="logs", column_name="tenant_id")
    agent = ForeignKeyField(Agent, null=True, backref="logs", column_name="agent_id")
    level = CharField(max_length=8)    # DEBUG|INFO|WARN|ERROR|CRITICAL
    module = CharField(max_length=64)  # source component
    message = TextField()
    log_type = CharField(max_length=16, default="system")  # system|agent|task|module|security
    timestamp = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "logs"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["agent_id"] = str(self.agent_id) if self.agent_id else None
        return d


# ---------------------------------------------------------------------------
# RefreshToken
# ---------------------------------------------------------------------------


class RefreshToken(BaseModel):
    """Stored refresh tokens for JWT rotation."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user = ForeignKeyField(User, backref="refresh_tokens", column_name="user_id")
    token_hash = CharField(max_length=128, unique=True)  # SHA-256 of the raw token
    expires_at = DateTimeField()
    revoked = BooleanField(default=False)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "refresh_tokens"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def is_valid(self) -> bool:
        if self.revoked:
            return False
        expires = self.expires_at
        if isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires)
            except ValueError:
                return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < expires


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class Timeline(BaseModel):
    """Ordered attack chain — sequence of module steps."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="timelines", column_name="tenant_id")
    name = CharField(max_length=128)
    description = TextField(null=True)
    agent_group = TextField(null=True)  # JSON array of group IDs or ["all"]
    steps = TextField(null=True)        # JSON array of TaskStep objects
    trigger = CharField(max_length=16, default="manual")  # manual|on_connect|schedule
    cron_expr = CharField(max_length=64, null=True)
    loop = IntegerField(default=0)      # 0 = disabled, N = repeat every N seconds
    status = CharField(max_length=16, default="draft")  # draft|active|completed|failed
    created_by = ForeignKeyField(User, null=True, backref="timelines", column_name="created_by")
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "timelines"

    @property
    def steps_list(self) -> list[dict]:
        return _json_loads(self.steps) or []

    @steps_list.setter
    def steps_list(self, value: list[dict]) -> None:
        self.steps = _json_dumps(value)

    @property
    def agent_group_list(self) -> list:
        return _json_loads(self.agent_group) or ["all"]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["created_by"] = str(self.created_by_id) if self.created_by_id else None
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["steps"] = self.steps_list
        d["agent_group"] = self.agent_group_list
        return d


# ---------------------------------------------------------------------------
# Finding — manual security finding tracker
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="findings", column_name="tenant_id")
    title = CharField(max_length=256)
    severity = CharField(max_length=16, default="high")  # critical|high|medium|low|info
    status = CharField(max_length=32, default="draft")   # draft|reviewed|accepted|mitigated|false_positive
    description = TextField(null=True)
    recommendation = TextField(null=True)
    evidence = TextField(null=True)
    cvss = CharField(max_length=8, null=True)    # stored as string "7.5"
    agent_id = CharField(max_length=64, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "findings"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["cvss"] = float(d["cvss"]) if d.get("cvss") else None
        return d


# ---------------------------------------------------------------------------
# AlertEvent — persisted alert log
# ---------------------------------------------------------------------------


class AlertEvent(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="alert_events", column_name="tenant_id")
    event = CharField(max_length=64)
    title = CharField(max_length=256)
    message = TextField()
    severity = CharField(max_length=16, default="info")  # info | warning | critical
    agent_id = CharField(max_length=64, null=True)
    data = TextField(null=True)
    read = BooleanField(default=False)
    timestamp = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "alert_events"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["data"] = _json_loads(d.get("data")) or {}
        return d


# ---------------------------------------------------------------------------
# AlertWebhook — configured webhook destinations
# ---------------------------------------------------------------------------


class AlertWebhook(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=128)
    url = TextField()
    kind = CharField(max_length=16, default="generic")  # slack | discord | generic
    enabled = BooleanField(default=True)
    min_severity = CharField(max_length=16, default="info")
    events = TextField(null=True)   # JSON list of event types, empty = all
    secret = CharField(max_length=256, null=True)
    template = TextField(null=True)  # Jinja2 template override for the payload
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "alert_webhooks"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["events"] = _json_loads(d.get("events")) or []
        d["template"] = d.get("template")
        return d


# ---------------------------------------------------------------------------
# AuditTrail — blockchain-like immutable event log
# ---------------------------------------------------------------------------


class AuditTrail(BaseModel):
    """Tamper-evident audit log: each entry links to the previous hash."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="audit_events", column_name="tenant_id")
    timestamp = DateTimeField(default=lambda: datetime.now(timezone.utc))
    action = CharField(max_length=64)          # e.g. login, task_created, agent_registered
    actor = CharField(max_length=128)          # username, agent_id, or "system"
    resource_type = CharField(max_length=64, null=True)  # agent, task, credential, user
    resource_id = CharField(max_length=128, null=True)
    details = TextField(null=True)             # JSON blob
    previous_hash = CharField(max_length=64, default="0" * 64)
    current_hash = CharField(max_length=64)

    class Meta:
        table_name = "audit_trail"
        indexes = (
            (("tenant", "timestamp"), False),
            (("resource_type", "resource_id"), False),
        )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["details"] = _json_loads(self.details)
        ts = self.timestamp
        if isinstance(ts, str):
            d["timestamp"] = ts
        elif ts:
            d["timestamp"] = ts.isoformat()
        else:
            d["timestamp"] = None
        return d


# ---------------------------------------------------------------------------
# ChatMessage — persisted chat/event translation layer
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A chat message or persona-translated event displayed to operators."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="chat_messages", column_name="tenant_id")
    user = ForeignKeyField(User, null=True, backref="chat_messages", column_name="user_id")
    role = CharField(max_length=16, default="assistant")  # user|assistant|system|event
    content = TextField()                     # persona/translated text shown in UI
    raw_payload = TextField(null=True)        # original technical payload (JSON)
    source_event_type = CharField(max_length=32, null=True)  # heartbeat|result|log|agent_connected|...
    channel = CharField(max_length=64, default="global", index=True)  # global|group:{id}
    agent_id = CharField(max_length=64, null=True)
    task_id = CharField(max_length=64, null=True)
    metadata = TextField(null=True)           # JSON object for UI hints (mood, avatar, raw_toggle)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "chat_messages"

    @property
    def metadata_dict(self) -> dict:
        return _json_loads(self.metadata) or {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self.metadata = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["user_id"] = str(self.user_id) if self.user_id else None
        d["metadata"] = self.metadata_dict
        d["raw_payload"] = _json_loads(self.raw_payload)
        return d


# ---------------------------------------------------------------------------
# Strategy / TTP data (MITRE ATT&CK-style + operator playbooks)
# ---------------------------------------------------------------------------


class Tactic(BaseModel):
    """High-level ATT&CK tactic / phase of an engagement."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="tactics", column_name="tenant_id")
    mitre_id = CharField(max_length=16, null=True, index=True)  # e.g. TA0001
    name = CharField(max_length=128)
    phase = CharField(max_length=64, null=True)  # e.g. Initial Access
    description = TextField(null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "tactics"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        return d


class Technique(BaseModel):
    """ATT&CK technique mapped to tasks, findings, and playbooks."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="techniques", column_name="tenant_id")
    mitre_id = CharField(max_length=16, null=True, index=True)  # e.g. T1059
    name = CharField(max_length=256)
    tactic = ForeignKeyField(Tactic, null=True, backref="techniques", column_name="tactic_id")
    description = TextField(null=True)
    platform = CharField(max_length=64, null=True)  # windows|linux|darwin|all
    data_sources = TextField(null=True)  # JSON list
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "techniques"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["tactic_id"] = str(self.tactic_id) if self.tactic_id else None
        d["data_sources"] = _json_loads(self.data_sources)
        return d


class Campaign(BaseModel):
    """Container for an engagement: target, agents, timelines, findings."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="campaigns", column_name="tenant_id")
    name = CharField(max_length=128)
    description = TextField(null=True)
    objective = CharField(max_length=256, null=True)
    status = CharField(max_length=16, default="active")  # active|paused|completed|archived
    start_date = DateTimeField(null=True)
    end_date = DateTimeField(null=True)
    metadata = TextField(null=True)  # JSON
    # Case management fields
    case_number = CharField(max_length=32, null=True, unique=False)
    priority = CharField(max_length=16, default="normal")  # low|normal|high|critical
    assigned_to = CharField(max_length=64, null=True)  # operator username
    due_date = DateTimeField(null=True)
    tags = TextField(null=True)  # JSON array
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "campaigns"

    @property
    def metadata_dict(self) -> dict:
        return _json_loads(self.metadata) or {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self.metadata = _json_dumps(value)

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @tags_list.setter
    def tags_list(self, value: list) -> None:
        self.tags = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["metadata"] = self.metadata_dict
        d["tags"] = self.tags_list
        return d


class Playbook(BaseModel):
    """Reusable sequence of steps aligned to techniques."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="playbooks", column_name="tenant_id")
    name = CharField(max_length=128)
    description = TextField(null=True)
    technique_ids = TextField(null=True)  # JSON list of Technique UUID strings
    steps = TextField(null=True)  # JSON list of {module, action, params, delay}
    tags = TextField(null=True)  # JSON list
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "playbooks"

    @property
    def technique_ids_list(self) -> list:
        return _json_loads(self.technique_ids) or []

    @technique_ids_list.setter
    def technique_ids_list(self, value: list) -> None:
        self.technique_ids = _json_dumps(value)

    @property
    def steps_list(self) -> list:
        return _json_loads(self.steps) or []

    @steps_list.setter
    def steps_list(self, value: list) -> None:
        self.steps = _json_dumps(value)

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @tags_list.setter
    def tags_list(self, value: list) -> None:
        self.tags = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["technique_ids"] = self.technique_ids_list
        d["steps"] = self.steps_list
        d["tags"] = self.tags_list
        return d


class AgentNote(BaseModel):
    """Operator observations about an agent or target."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="agent_notes", column_name="tenant_id")
    agent = ForeignKeyField(Agent, null=True, backref="notes", column_name="agent_id")
    user = ForeignKeyField(User, null=True, backref="agent_notes", column_name="user_id")
    content = TextField()
    category = CharField(max_length=32, default="observation")  # observation|ioc|remediation|objective
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "agent_notes"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["agent_id"] = str(self.agent_id) if self.agent_id else None
        d["user_id"] = str(self.user_id) if self.user_id else None
        return d


# ---------------------------------------------------------------------------
# C2Profile — malleable C2 profile for agent builds
# ---------------------------------------------------------------------------


class C2Profile(BaseModel):
    """A malleable C2 profile that shapes agent HTTP traffic."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="c2_profiles", column_name="tenant_id")
    name = CharField(max_length=128, unique=True)
    http_get_uri = CharField(max_length=256, default="/api/v1/agents/{agent_id}/tasks")
    http_post_uri = CharField(max_length=256, default="/api/v1/tasks/{task_id}/result")
    http_get_verb = CharField(max_length=16, default="GET")
    http_post_verb = CharField(max_length=16, default="POST")
    user_agent = TextField(default="")
    custom_headers = TextField(null=True)   # JSON dict
    cookie_name = CharField(max_length=64, default="")
    stage_uri = CharField(max_length=256, default="/api/v1/stage")
    jitter_seconds = CharField(max_length=16, default="2.0")
    max_retries = IntegerField(default=5)
    ssl_cert_hash = CharField(max_length=128, default="")
    redirector_url = CharField(max_length=256, default="")
    domain_front_host = CharField(max_length=256, default="")
    body_encoding = CharField(max_length=32, default="json")
    data_param = CharField(max_length=32, default="d")
    task_param = CharField(max_length=32, default="t")
    is_active = BooleanField(default=False)
    is_builtin = BooleanField(default=False)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "c2_profiles"

    @property
    def custom_headers_dict(self) -> dict:
        return _json_loads(self.custom_headers) or {}

    @custom_headers_dict.setter
    def custom_headers_dict(self, value: dict) -> None:
        self.custom_headers = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["custom_headers"] = self.custom_headers_dict
        try:
            d["jitter_seconds"] = float(self.jitter_seconds)
        except (TypeError, ValueError):
            d["jitter_seconds"] = 2.0
        return d


# ---------------------------------------------------------------------------
# Redirector — C2 traffic redirector configuration
# ---------------------------------------------------------------------------


class Redirector(BaseModel):
    """A C2 redirector configuration (nginx/apache fronting the C2)."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="redirectors", column_name="tenant_id")
    name = CharField(max_length=128)
    frontend_domain = CharField(max_length=256)
    backend_host = CharField(max_length=256)
    backend_port = IntegerField(default=8000)
    ssl_enabled = BooleanField(default=True)
    domain_front_host = CharField(max_length=256, default="")
    cdn_provider = CharField(max_length=64, default="")
    listen_port = IntegerField(default=443)
    extra_config = TextField(null=True)  # JSON dict of additional nginx/apache directives
    active = BooleanField(default=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "redirectors"

    @property
    def extra_config_dict(self) -> dict:
        return _json_loads(self.extra_config) or {}

    @extra_config_dict.setter
    def extra_config_dict(self, value: dict) -> None:
        self.extra_config = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["extra_config"] = self.extra_config_dict
        return d


# ---------------------------------------------------------------------------
# Evidence — encrypted evidence storage with hash verification
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """Tamper-evident evidence storage: screenshots, files, memory dumps, etc."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="evidence", column_name="tenant_id")
    agent_id = CharField(max_length=64, null=True)
    task_id = CharField(max_length=64, null=True)
    finding_id = CharField(max_length=64, null=True)
    campaign_id = CharField(max_length=64, null=True)
    name = CharField(max_length=256)
    type = CharField(max_length=32, default="file")  # file|screenshot|dump|network|log
    mime_type = CharField(max_length=128, null=True)
    size = IntegerField(default=0)
    sha256 = CharField(max_length=64, index=True)
    md5 = CharField(max_length=32, null=True)
    storage_path = CharField(max_length=512, null=True)  # relative path in evidence vault
    encrypted = BooleanField(default=True)
    description = TextField(null=True)
    collected_by = CharField(max_length=64, null=True)  # operator username
    collected_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    chain_hash = CharField(max_length=64, default="0" * 64)  # links to previous evidence

    class Meta:
        table_name = "evidence"
        indexes = (
            (("agent_id", "collected_at"), False),
            (("campaign_id",), False),
        )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        return d


# ---------------------------------------------------------------------------
# DetectionRule — auto-generated Sigma/YARA/Snort detection rules
# ---------------------------------------------------------------------------


class DetectionRule(BaseModel):
    """Detection rule generated from findings or manually created."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="detection_rules", column_name="tenant_id")
    title = CharField(max_length=256)
    description = TextField(null=True)
    rule_type = CharField(max_length=16, default="sigma")  # sigma|yara|snort|splunk|elastic
    rule_content = TextField()  # the actual rule YAML/text
    severity = CharField(max_length=16, default="high")
    status = CharField(max_length=16, default="draft")  # draft|active|deprecated|false_positive
    mitre_technique = CharField(max_length=32, null=True)  # e.g. T1003.001
    finding_id = CharField(max_length=64, null=True)  # source finding if auto-generated
    tags = TextField(null=True)  # JSON array
    created_by = CharField(max_length=64, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "detection_rules"

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["tags"] = _json_loads(self.tags) or []
        return d


# ---------------------------------------------------------------------------
# OperatorActivity — granular operator action tracking (complements AuditTrail)
# ---------------------------------------------------------------------------


class OperatorActivity(BaseModel):
    """Granular operator activity log for session reconstruction and accountability."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="operator_activities", column_name="tenant_id")
    operator = CharField(max_length=64)  # username
    session_id = CharField(max_length=64, null=True)  # login session
    action = CharField(max_length=64)  # login|logout|task_dispatch|mission_start|finding_update|...
    target_type = CharField(max_length=32, null=True)  # agent|task|finding|campaign|credential
    target_id = CharField(max_length=128, null=True)
    target_name = CharField(max_length=256, null=True)  # human-readable target name
    ip_address = CharField(max_length=45, null=True)
    user_agent = CharField(max_length=256, null=True)
    details = TextField(null=True)  # JSON
    success = BooleanField(default=True)
    duration_ms = IntegerField(null=True)  # how long the action took
    timestamp = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "operator_activities"
        indexes = (
            (("operator", "timestamp"), False),
            (("target_type", "target_id"), False),
            (("session_id",), False),
        )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["details"] = _json_loads(self.details)
        return d


# ---------------------------------------------------------------------------
# Resource — unified library index + native content storage
# ---------------------------------------------------------------------------


class Resource(BaseModel):
    """Unified library resource — index over existing entities + native content.

    For linked resources (source_type/source_id point to an existing entity),
    the library metadata (tags/status/version/relations) lives here while the
    core content is pulled from the underlying entity via its provider.

    For native resources (source_type='native'), content is stored directly
    in the `content` field (note body, snippet code, config text, CVE snapshot).
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = ForeignKeyField(Tenant, null=True, backref="resources", column_name="tenant_id")
    resource_type = CharField(max_length=32, index=True)  # module|poc|cve|note|snippet|...
    name = CharField(max_length=256, index=True)
    description = TextField(null=True)
    status = CharField(max_length=16, default="active")  # draft|experimental|active|stable|verified|deprecated|archived
    version = CharField(max_length=16, default="1.0.0")
    tags = TextField(null=True)              # JSON array
    project = CharField(max_length=64, null=True, index=True)
    owner = CharField(max_length=64, null=True)
    source = TextField(null=True)            # URL or originating file
    license = CharField(max_length=64, null=True)
    references = TextField(null=True)        # JSON array of URLs/strings
    dependencies = TextField(null=True)      # JSON array
    metadata = TextField(null=True)          # JSON object — type-specific fields
    content = TextField(null=True)           # native content (note body, snippet code, CVE snapshot)
    language = CharField(max_length=32, null=True)
    visibility = CharField(max_length=16, default="internal")  # public|internal|restricted|private
    storage_path = CharField(max_length=512, null=True)  # file assets (image/PDF/diagram)
    content_hash = CharField(max_length=64, null=True, index=True)  # SHA-256 for duplicate detection
    favorite = BooleanField(default=False)
    pinned = BooleanField(default=False)
    use_count = IntegerField(default=0)
    # Link to underlying entity (for linked resources)
    source_type = CharField(max_length=32, null=True, index=True)  # module|poc|finding|...|native
    source_id = CharField(max_length=64, null=True, index=True)
    created_by = CharField(max_length=64, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "resources"
        indexes = (
            (("tenant", "resource_type", "status"), False),
            (("source_type", "source_id"), False),
        )

    @property
    def tags_list(self) -> list:
        return _json_loads(self.tags) or []

    @tags_list.setter
    def tags_list(self, value: list) -> None:
        self.tags = _json_dumps(value)

    @property
    def metadata_dict(self) -> dict:
        return _json_loads(self.metadata) or {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self.metadata = _json_dumps(value)

    @property
    def references_list(self) -> list:
        return _json_loads(self.references) or []

    @references_list.setter
    def references_list(self, value: list) -> None:
        self.references = _json_dumps(value)

    @property
    def dependencies_list(self) -> list:
        return _json_loads(self.dependencies) or []

    @dependencies_list.setter
    def dependencies_list(self, value: list) -> None:
        self.dependencies = _json_dumps(value)

    def to_dict(self, include_content: bool = True) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["tenant_id"] = str(self.tenant_id) if self.tenant_id else None
        d["tags"] = self.tags_list
        d["metadata"] = self.metadata_dict
        d["references"] = self.references_list
        d["dependencies"] = self.dependencies_list
        if not include_content:
            d.pop("content", None)
        return d


# ---------------------------------------------------------------------------
# ResourceVersion — version history for editable resources
# ---------------------------------------------------------------------------


class ResourceVersion(BaseModel):
    """A snapshot of a resource at a point in time (for versioning)."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    resource = ForeignKeyField(Resource, backref="versions", column_name="resource_id", on_delete="CASCADE")
    version = CharField(max_length=16)
    snapshot = TextField()          # JSON — full resource snapshot at this version
    content = TextField(null=True)  # content at this version (for editable resources)
    change_note = TextField(null=True)
    created_by = CharField(max_length=64, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "resource_versions"
        indexes = (
            (("resource", "version"), False),
        )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["resource_id"] = str(self.resource_id)
        d["snapshot"] = _json_loads(self.snapshot)
        return d


# ---------------------------------------------------------------------------
# ResourceRelation — typed bidirectional relations between resources
# ---------------------------------------------------------------------------


class ResourceRelation(BaseModel):
    """A typed, bidirectional relation between two resources.

    relation_type: references|depends_on|related_to|implements|tests|describes|affects
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    source = ForeignKeyField(Resource, backref="outgoing_relations", column_name="source_id", on_delete="CASCADE")
    target = ForeignKeyField(Resource, backref="incoming_relations", column_name="target_id", on_delete="CASCADE")
    relation_type = CharField(max_length=32)
    metadata = TextField(null=True)  # JSON optional
    created_by = CharField(max_length=64, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        table_name = "resource_relations"
        indexes = (
            (("source", "target", "relation_type"), True),  # unique
            (("target", "source"), False),  # reverse lookup
        )

    @property
    def metadata_dict(self) -> dict:
        return _json_loads(self.metadata) or {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self.metadata = _json_dumps(value)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["id"] = str(d["id"])
        d["source_id"] = str(self.source_id)
        d["target_id"] = str(self.target_id)
        d["metadata"] = self.metadata_dict
        return d


# ---------------------------------------------------------------------------
# Ordered export list (used by database.py for create_tables)
# ---------------------------------------------------------------------------

ALL_MODELS = [
    Tenant,
    User,
    AgentGroup,
    Agent,
    Task,
    Module,
    PocTemplate,
    BuildPack,
    Credential,
    FileEvent,
    Log,
    RefreshToken,
    Timeline,
    Finding,
    AlertEvent,
    AlertWebhook,
    AuditTrail,
    Tactic,
    Technique,
    Campaign,
    Playbook,
    AgentNote,
    ChatMessage,
    C2Profile,
    Redirector,
    Evidence,
    DetectionRule,
    OperatorActivity,
    Resource,
    ResourceVersion,
    ResourceRelation,
]

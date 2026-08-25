"""
Lucy AI Agent — Security Engineering Architect

This module provides an advanced AI agent that acts as a Principal Security
Infrastructure Architect within the Lucy platform. It integrates with the local
LLM (Ollama/deepseek-coder-v2:lite) and has access to all Lucy resources:
- PoC library, build packs, module descriptors
- Agent data, task timelines, credentials, findings, logs

All code generation is sandboxed in the Docker container. Destructive operations
require explicit operator approval.
"""
import json
import logging
import subprocess
import shlex
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import settings
from core.poc_library import get_template_by_puid, load_library
from core.build_packs import get_pack_by_bpid, load_packs
from db.models import (
    Agent, BuildPack, Credential, FileEvent, Finding, Log, Module, PocTemplate,
    Task, Timeline
)

logger = logging.getLogger(__name__)


class AIAgent:
    """Security Engineering Architect AI Agent."""

    def __init__(self):
        self.url = settings.AI_AGENT_LLM_URL.rstrip("/")
        self.model = settings.AI_AGENT_LLM_MODEL
        self.system_prompt = settings.AI_AGENT_SYSTEM_PROMPT
        self.sandbox_container = settings.AI_AGENT_SANDBOX_CONTAINER
        self.sandbox_workspace = settings.AI_AGENT_SANDBOX_WORKSPACE
        self.sandbox_logs = settings.AI_AGENT_SANDBOX_LOGS
        self.max_retries = settings.AI_AGENT_MAX_RETRIES
        self._available: Optional[bool] = None

    @property
    def enabled(self) -> bool:
        return settings.AI_AGENT_ENABLED and bool(self.url)

    async def is_available(self) -> bool:
        """Check if the LLM endpoint is reachable."""
        if not self.enabled:
            return False
        if self._available is not None:
            return self._available
        try:
            req = urllib.request.Request(
                f"{self.url}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False
            logger.debug("AI Agent LLM not reachable at %s", self.url)
        return self._available

    def _chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 256) -> str:
        """Call the LLM /api/chat endpoint (Ollama-compatible)."""
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "")

    # ------------------------------------------------------------------
    # Resource Access (Lucy data)
    # ------------------------------------------------------------------

    def get_context(self) -> dict[str, Any]:
        """Build a comprehensive context snapshot of Lucy resources."""
        ctx: dict[str, Any] = {}

        # Agents
        try:
            agents = list(Agent.select().dicts())
            ctx["agents"] = [
                {
                    "id": str(a.get("id")),
                    "hostname": a.get("hostname"),
                    "os": a.get("os"),
                    "status": a.get("status"),
                    "last_seen": str(a.get("last_seen")) if a.get("last_seen") else None,
                }
                for a in agents
            ]
        except Exception as exc:
            ctx["agents_error"] = str(exc)

        # Tasks
        try:
            tasks = list(Task.select().order_by(Task.created_at.desc()).limit(20).dicts())
            ctx["recent_tasks"] = [
                {
                    "id": str(t.get("id")),
                    "status": t.get("status"),
                    "module": t.get("module"),
                    "action": t.get("action"),
                    "created_at": str(t.get("created_at")),
                }
                for t in tasks
            ]
        except Exception as exc:
            ctx["tasks_error"] = str(exc)

        # Timelines
        try:
            timelines = list(Timeline.select().dicts())
            ctx["timelines"] = [
                {
                    "id": str(tl.get("id")),
                    "name": tl.get("name"),
                    "status": tl.get("status"),
                    "trigger": tl.get("trigger"),
                }
                for tl in timelines
            ]
        except Exception as exc:
            ctx["timelines_error"] = str(exc)

        # Modules
        try:
            modules = list(Module.select().dicts())
            ctx["modules"] = [
                {
                    "id": str(m.get("id")),
                    "name": m.get("name"),
                    "category": m.get("category"),
                    "actions": json.loads(m.get("actions") or "[]"),
                    "tags": json.loads(m.get("tags") or "[]"),
                    "enabled": m.get("enabled"),
                }
                for m in modules
            ]
        except Exception as exc:
            ctx["modules_error"] = str(exc)

        # PoC Library
        try:
            pocs = load_library()
            ctx["poc_count"] = len(pocs)
            ctx["poc_categories"] = list(set(p.get("category", "unknown") for p in pocs))
        except Exception as exc:
            ctx["poc_error"] = str(exc)

        # Build Packs
        try:
            packs = load_packs()
            ctx["build_pack_count"] = len(packs)
        except Exception as exc:
            ctx["build_pack_error"] = str(exc)

        # Credentials
        try:
            cred_count = Credential.select().count()
            ctx["credential_count"] = cred_count
        except Exception as exc:
            ctx["credential_error"] = str(exc)

        # Findings
        try:
            finding_count = Finding.select().count()
            ctx["finding_count"] = finding_count
        except Exception as exc:
            ctx["finding_error"] = str(exc)

        # Logs
        try:
            recent_logs = list(Log.select().order_by(Log.timestamp.desc()).limit(10).dicts())
            ctx["recent_logs"] = [
                {
                    "level": l.get("level"),
                    "module": l.get("module"),
                    "message": l.get("message"),
                    "timestamp": str(l.get("timestamp")),
                }
                for l in recent_logs
            ]
        except Exception as exc:
            ctx["logs_error"] = str(exc)

        return ctx

    # ------------------------------------------------------------------
    # Core AI Capabilities
    # ------------------------------------------------------------------

    async def analyze_threat(self, query: str) -> dict[str, Any]:
        """Analyze a threat scenario using Lucy resources and LLM reasoning."""
        if not await self.is_available():
            return {"status": "unavailable", "message": "AI Agent LLM not reachable"}

        ctx = self.get_context()
        context_summary = json.dumps(ctx, indent=2, default=str)

        prompt = (
            f"Analyze this threat scenario in the context of the Lucy platform:\n\n"
            f"Scenario: {query}\n\n"
            f"Current Lucy resources:\n{context_summary}\n\n"
            f"Provide a structured analysis with:\n"
            f"1. Threat assessment (low/medium/high/critical)\n"
            f"2. Relevant MITRE ATT&CK techniques\n"
            f"3. Recommended Lucy modules/PoCs to deploy\n"
            f"4. Suggested timeline or playbook\n"
            f"5. Detection and defensive recommendations\n\n"
            f"Respond in JSON format."
        )

        try:
            response = self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.2, max_tokens=256)

            # Try to extract JSON
            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            parsed = json.loads(text)
            return {"status": "success", "analysis": parsed, "raw": response}
        except TimeoutError:
            logger.warning("AI threat analysis timed out")
            return {"status": "unavailable", "message": "AI Agent LLM call timed out"}
        except Exception as exc:
            logger.error("AI threat analysis failed: %s", exc)
            return {"status": "error", "message": str(exc), "raw": response if 'response' in dir() else None}

    async def generate_script(self, task_description: str, language: str = "python") -> dict[str, Any]:
        """Generate a modular security script for the sandbox."""
        if not await self.is_available():
            return {"status": "unavailable", "message": "AI Agent LLM not reachable"}

        prompt = (
            f"Generate a modular {language} security tool for the following task:\n\n"
            f"Task: {task_description}\n\n"
            f"Requirements:\n"
            f"- CLI entrypoint with argparse\n"
            f"- Core logic separated into functions/classes\n"
            f"- Structured JSON logging to /workspace/logs/\n"
            f"- Error handling and graceful degradation\n"
            f"- Comments explaining the security rationale\n\n"
            f"Respond with ONLY the code, wrapped in a markdown code block."
        )

        try:
            response = self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.2, max_tokens=256)

            # Extract code from markdown block
            code = response
            if "```" in response:
                parts = response.split("```")
                for part in parts:
                    if part.strip().startswith("python") or part.strip().startswith(language):
                        code = part.replace("python", "").replace(language, "").strip()
                        break
                    elif part.strip() and not part.strip().startswith("python"):
                        code = part.strip()
                        break

            return {"status": "success", "language": language, "code": code, "raw": response}
        except Exception as exc:
            logger.error("AI script generation failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    def _docker_container_running(self) -> bool:
        """Check if the Docker sandbox container is actually running."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self.sandbox_container],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and "true" in result.stdout.strip().lower()
        except Exception:
            return False

    async def execute_in_sandbox(
        self,
        command: str | list[str],
        timeout: int = 60,
        cwd: str | None = None,
        input_data: str | None = None,
    ) -> dict[str, Any]:
        """Execute a command in the sandbox container (Docker) or locally as fallback."""
        # Normalize to a list so no host shell is invoked (shell=False).
        if isinstance(command, str):
            try:
                command_list = shlex.split(command)
            except ValueError:
                return {"status": "error", "message": "Invalid command string"}
        else:
            command_list = [str(c) for c in command]

        # Try Docker sandbox first — only if the container is actually running
        if self.sandbox_container and self._docker_container_running():
            try:
                docker_cmd = ["docker", "exec", "-i"]
                if cwd:
                    docker_cmd.extend(["-w", cwd])
                docker_cmd.append(self.sandbox_container)
                docker_cmd.extend(command_list)
                result = subprocess.run(
                    docker_cmd,
                    input=input_data,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return {
                    "status": "success" if result.returncode == 0 else "failure",
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "command": command if isinstance(command, str) else shlex.join(command_list),
                    "sandbox_mode": "docker",
                }
            except subprocess.TimeoutExpired:
                return {"status": "timeout", "message": f"Command timed out after {timeout}s"}
            except FileNotFoundError:
                logger.warning("Docker not available — falling back to local sandbox mode")
            except Exception as exc:
                logger.warning("Docker sandbox failed (%s) — falling back to local mode", exc)

        # Local fallback — run in a restricted working directory
        local_ws = Path(self.sandbox_workspace).resolve() if self.sandbox_workspace else Path("data/ai_sandbox").resolve()
        local_ws.mkdir(parents=True, exist_ok=True)
        run_cwd = cwd or str(local_ws)
        try:
            if isinstance(command, str):
                result = subprocess.run(
                    command,
                    input=input_data,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=run_cwd,
                )
            else:
                result = subprocess.run(
                    command_list,
                    input=input_data,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=run_cwd,
                )
            return {
                "status": "success" if result.returncode == 0 else "failure",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command if isinstance(command, str) else shlex.join(command_list),
                "sandbox_mode": "local",
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "message": f"Command timed out after {timeout}s", "sandbox_mode": "local"}
        except Exception as exc:
            return {"status": "error", "message": str(exc), "sandbox_mode": "local"}

    async def write_file_to_sandbox(self, path: str, content: str) -> dict[str, Any]:
        """Write a file to the sandbox workspace (Docker or local)."""
        local_path = path.lstrip("/")
        # Try Docker first
        if self.sandbox_container:
            full_path = f"{self.sandbox_workspace}/{local_path}" if self.sandbox_workspace else f"/workspace/{local_path}"
            parent = full_path.rsplit("/", 1)[0] if "/" in full_path else "/"
            # No shell is used; paths are passed as separate list arguments.
            await self.execute_in_sandbox(["mkdir", "-p", parent], timeout=10)
            result = await self.execute_in_sandbox(["tee", full_path], input_data=content, timeout=30)
            if result.get("sandbox_mode") == "docker":
                return result

        # Local fallback — write directly to filesystem
        local_ws = Path(self.sandbox_workspace).resolve() if self.sandbox_workspace else Path("data/ai_sandbox").resolve()
        full_local = local_ws / local_path
        try:
            full_local.parent.mkdir(parents=True, exist_ok=True)
            full_local.write_text(content, encoding="utf-8")
            return {
                "status": "success",
                "path": str(full_local),
                "bytes_written": len(content),
                "sandbox_mode": "local",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc), "sandbox_mode": "local"}

    async def run_script(self, script_path: str, args: str = "") -> dict[str, Any]:
        """Run a script in the sandbox and return structured output."""
        local_path = script_path.lstrip("/")
        script_args = []
        if args:
            try:
                script_args = shlex.split(args)
            except ValueError:
                return {"status": "error", "message": "Invalid script arguments"}

        # Try Docker first
        if self.sandbox_container:
            full_path = f"{self.sandbox_workspace}/{local_path}" if self.sandbox_workspace else f"/workspace/{local_path}"
            result = await self.execute_in_sandbox(
                ["python3", full_path] + script_args,
                timeout=120,
                cwd=self.sandbox_workspace,
            )

            if result.get("sandbox_mode") == "docker":
                # Try to parse JSON logs if they exist
                if result.get("status") == "success":
                    log_path = f"{self.sandbox_logs}/{script_path.replace('/', '_').replace('.py', '')}.json"
                    log_result = await self.execute_in_sandbox(["cat", log_path], timeout=10)
                    try:
                        result["structured_logs"] = json.loads(log_result.get("stdout", "{}"))
                    except Exception:
                        result["structured_logs"] = None
                return result

        # Local fallback
        local_ws = Path(self.sandbox_workspace).resolve() if self.sandbox_workspace else Path("data/ai_sandbox").resolve()
        full_local = local_ws / local_path
        result = await self.execute_in_sandbox(
            ["python3", str(full_local)] + script_args,
            timeout=120,
            cwd=str(local_ws),
        )

        # Try to parse JSON logs locally
        if result.get("status") == "success":
            log_file = local_ws / f"{script_path.replace('/', '_').replace('.py', '')}.json"
            if log_file.exists():
                try:
                    result["structured_logs"] = json.loads(log_file.read_text(encoding="utf-8"))
                except Exception:
                    result["structured_logs"] = None
        return result

    async def suggest_next_steps(self, current_state: dict[str, Any]) -> dict[str, Any]:
        """Suggest next tactical steps based on current Lucy state."""
        if not await self.is_available():
            return {"status": "unavailable", "message": "AI Agent LLM not reachable"}

        state_json = json.dumps(current_state, indent=2, default=str)

        prompt = (
            f"Based on this current Lucy mission state, suggest 3-5 tactical next steps:\n\n"
            f"{state_json}\n\n"
            f"For each step, provide:\n"
            f"1. Action name\n"
            f"2. Target (agent, group, or module)\n"
            f"3. Expected outcome\n"
            f"4. Risk level (low/medium/high)\n"
            f"5. MITRE technique mapping\n\n"
            f"Respond in JSON format as a list of steps."
        )

        try:
            response = self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=256)

            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            parsed = json.loads(text)
            return {"status": "success", "suggestions": parsed, "raw": response}
        except Exception as exc:
            return {"status": "error", "message": str(exc), "raw": response if 'response' in dir() else None}

    async def analyze_results(self, task_results: list[dict]) -> dict[str, Any]:
        """Analyze task execution results and provide insights."""
        if not await self.is_available():
            return {"status": "unavailable", "message": "AI Agent LLM not reachable"}

        results_json = json.dumps(task_results, indent=2, default=str)

        prompt = (
            f"Analyze these task execution results from the Lucy platform:\n\n"
            f"{results_json}\n\n"
            f"Provide:\n"
            f"1. Success/failure breakdown\n"
            f"2. Notable findings or anomalies\n"
            f"3. Recommendations for follow-up actions\n"
            f"4. Suggested PoC or module to run next\n\n"
            f"Respond in JSON format."
        )

        try:
            response = self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.2, max_tokens=256)

            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            parsed = json.loads(text)
            return {"status": "success", "analysis": parsed, "raw": response}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}


# Shared instance
agent = AIAgent()

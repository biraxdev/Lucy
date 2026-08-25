"""
Lucy AI Chat Engine — Interactive Autonomous Architect

Ultra-intelligent conversational system that:
- Maintains multi-turn conversation state
- Reflects, plans, and asks clarifying questions before acting
- Searches Lucy resources (modules, PoCs, build packs, agents, tasks)
- Generates Lucy code (Python modules, API endpoints, React components)
- Self-builds: writes files, registers modules, updates Lucy in real-time
- Executes in sandbox for validation before committing
- Understands the entire Lucy infrastructure and can modify it

Conversation flow:
  USER_REQUEST -> REFLECT -> (CLARIFY? -> USER_ANSWERS) -> PLAN -> EXECUTE -> REPORT
"""
import json
import logging
import os
import re
import subprocess
import textwrap
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import settings
from core.ai_agent import agent as ai_agent
from core.module_manager import ModuleManager
from core.poc_library import load_library, get_template_by_puid
from core.build_packs import load_packs, get_pack_by_bpid
from db.models import Agent, Module, Task, Timeline, PocTemplate, BuildPack, Credential, Finding, Log

logger = logging.getLogger(__name__)

manager = ModuleManager()


# ---------------------------------------------------------------------------
# Conversation State
# ---------------------------------------------------------------------------

class ConversationState:
    """In-memory conversation state per user/session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: list[dict] = []           # Full message history
        self.pending_clarification: dict | None = None
        self.current_plan: list[dict] = []
        self.plan_status: str = "idle"           # idle, clarifying, planning, executing, done
        self.context_snapshot: dict = {}
        self.created_at = datetime.now(timezone.utc)

    def add_message(self, role: str, content: str, metadata: dict | None = None) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        })

    def to_llm_context(self, max_messages: int = 20) -> list[dict]:
        """Return last N messages formatted for LLM consumption."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages[-max_messages:]
        ]


# Global conversation store (in production, use Redis or DB)
_conversations: dict[str, ConversationState] = {}


def get_conversation(session_id: str) -> ConversationState:
    if session_id not in _conversations:
        _conversations[session_id] = ConversationState(session_id)
    return _conversations[session_id]


# ---------------------------------------------------------------------------
# LLM Communication
# ---------------------------------------------------------------------------

class AIChatLLM:
    """LLM interface tuned for interactive conversation."""

    def __init__(self, url: str | None = None, model: str | None = None):
        self.url = (url or settings.AI_AGENT_LLM_URL).rstrip("/")
        self.model = model or settings.AI_AGENT_LLM_MODEL
        self.system_base = settings.AI_AGENT_SYSTEM_PROMPT

    def _call(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 192) -> str:
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

    def chat(self, state: ConversationState, user_message: str) -> str:
        """Send a message in the context of the conversation and return the AI response."""
        system = self._build_system_prompt(state)
        msgs = [{"role": "system", "content": system}] + state.to_llm_context() + [
            {"role": "user", "content": user_message}
        ]
        return self._call(msgs, temperature=0.3, max_tokens=192)

    def structured_chat(self, state: ConversationState, user_message: str, schema_hint: str) -> dict:
        """Chat expecting a JSON response. Returns parsed dict or {'error': ...}."""
        system = self._build_system_prompt(state) + f"\n\nIMPORTANT: You must respond ONLY with valid JSON. {schema_hint}"
        msgs = [{"role": "system", "content": system}] + state.to_llm_context() + [
            {"role": "user", "content": user_message}
        ]
        raw = self._call(msgs, temperature=0.2, max_tokens=192)
        return self._extract_json(raw)

    def _build_system_prompt(self, state: ConversationState) -> str:
        infra = self._describe_infrastructure()
        resources = self._describe_resources()
        return (
            f"{self.system_base}\n\n"
            f"=== LUCY INFRASTRUCTURE ===\n{infra}\n\n"
            f"=== AVAILABLE RESOURCES ===\n{resources}\n\n"
            f"=== CONVERSATION STATE ===\n"
            f"Status: {state.plan_status}\n"
            f"Pending clarification: {state.pending_clarification is not None}\n"
            f"Current plan steps: {len(state.current_plan)}\n\n"
            f"You are an interactive AI architect. When the user asks you to build, modify, or create something:\n"
            f"1. FIRST, reflect and identify missing details.\n"
            f"2. If anything is unclear, ask concise clarifying questions (1-3 max).\n"
            f"3. Once clarified, build a step-by-step execution plan.\n"
            f"4. Execute each step: generate code, write files, register modules, test in sandbox.\n"
            f"5. Report results clearly with file paths and status.\n"
            f"You can modify Lucy's own source code, create new modules, new API endpoints, and new UI components.\n"
            f"You understand FastAPI, Peewee ORM, React 18, TypeScript, TailwindCSS, and Zustand.\n"
        )

    def _describe_infrastructure(self) -> str:
        return textwrap.dedent("""\
            Lucy is a Remote Agent Testing System (RATS) with:
            - Backend: Python 3.12 + FastAPI + WebSockets + SQLite (Peewee ORM) + Celery + Redis
            - Frontend: React 18 + TypeScript + TailwindCSS + Zustand + React Router + ReactFlow
            - Agent: standalone Python agent with modules (shell, file, info, keylog, screenshot, browser)
            - Docker: Compose stack with backend, frontend, redis, celery, ollama, sandbox
            - Auth: JWT + API Key rotation
            - Crypto: AES-256-GCM, ECDH P-256, HMAC-SHA256
        """)

    def _describe_resources(self) -> str:
        lines = []
        try:
            lines.append(f"Modules: {Module.select().count()}")
            lines.append(f"Agents: {Agent.select().count()}")
            lines.append(f"Tasks: {Task.select().count()}")
            lines.append(f"Timelines: {Timeline.select().count()}")
            lines.append(f"PoC Templates: {PocTemplate.select().count()}")
            lines.append(f"Build Packs: {BuildPack.select().count()}")
            lines.append(f"Credentials: {Credential.select().count()}")
            lines.append(f"Findings: {Finding.select().count()}")
        except Exception as exc:
            lines.append(f"Resource count error: {exc}")
        return "\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            return json.loads(text)
        except Exception as exc:
            return {"error": str(exc), "raw": text}


llm = AIChatLLM()


# ---------------------------------------------------------------------------
# Core Engine: Reflect -> Clarify -> Plan -> Execute
# ---------------------------------------------------------------------------

class InteractiveAIEngine:
    """Main engine for the interactive AI chat experience."""

    def __init__(self):
        self.llm = llm

    async def _search_modules(self, request: str) -> dict | None:
        """Fast, LLM-free module search for 'search modules for X' queries."""
        text = request.lower()
        if "module" not in text or "search" not in text:
            return None
        keyword = ""
        if "for" in text:
            parts = text.split("for")[-1].strip().split()
            if parts:
                keyword = parts[0]
        if not keyword:
            keyword = text.split()[-1]
        if keyword in ("modules", "module"):
            keyword = ""
        try:
            from db.models import Module

            query = Module.select().where(Module.enabled == True)
            if keyword:
                keyword = keyword.lower()
                query = query.where(
                    (Module.name.contains(keyword)) | (Module.description.contains(keyword))
                )
            matches = []
            for m in query.limit(5):
                matches.append({
                    "step": len(matches) + 1,
                    "module": m.name,
                    "action": (m.actions_list[:1] or ["list"])[0],
                    "params": {},
                    "description": m.description or "",
                    "confidence": "high",
                })
            if not matches:
                return None
            return {
                "type": "execution_report",
                "status": "done",
                "plan_status": "done",
                "results": matches,
                "message": f"Found {len(matches)} modules matching your request.",
            }
        except Exception:
            return None

    async def process(self, session_id: str, user_message: str) -> dict:
        """Process a user message through the full interactive pipeline."""
        state = get_conversation(session_id)
        state.add_message("user", user_message)

        # Step 1: Handle clarification answers
        if state.plan_status == "clarifying" and state.pending_clarification:
            return await self._handle_clarification_answer(state, user_message)

        # Step 2: Reflect on the request
        reflection = await self._reflect(state, user_message)

        # Step 3: If unclear, ask clarifying questions
        if reflection.get("needs_clarification"):
            return await self._ask_clarification(state, reflection)

        # Step 4: Build plan
        plan = await self._build_plan(state, user_message, reflection)
        state.current_plan = plan
        state.plan_status = "executing"

        # Step 5: Execute plan
        results = await self._execute_plan(state, plan)
        state.plan_status = "done"

        # Step 6: Report
        report = await self._generate_report(state, results)
        state.add_message("assistant", report["message"], report)
        return report

    async def _reflect(self, state: ConversationState, user_message: str) -> dict:
        """Analyze the request to determine if clarification is needed."""
        prompt = (
            f"Analyze this user request and determine if you have enough information to execute it.\n\n"
            f"User request: \"{user_message}\"\n\n"
            f"Respond in JSON:\n"
            f'{{"needs_clarification": true/false, '
            f'"reasoning": "brief analysis", '
            f'"questions": ["question 1", "question 2", ...], '
            f'"suggested_approach": "high-level plan"}}'
        )
        return self.llm.structured_chat(state, prompt, "JSON with needs_clarification, reasoning, questions, suggested_approach")

    async def _ask_clarification(self, state: ConversationState, reflection: dict) -> dict:
        """Pose clarifying questions to the user."""
        questions = reflection.get("questions", ["Can you provide more details?"])
        state.pending_clarification = {
            "questions": questions,
            "original_request": state.messages[-1]["content"],
            "reflection": reflection,
        }
        state.plan_status = "clarifying"

        message = (
            "Je voudrais bien vous aider, mais j'ai besoin de quelques clarifications :\n\n"
            + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
            + "\n\nRépondez-moi avec ces détails et je m'exécute immédiatement."
        )
        state.add_message("assistant", message, {"type": "clarification", "questions": questions})
        return {
            "type": "clarification",
            "questions": questions,
            "message": message,
            "status": "clarifying",
        }

    async def _handle_clarification_answer(self, state: ConversationState, answer: str) -> dict:
        """Process the user's clarification answers and proceed."""
        state.pending_clarification["answer"] = answer
        state.pending_clarification = None

        # Re-run reflection with full context now that we have answers
        full_request = state.messages[-2]["content"] + "\n\nClarifications: " + answer
        reflection = await self._reflect(state, full_request)

        plan = await self._build_plan(state, full_request, reflection)
        state.current_plan = plan
        state.plan_status = "executing"

        results = await self._execute_plan(state, plan)
        state.plan_status = "done"

        report = await self._generate_report(state, results)
        state.add_message("assistant", report["message"], report)
        return report

    async def _build_plan(self, state: ConversationState, request: str, reflection: dict) -> list[dict]:
        """Build a step-by-step execution plan."""
        prompt = (
            f"Build a precise execution plan for this request.\n\n"
            f"Request: {request}\n"
            f"Approach: {reflection.get('suggested_approach', 'Custom implementation')}\n\n"
            f"You have access to these Lucy capabilities:\n"
            f"- generate_python_module(name, code, description, actions, params_schema)\n"
            f"- generate_api_endpoint(route, method, code, description)\n"
            f"- generate_react_component(name, code, route?)\n"
            f"- execute_sandbox_command(command)\n"
            f"- write_sandbox_file(path, content)\n"
            f"- run_sandbox_script(path, args)\n"
            f"- search_modules(query), search_pocs(query), search_agents(query)\n"
            f"- create_timeline(name, steps), execute_timeline(id)\n"
            f"- register_module_in_db(metadata)\n"
            f"\n"
            f"Respond in JSON array of steps:\n"
            f'[{{"step": 1, "action": "action_name", "params": {{...}}, "description": "what this does"}}]'
        )
        plan = self.llm.structured_chat(state, prompt, "JSON array of step objects with step, action, params, description")
        if isinstance(plan, list):
            return plan
        return [{"step": 1, "action": "chat_response", "params": {"message": "Je vais analyser votre demande et construire une solution."}, "description": "Initial analysis"}]

    async def _execute_plan(self, state: ConversationState, plan: list[dict]) -> list[dict]:
        """Execute each step of the plan."""
        results = []
        for step in plan:
            action = step.get("action", "unknown")
            params = step.get("params", {})
            description = step.get("description", "")
            logger.info("Executing plan step %s: %s", step.get("step"), action)

            try:
                result = await self._execute_action(action, params, state)
                results.append({
                    "step": step.get("step"),
                    "action": action,
                    "description": description,
                    "status": "success",
                    "result": result,
                })
            except Exception as exc:
                logger.exception("Plan step failed: %s", action)
                results.append({
                    "step": step.get("step"),
                    "action": action,
                    "description": description,
                    "status": "error",
                    "error": str(exc),
                })
                # Try to auto-fix if it's a code generation step
                if action in ("generate_python_module", "generate_api_endpoint", "generate_react_component"):
                    fix_result = await self._auto_fix(action, params, str(exc), state)
                    results.append({
                        "step": step.get("step"),
                        "action": f"{action}_auto_fix",
                        "status": "success" if fix_result.get("fixed") else "error",
                        "result": fix_result,
                    })

        return results

    async def _execute_action(self, action: str, params: dict, state: ConversationState) -> dict:
        """Dispatch an action."""
        handlers = {
            "chat_response": self._action_chat_response,
            "generate_python_module": self._action_generate_python_module,
            "generate_api_endpoint": self._action_generate_api_endpoint,
            "generate_react_component": self._action_generate_react_component,
            "execute_sandbox_command": self._action_execute_sandbox_command,
            "write_sandbox_file": self._action_write_sandbox_file,
            "run_sandbox_script": self._action_run_sandbox_script,
            "search_modules": self._action_search_modules,
            "search_pocs": self._action_search_pocs,
            "search_agents": self._action_search_agents,
            "create_timeline": self._action_create_timeline,
            "register_module_in_db": self._action_register_module_in_db,
        }
        handler = handlers.get(action, self._action_unknown)
        return await handler(params, state)

    # ------------------------------------------------------------------
    # Action Handlers
    # ------------------------------------------------------------------

    async def _action_chat_response(self, params: dict, state: ConversationState) -> dict:
        return {"message": params.get("message", "Done.")}

    async def _action_generate_python_module(self, params: dict, state: ConversationState) -> dict:
        """Generate a Python module and register it in Lucy."""
        name = params.get("name", "custom_module")
        description = params.get("description", "Auto-generated module")
        actions = params.get("actions", [])
        params_schema = params.get("params_schema", {})

        # Generate code using LLM
        code_prompt = (
            f"Generate a complete Python module for Lucy named '{name}'.\n"
            f"Description: {description}\n"
            f"Actions: {actions}\n"
            f"Params schema: {json.dumps(params_schema)}\n\n"
            f"Requirements:\n"
            f"- Must be a valid Python module with register_actions() function\n"
            f"- Use standard library only (no external deps unless justified)\n"
            f"- Include docstrings and type hints\n"
            f"- Handle errors gracefully\n"
            f"- Return structured dict results\n\n"
            f"Respond with ONLY the Python code in a markdown code block."
        )
        raw = self.llm.chat(state, code_prompt)
        code = self._extract_code(raw)

        # Write to sandbox first for validation
        sandbox_path = f"/workspace/modules/{name}.py"
        await ai_agent.write_file_to_sandbox(sandbox_path, code)

        # Test syntax in sandbox
        test_result = await ai_agent.execute_in_sandbox(f"python3 -m py_compile {sandbox_path}")
        if test_result.get("returncode") != 0:
            # Auto-fix
            fix = await self._auto_fix_code(code, test_result.get("stderr", ""), state)
            code = fix.get("code", code)
            await ai_agent.write_file_to_sandbox(sandbox_path, code)

        # Register in Lucy DB
        module_data = {
            "name": name,
            "version": params.get("version", "1.0.0"),
            "description": description,
            "code": code,
            "actions": json.dumps(actions),
            "params_schema": json.dumps(params_schema),
            "category": params.get("category", "custom"),
            "tags": json.dumps(params.get("tags", ["ai-generated"])),
            "inputs": json.dumps(params.get("inputs", [])),
            "outputs": json.dumps(params.get("outputs", [])),
            "expected_duration": params.get("expected_duration", 30),
            "os_compat": json.dumps(params.get("os_compat", ["windows", "linux", "darwin"])),
        }
        mod = manager.register(**module_data)

        return {
            "module_name": name,
            "sandbox_path": sandbox_path,
            "db_module_id": str(mod.id) if mod else None,
            "code_length": len(code),
            "syntax_valid": test_result.get("returncode") == 0,
        }

    async def _action_generate_api_endpoint(self, params: dict, state: ConversationState) -> dict:
        """Generate a FastAPI endpoint and inject it into Lucy."""
        route = params.get("route", "/custom")
        method = params.get("method", "GET")
        description = params.get("description", "Auto-generated endpoint")

        code_prompt = (
            f"Generate a FastAPI endpoint for Lucy.\n"
            f"Route: {route}\n"
            f"Method: {method}\n"
            f"Description: {description}\n\n"
            f"Requirements:\n"
            f"- Use existing Lucy patterns (dependencies.CurrentUser, HTTPException, etc.)\n"
            f"- Use Peewee ORM for DB access\n"
            f"- Include Pydantic request/response models\n"
            f"- Include proper error handling\n"
            f"- Return JSON responses\n\n"
            f"Respond with ONLY the Python code in a markdown code block."
        )
        raw = self.llm.chat(state, code_prompt)
        code = self._extract_code(raw)

        # Write to project api directory
        api_dir = Path(__file__).parent.parent / "api"
        file_name = f"ai_generated_{uuid.uuid4().hex[:8]}.py"
        file_path = api_dir / file_name
        file_path.write_text(code, encoding="utf-8")

        # Syntax check
        test_result = await ai_agent.execute_in_sandbox(f"python3 -m py_compile {file_path}")

        return {
            "file_path": str(file_path),
            "route": route,
            "method": method,
            "syntax_valid": test_result.get("returncode") == 0,
            "note": "Restart backend to load new endpoint, or use dynamic router registration.",
        }

    async def _action_generate_react_component(self, params: dict, state: ConversationState) -> dict:
        """Generate a React component and write it to frontend."""
        name = params.get("name", "AiGeneratedComponent")
        route = params.get("route")

        code_prompt = (
            f"Generate a React 18 + TypeScript component for Lucy.\n"
            f"Component name: {name}\n"
            f"Route: {route or 'no route'}\n"
            f"Description: {params.get('description', 'Auto-generated component')}\n\n"
            f"Requirements:\n"
            f"- Use functional components with hooks\n"
            f"- Use TailwindCSS for styling (daisyUI classes: btn, card, badge, etc.)\n"
            f"- Use Lucide React icons\n"
            f"- Use Zustand stores if state management needed\n"
            f"- Use react-query for API calls\n"
            f"- Proper TypeScript types\n"
            f"- Export default component\n\n"
            f"Respond with ONLY the TypeScript/React code in a markdown code block."
        )
        raw = self.llm.chat(state, code_prompt)
        code = self.llm._extract_json(raw)
        if isinstance(code, dict):
            code = code.get("code", raw)
        if not isinstance(code, str):
            code = self._extract_code(raw)

        # Write to frontend pages or components
        if route:
            file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "pages" / f"{name}.tsx"
        else:
            file_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "components" / f"{name}.tsx"
        file_path.write_text(code, encoding="utf-8")

        return {
            "file_path": str(file_path),
            "component_name": name,
            "route": route,
            "note": "Component written to disk but NOT auto-routed. Add a route in frontend/src/routes.tsx and import the component manually to make it reachable in the UI.",
        }

    async def _action_execute_sandbox_command(self, params: dict, state: ConversationState) -> dict:
        return await ai_agent.execute_in_sandbox(params.get("command", ""), params.get("timeout", 60))

    async def _action_write_sandbox_file(self, params: dict, state: ConversationState) -> dict:
        return await ai_agent.write_file_to_sandbox(params.get("path", ""), params.get("content", ""))

    async def _action_run_sandbox_script(self, params: dict, state: ConversationState) -> dict:
        return await ai_agent.run_script(params.get("path", ""), params.get("args", ""))

    async def _action_search_modules(self, params: dict, state: ConversationState) -> dict:
        query = params.get("query", "")
        try:
            matches = []
            for m in Module.select().where(Module.name.contains(query) | Module.description.contains(query)):
                matches.append({"id": str(m.id), "name": m.name, "category": m.category, "actions": m.actions_list})
            return {"matches": matches, "count": len(matches)}
        except Exception as exc:
            return {"error": str(exc)}

    async def _action_search_pocs(self, params: dict, state: ConversationState) -> dict:
        query = params.get("query", "").lower()
        try:
            pocs = load_library()
            matches = [p for p in pocs if query in p.get("name", "").lower() or query in p.get("description", "").lower()]
            return {"matches": matches, "count": len(matches)}
        except Exception as exc:
            return {"error": str(exc)}

    async def _action_search_agents(self, params: dict, state: ConversationState) -> dict:
        query = params.get("query", "").lower()
        try:
            matches = []
            for a in Agent.select().where(Agent.hostname.contains(query) | Agent.os.contains(query)):
                matches.append({"id": str(a.id), "hostname": a.hostname, "os": a.os, "status": a.status})
            return {"matches": matches, "count": len(matches)}
        except Exception as exc:
            return {"error": str(exc)}

    async def _action_create_timeline(self, params: dict, state: ConversationState) -> dict:
        from core.orchestrator import orchestrator
        name = params.get("name", "AI Timeline")
        steps = params.get("steps", [])
        tl = orchestrator.create_timeline(name=name, steps=steps)
        return {"timeline_id": str(tl.id), "name": name, "steps_count": len(steps)}

    async def _action_register_module_in_db(self, params: dict, state: ConversationState) -> dict:
        mod = manager.register(**params)
        return {"module_id": str(mod.id) if mod else None, "name": params.get("name")}

    async def _action_unknown(self, params: dict, state: ConversationState) -> dict:
        return {"message": f"Unknown action. I can only execute planned actions."}

    # ------------------------------------------------------------------
    # Auto-fix
    # ------------------------------------------------------------------

    async def _auto_fix(self, action: str, params: dict, error: str, state: ConversationState) -> dict:
        """Attempt to auto-fix a failed action by regenerating the code."""
        prompt = (
            f"The previous code generation failed with this error:\n{error}\n\n"
            f"Original params: {json.dumps(params)}\n\n"
            f"Please regenerate the code fixing the error. Respond with ONLY the corrected code."
        )
        raw = self.llm.chat(state, prompt)
        code = self._extract_code(raw)
        return {"fixed": True, "code": code, "original_error": error}

    async def _auto_fix_code(self, code: str, error: str, state: ConversationState) -> dict:
        """Auto-fix Python code syntax errors."""
        prompt = (
            f"This Python code has a syntax error:\n\n{error}\n\n"
            f"Code:\n```python\n{code}\n```\n\n"
            f"Fix it and return ONLY the corrected code."
        )
        raw = self.llm.chat(state, prompt)
        return {"fixed": True, "code": self._extract_code(raw)}

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    async def _generate_report(self, state: ConversationState, results: list[dict]) -> dict:
        """Generate a human-readable report of the plan execution."""
        successes = [r for r in results if r["status"] == "success"]
        errors = [r for r in results if r["status"] == "error"]

        summary = (
            f"Exécution terminée. {len(successes)} étapes réussies, {len(errors)} erreurs.\n\n"
        )

        for r in results:
            icon = "✅" if r["status"] == "success" else "❌"
            summary += f"{icon} Étape {r['step']}: {r['description']}\n"
            if r["status"] == "success" and isinstance(r.get("result"), dict):
                for k, v in r["result"].items():
                    if k in ("file_path", "module_name", "sandbox_path", "route", "component_name"):
                        summary += f"   → {k}: {v}\n"
            elif r["status"] == "error":
                summary += f"   → Erreur: {r.get('error', 'Unknown')}\n"

        if not errors:
            summary += "\n🎯 Tout est opérationnel. Vous pouvez utiliser ce qui a été créé."
        else:
            summary += "\n⚠️ Certaines étapes ont échoué. Je peux réessayer ou contourner si vous me le demandez."

        return {
            "type": "execution_report",
            "message": summary,
            "success_count": len(successes),
            "error_count": len(errors),
            "results": results,
            "status": "done",
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_code(text: str) -> str:
        """Extract code from markdown code blocks."""
        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("python"):
                    return part[6:].strip()
                if part.startswith("typescript") or part.startswith("tsx"):
                    return part[10:].strip() if part.startswith("typescript") else part[3:].strip()
                if part.startswith("javascript") or part.startswith("js"):
                    return part[10:].strip() if part.startswith("javascript") else part[2:].strip()
                if "\n" in part and len(part) > 20 and not part.startswith("json"):
                    return part.strip()
        return text

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, session_id: str, message: str) -> dict:
        """Simple chat mode when not in execution mode."""
        state = get_conversation(session_id)
        state.add_message("user", message)
        response = self.llm.chat(state, message)
        state.add_message("assistant", response)
        return {"type": "chat", "message": response, "status": "done"}

    async def clear_session(self, session_id: str) -> dict:
        if session_id in _conversations:
            del _conversations[session_id]
        return {"status": "cleared"}

    def get_history(self, session_id: str) -> list[dict]:
        state = get_conversation(session_id)
        return state.messages


# Shared instance
engine = InteractiveAIEngine()

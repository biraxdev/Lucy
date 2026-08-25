"""
Report generation engine for Project Lucy.
Produces HTML, PDF (via WeasyPrint), and JSON reports.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("./data/reports")
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "reports"


def _ensure_dirs() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class ReportEngine:
    """Generate structured engagement reports."""

    _instance: Optional["ReportEngine"] = None

    def __new__(cls) -> "ReportEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def generate(
        self,
        report_type: str,
        fmt: str,
        agent_ids: Optional[list[str]] = None,
        date_range: Optional[dict] = None,
    ) -> dict:
        """
        Returns {"report_id": str, "path": str, "status": "done"}.
        report_type: "engagement" | "credentials" | "technical"
        fmt: "html" | "pdf" | "json"
        """
        _ensure_dirs()
        report_id = str(uuid.uuid4())

        data = self._collect_data(report_type, agent_ids, date_range)

        if fmt == "json":
            path = self._render_json(report_id, report_type, data)
        elif fmt in ("html", "pdf"):
            html = self._render_html(report_type, data)
            if fmt == "pdf":
                path = self._render_pdf(report_id, html)
            else:
                path = REPORTS_DIR / f"{report_id}.html"
                path.write_text(html, encoding="utf-8")
                path = str(path)
        else:
            raise ValueError(f"Unknown format: {fmt}")

        return {"report_id": report_id, "path": str(path), "status": "done", "format": fmt, "type": report_type}

    # --- Data collection ---

    def _collect_data(self, report_type: str, agent_ids, date_range) -> dict:
        from db.models import Agent, Task, Credential, Log, Timeline, Finding

        agents_q = Agent.select()
        if agent_ids:
            agents_q = agents_q.where(Agent.id.in_(agent_ids))

        agents = [a.to_dict() for a in agents_q]
        agent_id_set = {a["id"] for a in agents}

        tasks_q = Task.select().order_by(Task.created_at.desc())
        if agent_ids:
            tasks_q = tasks_q.where(Task.agent_id.in_(agent_id_set))
        tasks = [t.to_dict() for t in tasks_q]

        creds_q = Credential.select().order_by(Credential.captured_at.desc())
        if agent_ids:
            creds_q = creds_q.where(Credential.agent_id.in_(agent_id_set))
        credentials = [c.to_dict() for c in creds_q]

        logs_q = Log.select().order_by(Log.timestamp.desc()).limit(500)
        if agent_ids:
            logs_q = logs_q.where(Log.agent_id.in_(agent_id_set))
        logs = [l.to_dict() for l in logs_q]

        try:
            timelines = [t.to_dict() for t in Timeline.select()]
        except Exception:
            timelines = []

        try:
            manual_findings = [f.to_dict() for f in Finding.select().order_by(Finding.created_at.desc())]
        except Exception:
            manual_findings = []

        completed = sum(1 for t in tasks if t.get("status") == "completed")
        failed    = sum(1 for t in tasks if t.get("status") == "failed")
        total     = len(tasks)
        success_rate = round(completed / total * 100, 1) if total else 0

        modules_used: dict[str, int] = {}
        for t in tasks:
            m = t.get("module", "unknown")
            modules_used[m] = modules_used.get(m, 0) + 1
        top_modules = sorted(modules_used.items(), key=lambda x: x[1], reverse=True)[:10]

        per_agent: list[dict] = []
        for a in agents:
            aid = a["id"]
            a_tasks  = [t for t in tasks       if t.get("agent_id") == aid]
            a_creds  = [c for c in credentials if c.get("agent_id") == aid]
            a_done   = sum(1 for t in a_tasks if t.get("status") == "completed")
            per_agent.append({
                "id": aid,
                "hostname": a.get("hostname", "—"),
                "os": a.get("os", "—"),
                "username": a.get("username", "—"),
                "ip_private": a.get("ip_private", "—"),
                "ip_public": a.get("ip_public", "—"),
                "status": a.get("status", "—"),
                "last_seen": a.get("last_seen", "—"),
                "task_count": len(a_tasks),
                "completed_tasks": a_done,
                "credential_count": len(a_creds),
            })

        auto_findings = self._generate_findings(agents, tasks, credentials)
        findings = manual_findings + auto_findings

        cred_by_source: dict[str, int] = {}
        for c in credentials:
            src = c.get("source", "unknown")
            cred_by_source[src] = cred_by_source.get(src, 0) + 1

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_type": report_type,
            "agents": agents,
            "per_agent": per_agent,
            "tasks": tasks,
            "credentials": credentials,
            "logs": logs,
            "timelines": timelines,
            "findings": findings,
            "manual_findings": manual_findings,
            "top_modules": top_modules,
            "cred_by_source": cred_by_source,
            "summary": {
                "total_agents": len(agents),
                "online_agents":  sum(1 for a in agents if a.get("status") == "online"),
                "total_tasks": total,
                "completed_tasks": completed,
                "failed_tasks": failed,
                "success_rate": success_rate,
                "total_credentials": len(credentials),
                "total_timelines": len(timelines),
                "total_findings": len(findings),
                "findings_critical": sum(1 for f in findings if f["severity"] == "critical"),
                "findings_high":     sum(1 for f in findings if f["severity"] == "high"),
                "findings_medium":   sum(1 for f in findings if f["severity"] == "medium"),
                "findings_low":      sum(1 for f in findings if f["severity"] == "low"),
            },
        }

        if report_type == "executive":
            data["executive_summary"] = self._generate_executive_summary(data)
            data["key_takeaways"] = self._generate_key_takeaways(data)
            data["charts"] = self._build_charts(data)

        return data

    # --- Executive AI-style summary helpers ---

    def _generate_executive_summary(self, data: dict) -> str:
        s = data["summary"]
        parts = [
            f"This engagement involved {s['total_agents']} agent(s), {s['total_tasks']} task(s), and resulted in {s['total_credentials']} credential(s) harvested.",
        ]
        if s["total_agents"] > 0:
            parts.append(f"{s['online_agents']} agent(s) remain online, indicating active persistence.")
        if s["total_credentials"] > 0:
            parts.append(f"Credentials were collected from {len(data['cred_by_source'])} distinct source(s), demonstrating significant exposure of stored secrets.")
        if s["total_findings"] > 0:
            parts.append(f"{s['total_findings']} security finding(s) were identified, including {s['findings_critical']} critical and {s['findings_high']} high severity issues.")
        if s["failed_tasks"] > 0:
            parts.append(f"{s['failed_tasks']} task(s) failed, suggesting possible detection or privilege limitations on target endpoints.")
        if s["success_rate"] >= 80:
            parts.append("Overall mission success rate is high, indicating weak endpoint controls and effective operator tradecraft.")
        elif s["success_rate"] < 50:
            parts.append("Overall mission success rate is low, suggesting stronger detection or defensive posture than expected.")
        return " ".join(parts)

    def _generate_key_takeaways(self, data: dict) -> str:
        s = data["summary"]
        takeaways = []
        if s["total_credentials"] > 10:
            takeaways.append("credential storage is a major weakness")
        if s["findings_critical"] > 0:
            takeaways.append("immediate remediation is required for critical findings")
        if s["online_agents"] > 0:
            takeaways.append("active implants require incident response")
        if s["failed_tasks"] > 0:
            takeaways.append("review detection coverage and failed task logs")
        if not takeaways:
            takeaways.append("no significant activity detected")
        return "; ".join(takeaways).capitalize() + "."

    # --- SVG chart helpers (embedded in HTML/PDF) ---

    def _build_charts(self, data: dict) -> dict[str, str]:
        s = data["summary"]
        task_distribution = {
            "Completed": s["completed_tasks"],
            "Failed": s["failed_tasks"],
            "Other": s["total_tasks"] - s["completed_tasks"] - s["failed_tasks"],
        }

        os_distribution: dict[str, int] = {}
        for a in data["agents"]:
            os_name = a.get("os", "unknown") or "unknown"
            os_distribution[os_name] = os_distribution.get(os_name, 0) + 1

        severity_distribution = {
            "Critical": s["findings_critical"],
            "High": s["findings_high"],
            "Medium": s["findings_medium"],
            "Low": s["findings_low"],
        }

        return {
            "tasks_pie": self._build_svg_pie(task_distribution, "Task Distribution", ["#22c55e", "#ef4444", "#6b7280"]),
            "modules_bar": self._build_svg_bar(dict(data["top_modules"]), "Top Modules", "#3b82f6"),
            "os_pie": self._build_svg_pie(os_distribution, "OS Distribution", ["#8b5cf6", "#06b6d4", "#f59e0b", "#10b981", "#6b7280"]),
            "creds_bar": self._build_svg_bar(data["cred_by_source"], "Credentials by Source", "#f97316"),
            "severity_bar": self._build_svg_bar(severity_distribution, "Findings by Severity", "#ef4444"),
        }

    def _build_svg_pie(self, data: dict, title: str, colors: list) -> str:
        values = [v for v in data.values() if v > 0]
        labels = [k for k, v in data.items() if v > 0]
        if not values:
            return f'<svg viewBox="0 0 300 200" xmlns="http://www.w3.org/2000/svg"><text x="150" y="100" text-anchor="middle" fill="#8b949e">No data</text></svg>'
        total = sum(values)
        cx, cy, r = 100, 100, 80
        start_angle = -90
        slices = []
        legend = []
        for i, (label, value) in enumerate(zip(labels, values)):
            angle = value / total * 360
            x1 = cx + r * self._cos_deg(start_angle)
            y1 = cy + r * self._sin_deg(start_angle)
            x2 = cx + r * self._cos_deg(start_angle + angle)
            y2 = cy + r * self._sin_deg(start_angle + angle)
            large = 1 if angle > 180 else 0
            path = f"M {cx} {cy} L {x1} {y1} A {r} {r} 0 {large} 1 {x2} {y2} Z"
            color = colors[i % len(colors)]
            slices.append(f'<path d="{path}" fill="{color}" stroke="#0d1117" stroke-width="2"/>')
            start_angle += angle
            legend.append(f'<text x="210" y="{35 + i * 22}" fill="{color}" font-size="12">● {label}: {value}</text>')
        return f"""<svg viewBox="0 0 330 200" xmlns="http://www.w3.org/2000/svg">
  <text x="10" y="20" fill="#e6edf3" font-size="14" font-weight="bold">{title}</text>
  {''.join(slices)}
  {''.join(legend)}
</svg>"""

    def _build_svg_bar(self, data: dict, title: str, color: str) -> str:
        if not data:
            return f'<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg"><text x="200" y="100" text-anchor="middle" fill="#8b949e">No data</text></svg>'
        labels = list(data.keys())
        values = list(data.values())
        max_v = max(max(values), 1)
        chart_h = 140
        chart_w = 320
        bar_w = chart_w / len(labels) * 0.6
        gap = chart_w / len(labels) * 0.4
        bars = []
        for i, (label, value) in enumerate(zip(labels, values)):
            h = value / max_v * chart_h
            x = 40 + i * (bar_w + gap) + gap / 2
            y = 160 - h
            bars.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}" rx="3"/>')
            bars.append(f'<text x="{x + bar_w / 2}" y="{y - 5}" text-anchor="middle" fill="#e6edf3" font-size="10">{value}</text>')
            bars.append(f'<text x="{x + bar_w / 2}" y="175" text-anchor="middle" fill="#8b949e" font-size="10">{label}</text>')
        return f"""<svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
  <text x="10" y="20" fill="#e6edf3" font-size="14" font-weight="bold">{title}</text>
  <line x1="40" y1="160" x2="360" y2="160" stroke="#30363d" stroke-width="1"/>
  {''.join(bars)}
</svg>"""

    @staticmethod
    def _cos_deg(angle: float) -> float:
        import math
        return math.cos(math.radians(angle))

    @staticmethod
    def _sin_deg(angle: float) -> float:
        import math
        return math.sin(math.radians(angle))

    def _generate_findings(self, agents: list, tasks: list, credentials: list) -> list[dict]:
        findings: list[dict] = []

        if credentials:
            findings.append({
                "id": "F-001",
                "title": f"{len(credentials)} credential(s) harvested",
                "severity": "critical",
                "description": f"The agent successfully extracted {len(credentials)} stored credentials from browsers, credential managers, and environment variables.",
                "recommendation": "Enable credential encryption at rest, enforce MFA on all accounts, and audit browser password managers usage.",
                "evidence": f"Sources: {', '.join(set(c.get('source','?') for c in credentials[:10]))}",
            })

        browser_creds = [c for c in credentials if c.get("source") in ("chrome", "firefox", "edge", "brave")]
        if browser_creds:
            findings.append({
                "id": "F-002",
                "title": f"Browser saved passwords exposed ({len(browser_creds)} entries)",
                "severity": "high",
                "description": "Passwords stored in browser profiles were accessible without elevation of privilege.",
                "recommendation": "Disable browser password manager via GPO. Use a dedicated password manager with hardware-backed encryption.",
                "evidence": f"{len(browser_creds)} passwords from browser profiles",
            })

        failed_tasks = [t for t in tasks if t.get("status") == "failed"]
        if failed_tasks:
            findings.append({
                "id": "F-003",
                "title": f"{len(failed_tasks)} task(s) failed — partial detection possible",
                "severity": "medium",
                "description": "Some agent tasks failed, potentially due to AV/EDR intervention or missing privileges. This may indicate partial detection.",
                "recommendation": "Review failed task logs. Correlate with AV/EDR alerts to confirm detection coverage.",
                "evidence": f"Failed modules: {', '.join(set(t.get('module','?') for t in failed_tasks[:5]))}",
            })

        online_agents = [a for a in agents if a.get("status") == "online"]
        if online_agents:
            findings.append({
                "id": "F-004",
                "title": f"{len(online_agents)} agent(s) still active / persistent",
                "severity": "high" if len(online_agents) > 1 else "medium",
                "description": f"{len(online_agents)} agent(s) maintain an active C2 connection, indicating successful persistence or undetected implant.",
                "recommendation": "Implement network segmentation, outbound traffic inspection, and EDR behavioral monitoring for C2 beaconing.",
                "evidence": f"Active agents: {', '.join(a.get('hostname','?') for a in online_agents[:5])}",
            })

        if len(agents) > 0:
            findings.append({
                "id": "F-005",
                "title": "Initial access achieved on all target endpoints",
                "severity": "critical",
                "description": f"Agent was successfully deployed and executed on {len(agents)} endpoint(s) without triggering security controls.",
                "recommendation": "Review endpoint hardening, application whitelisting (AppLocker/WDAC), and user awareness training.",
                "evidence": f"Compromised hosts: {', '.join(a.get('hostname','?') for a in agents[:5])}",
            })

        return findings

    # --- Renderers ---

    def _render_json(self, report_id: str, report_type: str, data: dict) -> str:
        path = REPORTS_DIR / f"{report_id}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(path)

    def _render_html(self, report_type: str, data: dict) -> str:
        template_path = TEMPLATES_DIR / f"{report_type}.html"
        if template_path.exists():
            try:
                from jinja2 import Environment, FileSystemLoader
                env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
                tmpl = env.get_template(f"{report_type}.html")
                return tmpl.render(**data)
            except ImportError:
                pass

        return self._fallback_html(data)

    def _render_pdf(self, report_id: str, html: str) -> str:
        path = REPORTS_DIR / f"{report_id}.pdf"
        try:
            from weasyprint import HTML
            HTML(string=html).write_pdf(str(path))
        except ImportError:
            html_path = REPORTS_DIR / f"{report_id}.html"
            html_path.write_text(html, encoding="utf-8")
            path = html_path
            logger.warning("WeasyPrint not installed — fell back to HTML.")
        return str(path)

    def _fallback_html(self, data: dict) -> str:
        s = data["summary"]
        agents_rows = "".join(
            f"<tr><td>{a.get('hostname')}</td><td>{a.get('os')}</td>"
            f"<td>{a.get('ip_public','')}</td><td>{a.get('status')}</td></tr>"
            for a in data["agents"]
        )
        creds_rows = "".join(
            f"<tr><td>{c.get('url','')}</td><td>{c.get('username')}</td>"
            f"<td>{c.get('source')}</td><td>{c.get('confidence')}</td></tr>"
            for c in data["credentials"]
        )
        sev_color = {"critical": "#ef4444", "high": "#f97316", "medium": "#f59e0b", "low": "#22c55e", "info": "#3b82f6"}
        findings_rows = "".join(
            f"<tr><td style='color:{sev_color.get(f.get('severity','info'),'#fff')}'>{f.get('severity','').upper()}</td>"
            f"<td>{f.get('title','')}</td><td>{f.get('status','')}</td></tr>"
            for f in data.get("findings", [])
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Lucy C2 — Report</title>
<style>
  body{{font-family:monospace;background:#0d1117;color:#e6edf3;padding:2rem}}
  h1{{color:#22c55e}} table{{border-collapse:collapse;width:100%;margin:1rem 0}}
  th,td{{border:1px solid #30363d;padding:.4rem .7rem;text-align:left}}
  th{{background:#161b22}} .badge{{padding:.1rem .4rem;border-radius:4px;font-size:.8em}}
  .ok{{color:#22c55e}} .warn{{color:#f59e0b}} .err{{color:#ef4444}}
</style></head>
<body>
<h1>Lucy C2 — Engagement Report</h1>
<p>Generated: {data['generated_at']}</p>
<h2>Summary</h2>
<ul>
  <li>Agents: {s['total_agents']} ({s['online_agents']} online)</li>
  <li>Tasks: {s['total_tasks']} ({s['completed_tasks']} done, {s['failed_tasks']} failed)</li>
  <li>Credentials collected: {s['total_credentials']}</li>
</ul>
<h2>Agents</h2>
<table><tr><th>Hostname</th><th>OS</th><th>IP</th><th>Status</th></tr>{agents_rows}</table>
<h2>Credentials</h2>
<table><tr><th>URL</th><th>Username</th><th>Source</th><th>Confidence</th></tr>{creds_rows}</table>
<h2>Findings ({s.get('total_findings', 0)})</h2>
<table><tr><th>Severity</th><th>Title</th><th>Status</th></tr>{findings_rows}</table>
</body></html>"""

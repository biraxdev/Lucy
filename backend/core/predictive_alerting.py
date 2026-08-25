"""
Predictive alerting engine for Project Lucy.

Analyzes historical data (tasks, logs, credentials, agent heartbeats) to
surface anomalies before they become critical:
  - task failure-rate spikes
  - agents at risk of going offline (heartbeat jitter)
  - credential-collection bursts
  - error/critical log spikes
  - baseline deviation for new agents

Results are stored as "predictions" and surfaced through the alert feed
as warning-level alerts when a threshold is crossed.
"""
import asyncio
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _z_score(value: float, mean: float, stdev: float) -> float:
    if stdev == 0:
        return 0.0
    return (value - mean) / stdev


class PredictiveAlertEngine:
    """Singleton predictive alert engine."""

    _instance: Optional["PredictiveAlertEngine"] = None

    def __new__(cls) -> "PredictiveAlertEngine":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._predictions: list[dict] = []
            inst._task: Optional[asyncio.Task] = None
            inst._loop: Optional[asyncio.AbstractEventLoop] = None
            inst._lock = asyncio.Lock()
            inst._running = False
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        current_loop = asyncio.get_running_loop()
        if self._running and self._loop is current_loop and self._task and not self._task.done():
            return
        if self._task and self._loop is not current_loop:
            self._task.cancel()
        self._running = True
        self._loop = current_loop
        interval = getattr(settings, "PREDICTIVE_ALERT_INTERVAL_SECONDS", 300)
        self._task = asyncio.create_task(self._analysis_loop(interval))
        logger.info("PredictiveAlertEngine started (interval=%ds).", interval)

    async def stop(self) -> None:
        self._running = False
        current_loop = asyncio.get_running_loop()
        if self._task:
            if self._loop is current_loop:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            else:
                self._task.cancel()
            self._task = None
        logger.info("PredictiveAlertEngine stopped.")

    async def _analysis_loop(self, interval: int) -> None:
        while self._running:
            try:
                await self.run_analysis()
            except Exception as exc:
                logger.error("Predictive analysis failed: %s", exc)
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_predictions(self, limit: int = 100) -> list[dict]:
        return list(reversed(self._predictions))[:limit]

    def get_active_threats(self) -> list[dict]:
        """Return predictions with severity warning or higher."""
        return [p for p in self._predictions if p.get("severity") in ("warning", "critical")]

    async def run_analysis(self) -> list[dict]:
        """Run all predictive heuristics and return generated predictions."""
        from database import database

        with database:
            new_predictions = []
            new_predictions.extend(self._analyze_task_failure_rate())
            new_predictions.extend(self._analyze_agent_offline_risk())
            new_predictions.extend(self._analyze_credential_burst())
            new_predictions.extend(self._analyze_log_anomaly())
            new_predictions.extend(self._analyze_new_agent_behavior())

        async with self._lock:
            for p in new_predictions:
                self._predictions.append(p)
            max_store = getattr(settings, "PREDICTIVE_ALERT_MAX_STORED", 500)
            if len(self._predictions) > max_store:
                self._predictions = self._predictions[-max_store:]

        for p in new_predictions:
            await self._emit_alert(p)

        return new_predictions

    # ------------------------------------------------------------------
    # Heuristics
    # ------------------------------------------------------------------

    def _analyze_task_failure_rate(self) -> list[dict]:
        """Compare the recent failure rate to the historical baseline."""
        from db.models import Task

        predictions: list[dict] = []
        window_recent = timedelta(hours=1)
        window_baseline = timedelta(hours=24)
        now = datetime.now(timezone.utc)

        recent = Task.select().where(Task.created_at >= now - window_recent)
        baseline = Task.select().where(
            Task.created_at >= now - window_baseline,
            Task.created_at < now - window_recent,
        )

        recent_total = recent.count()
        baseline_total = baseline.count()
        if recent_total < 5 or baseline_total < 10:
            return predictions

        recent_failed = recent.where(Task.status == "failed").count()
        baseline_failed = baseline.where(Task.status == "failed").count()

        recent_rate = recent_failed / recent_total
        baseline_rate = baseline_failed / baseline_total

        if baseline_rate == 0 and recent_rate > 0:
            baseline_rate = 0.01

        z = _z_score(recent_rate, baseline_rate, math.sqrt(baseline_rate * (1 - baseline_rate) / baseline_total))
        if z < 2.0 and recent_rate < baseline_rate * 2:
            return predictions

        severity = "critical" if recent_rate > 0.5 or z > 3 else "warning"
        predictions.append(self._make_prediction(
            kind="task_failure_spike",
            severity=severity,
            title="Predicted task failure spike",
            message=(
                f"Task failure rate is {recent_rate:.1%} over the last hour "
                f"(baseline {baseline_rate:.1%}, z={z:.2f})."
            ),
            data={
                "recent_rate": recent_rate,
                "baseline_rate": baseline_rate,
                "recent_total": recent_total,
                "baseline_total": baseline_total,
                "z_score": z,
            },
        ))
        return predictions

    def _analyze_agent_offline_risk(self) -> list[dict]:
        """Flag agents whose heartbeat interval is degrading (high jitter)."""
        from db.models import Agent, Task

        predictions: list[dict] = []
        now = datetime.now(timezone.utc)
        window = timedelta(hours=2)

        for agent in Agent.select().where(Agent.status.in_(["online", "idle"])):
            heartbeats = (
                Task.select()
                .where(
                    Task.agent == agent,
                    Task.module == "heartbeat",
                    Task.created_at >= now - window,
                )
                .order_by(Task.created_at.asc())
            )
            timestamps = [t.created_at for t in heartbeats]
            if len(timestamps) < 4:
                continue

            deltas = [
                (timestamps[i] - timestamps[i - 1]).total_seconds()
                for i in range(1, len(timestamps))
            ]
            if not deltas:
                continue
            avg_delta = _mean(deltas)
            std_delta = _stdev(deltas)
            cv = std_delta / avg_delta if avg_delta else 0
            last_seen = agent.last_seen or now
            seconds_since_last_seen = max(0, (now - last_seen.replace(tzinfo=timezone.utc)).total_seconds())

            offline_threshold = getattr(settings, "AGENT_OFFLINE_THRESHOLD", 120)
            if seconds_since_last_seen > offline_threshold * 0.6 or cv > 1.0:
                severity = "critical" if seconds_since_last_seen > offline_threshold * 0.8 else "warning"
                predictions.append(self._make_prediction(
                    kind="agent_offline_risk",
                    severity=severity,
                    title=f"Agent {agent.hostname} at risk of going offline",
                    message=(
                        f"Heartbeat jitter CV={cv:.2f}, last seen {seconds_since_last_seen:.0f}s ago "
                        f"(threshold {offline_threshold}s)."
                    ),
                    agent_id=str(agent.id),
                    data={
                        "hostname": agent.hostname,
                        "avg_heartbeat_interval": avg_delta,
                        "heartbeat_jitter_std": std_delta,
                        "coefficient_of_variation": cv,
                        "seconds_since_last_seen": seconds_since_last_seen,
                    },
                ))
        return predictions

    def _analyze_credential_burst(self) -> list[dict]:
        """Detect sudden credential-harvesting bursts."""
        from db.models import Credential

        predictions: list[dict] = []
        now = datetime.now(timezone.utc)
        recent_window = timedelta(minutes=15)
        baseline_window = timedelta(hours=24)

        recent_count = Credential.select().where(Credential.captured_at >= now - recent_window).count()
        baseline_count = Credential.select().where(
            Credential.captured_at >= now - baseline_window,
            Credential.captured_at < now - recent_window,
        ).count()

        if baseline_count < 1:
            return predictions

        baseline_rate = baseline_count / (baseline_window.total_seconds() / 60)
        recent_rate = recent_count / (recent_window.total_seconds() / 60)
        z = _z_score(recent_rate, baseline_rate, math.sqrt(baseline_rate))

        if z < 2.0 and recent_count < max(5, baseline_rate * 2):
            return predictions

        severity = "critical" if z > 3 or recent_count > 50 else "warning"
        predictions.append(self._make_prediction(
            kind="credential_burst",
            severity=severity,
            title="Predicted credential exfiltration burst",
            message=(
                f"{recent_count} credentials captured in the last 15 minutes "
                f"(baseline rate {baseline_rate:.1f}/min, z={z:.2f})."
            ),
            data={
                "recent_count": recent_count,
                "baseline_rate_per_min": baseline_rate,
                "recent_rate_per_min": recent_rate,
                "z_score": z,
            },
        ))
        return predictions

    def _analyze_log_anomaly(self) -> list[dict]:
        """Detect abnormal error/critical log rates."""
        from db.models import Log

        predictions: list[dict] = []
        now = datetime.now(timezone.utc)
        recent_window = timedelta(minutes=30)
        baseline_window = timedelta(hours=6)

        recent_errors = Log.select().where(
            Log.level.in_(["ERROR", "CRITICAL"]),
            Log.timestamp >= now - recent_window,
        ).count()
        baseline_errors = Log.select().where(
            Log.level.in_(["ERROR", "CRITICAL"]),
            Log.timestamp >= now - baseline_window,
            Log.timestamp < now - recent_window,
        ).count()

        baseline_slots = max(1, (baseline_window - recent_window).total_seconds() / recent_window.total_seconds())
        baseline_rate = baseline_errors / baseline_slots

        if baseline_rate < 1 and recent_errors < 5:
            return predictions

        z = _z_score(recent_errors, baseline_rate, math.sqrt(baseline_rate))
        if z < 2.0 and recent_errors < baseline_rate * 2:
            return predictions

        severity = "critical" if "CRITICAL" in [l.level for l in Log.select().where(Log.timestamp >= now - recent_window).limit(1)] else "warning"
        severity = "critical" if recent_errors > 50 else severity
        predictions.append(self._make_prediction(
            kind="log_error_spike",
            severity=severity,
            title="Predicted error/critical log spike",
            message=(
                f"{recent_errors} ERROR/CRITICAL logs in the last 30 minutes "
                f"(baseline {baseline_rate:.1f}/slot, z={z:.2f})."
            ),
            data={
                "recent_error_count": recent_errors,
                "baseline_rate_per_slot": baseline_rate,
                "z_score": z,
            },
        ))
        return predictions

    def _analyze_new_agent_behavior(self) -> list[dict]:
        """Flag newly seen agents that behave very differently from peers."""
        from db.models import Agent, Task

        predictions: list[dict] = []
        now = datetime.now(timezone.utc)
        cohort_window = timedelta(hours=24)

        new_agents = Agent.select().where(Agent.first_seen >= now - cohort_window)
        cohort = Agent.select().where(Agent.first_seen < now - cohort_window)

        if not new_agents.count() or not cohort.count():
            return predictions

        cohort_task_counts = [a.tasks.count() for a in cohort]
        cohort_mean = _mean(cohort_task_counts)
        cohort_std = _stdev(cohort_task_counts)

        for agent in new_agents:
            task_count = agent.tasks.count()
            z = _z_score(task_count, cohort_mean, cohort_std)
            if z > 2.5:
                predictions.append(self._make_prediction(
                    kind="new_agent_anomaly",
                    severity="warning",
                    title=f"New agent {agent.hostname} shows anomalous activity",
                    message=(
                        f"New agent executed {task_count} tasks in 24h "
                        f"(cohort mean {cohort_mean:.1f}, z={z:.2f})."
                    ),
                    agent_id=str(agent.id),
                    data={
                        "hostname": agent.hostname,
                        "task_count_24h": task_count,
                        "cohort_mean": cohort_mean,
                        "cohort_std": cohort_std,
                        "z_score": z,
                    },
                ))
        return predictions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_prediction(
        self,
        kind: str,
        severity: str,
        title: str,
        message: str,
        agent_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "kind": kind,
            "severity": severity,
            "title": title,
            "message": message,
            "agent_id": agent_id,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }

    async def _emit_alert(self, prediction: dict) -> None:
        """Surface high-confidence predictions through the alert manager."""
        if prediction.get("severity") not in ("warning", "critical"):
            return
        try:
            from core.alert_manager import AlertManager
            alert_manager = AlertManager()
            await alert_manager.fire(
                event="predictive_alert",
                title=prediction["title"],
                message=prediction["message"],
                severity=prediction["severity"],
                agent_id=prediction.get("agent_id"),
                data={
                    "prediction_id": prediction["id"],
                    "kind": prediction["kind"],
                    **prediction.get("data", {}),
                },
            )
        except Exception as exc:
            logger.debug("Failed to emit predictive alert: %s", exc)

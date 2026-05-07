"""LangGraph-powered multi-step incident investigation pipeline."""

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.incident_window import resolve_incident_window
from app.models.investigation import InvestigationState
from app.models.webhook import AlertPayload
from app.services import llm_engine, loki_client, prometheus_client, sanitizer

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    payload: AlertPayload
    past_solution: str | None
    alert_name: str
    state: str
    labels: dict[str, str]
    message: str
    dashboard_url: str | None
    incident_window: dict[str, Any]
    raw_logs: list[str]
    raw_metrics: dict[str, float]
    evidence: list[str]
    redacted_logs: list[str]
    redacted_metrics: dict[str, float]
    redaction_map: dict[str, str]
    diagnostic: dict[str, Any]
    confidence_score: float
    solution_steps: list[str]
    final_solution: str


async def extract_alert_node(state: GraphState) -> GraphState:
    payload = state["payload"]
    return {
        "alert_name": payload.alert_name,
        "state": payload.state,
        "labels": payload.labels,
        "message": payload.message,
        "dashboard_url": payload.dashboard_url,
    }


async def resolve_incident_window_node(state: GraphState) -> GraphState:
    window = resolve_incident_window(state["payload"])
    return {"incident_window": window.model_dump(mode="json")}


async def fetch_logs_node(state: GraphState) -> GraphState:
    labels = state.get("labels", {})
    window = state.get("incident_window", {})
    logs = await loki_client.get_logs(
        pod=labels.get("pod", "unknown"),
        namespace=labels.get("namespace", "app-demo"),
        limit=100,
        since=f"{window.get('lookback_minutes', 30)}m",
    )
    return {"raw_logs": logs}


async def fetch_metrics_node(state: GraphState) -> GraphState:
    labels = state.get("labels", {})
    metrics = await prometheus_client.get_metrics(
        pod=labels.get("pod", "unknown"),
        namespace=labels.get("namespace", "app-demo"),
    )
    return {"raw_metrics": metrics}


async def filter_and_redact_node(state: GraphState) -> GraphState:
    evidence, redaction_map, redacted_logs, redacted_metrics = sanitizer.filter_and_redact_evidence(
        logs=state.get("raw_logs", []),
        metrics=state.get("raw_metrics", {}),
        max_items=50,
    )
    return {
        "evidence": evidence,
        "redaction_map": redaction_map,
        "redacted_logs": redacted_logs,
        "redacted_metrics": redacted_metrics,
    }


def _estimate_confidence(diagnostic: dict[str, Any], evidence: list[str]) -> float:
    if not diagnostic:
        return 0.0
    base = 0.5 if diagnostic.get("cause_racine") else 0.3
    if diagnostic.get("actions_immediates"):
        base += 0.2
    if len(evidence) >= 20:
        base += 0.2
    return min(1.0, base)


async def diagnose_node(state: GraphState) -> GraphState:
    diagnostic = await llm_engine.analyze(
        alert_name=state.get("alert_name", "unknown"),
        message=state.get("message", ""),
        labels=state.get("labels", {}),
        cleaned_logs=state.get("redacted_logs", []),
        metrics=state.get("redacted_metrics", {}),
        past_solution=state.get("past_solution"),
    )
    confidence_score = _estimate_confidence(diagnostic, state.get("evidence", []))
    return {"diagnostic": diagnostic, "confidence_score": confidence_score}


async def build_solution_node(state: GraphState) -> GraphState:
    solution = state.get("diagnostic", {}).get("solution", "").strip()
    if not solution:
        return {"solution_steps": [], "final_solution": ""}

    lines = [line.strip("- ").strip() for line in solution.splitlines() if line.strip()]
    if not lines:
        lines = [solution]

    solution_steps = lines[:8]
    final_solution = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(solution_steps))
    return {"solution_steps": solution_steps, "final_solution": final_solution}


def _build_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("extract_alert", extract_alert_node)
    workflow.add_node("resolve_incident_window", resolve_incident_window_node)
    workflow.add_node("fetch_logs", fetch_logs_node)
    workflow.add_node("fetch_metrics", fetch_metrics_node)
    workflow.add_node("filter_and_redact", filter_and_redact_node)
    workflow.add_node("diagnose", diagnose_node)
    workflow.add_node("build_solution", build_solution_node)

    workflow.set_entry_point("extract_alert")
    workflow.add_edge("extract_alert", "resolve_incident_window")
    workflow.add_edge("resolve_incident_window", "fetch_logs")
    workflow.add_edge("fetch_logs", "fetch_metrics")
    workflow.add_edge("fetch_metrics", "filter_and_redact")
    workflow.add_edge("filter_and_redact", "diagnose")
    workflow.add_edge("diagnose", "build_solution")
    workflow.add_edge("build_solution", END)
    return workflow.compile()


graph = _build_graph()


class InvestigationPipeline:
    """Wrapper around compiled LangGraph for easy FastAPI integration."""

    def __init__(self) -> None:
        self._graph = graph

    async def run(self, payload: AlertPayload, past_solution: str | None = None) -> InvestigationState:
        final_state = await self._graph.ainvoke({"payload": payload, "past_solution": past_solution})
        logger.info("✅ LangGraph investigation completed", extra={"alert_name": payload.alert_name})
        return InvestigationState(
            alert_name=final_state.get("alert_name", payload.alert_name),
            state=final_state.get("state", payload.state),
            labels=final_state.get("labels", payload.labels),
            message=final_state.get("message", payload.message),
            dashboard_url=final_state.get("dashboard_url", payload.dashboard_url),
            incident_window=final_state.get("incident_window"),
            raw_logs=final_state.get("raw_logs", []),
            raw_metrics=final_state.get("raw_metrics", {}),
            redacted_logs=final_state.get("redacted_logs", []),
            redacted_metrics=final_state.get("redacted_metrics", {}),
            evidence=final_state.get("evidence", []),
            redaction_map=final_state.get("redaction_map", {}),
            diagnostic=final_state.get("diagnostic"),
            solution_steps=final_state.get("solution_steps", []),
            final_solution=final_state.get("final_solution", ""),
            confidence_score=final_state.get("confidence_score", 0.0),
            past_solution=past_solution,
        )

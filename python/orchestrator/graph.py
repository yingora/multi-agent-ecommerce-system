"""Linear LangGraph stages; parallel branches return explicit, non-mutating updates."""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from models.schemas import Product, UserProfile
from .supervisor import SupervisorOrchestrator


class PipelineState(TypedDict, total=False):
    request_id: str
    user_id: str
    scene: str
    num_items: int
    context: dict[str, Any]
    experiment_group: str
    ranking_strategy: str
    user_profile: UserProfile | None
    raw_products: list[Product]
    ranked_products: list[Product]
    available_ids: set[str]
    final_products: list[Product]
    marketing_copies: list[dict[str, str]]
    agent_results: dict[str, Any]
    total_latency_ms: float
    _start_time: float


def build_recommendation_graph(supervisor: SupervisorOrchestrator | None = None):
    workflow = supervisor if supervisor is not None else SupervisorOrchestrator()
    graph = StateGraph(PipelineState)
    nodes = [("init", workflow.initialize), ("parallel_phase1", workflow.parallel_phase1),
             ("parallel_phase2", workflow.parallel_phase2), ("filter", workflow.filter_products),
             ("marketing_copy", workflow.marketing_copy), ("aggregate", workflow.aggregate)]
    for name, node in nodes:
        graph.add_node(name, node)
    graph.set_entry_point("init")
    for (left, _), (right, _) in zip(nodes, nodes[1:]):
        graph.add_edge(left, right)
    graph.add_edge("aggregate", END)
    return graph.compile()

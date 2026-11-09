"""Fixed-stage workflow shared by the direct supervisor and LangGraph nodes."""
from __future__ import annotations

import asyncio
import time
import uuid

from agents import InventoryAgent, MarketingCopyAgent, ProductRecAgent, UserProfileAgent
from config import get_settings
from models.schemas import RecommendationRequest, RecommendationResponse
from services.ab_test import ABTestEngine


class SupervisorOrchestrator:
    def __init__(self, ab_engine: ABTestEngine | None = None):
        self.user_profile_agent = UserProfileAgent()
        self.product_rec_agent = ProductRecAgent()
        self.marketing_copy_agent = MarketingCopyAgent()
        self.inventory_agent = InventoryAgent()
        settings = get_settings()
        self.ab_engine = ab_engine or ABTestEngine(settings.ab_test_default_bucket_count)
        self.experiments_enabled = settings.ab_test_enabled

    async def initialize(self, state):
        request = RecommendationRequest.model_validate(state)
        experiment = (self.ab_engine.assign(request.user_id) if self.experiments_enabled
                      else {"group": "control", "config": {"rerank": "rule_based"}})
        # Reset every request-owned output, including inputs supplied to a reused graph.
        return {**request.model_dump(), "request_id": str(uuid.uuid4()),
                "_start_time": time.perf_counter(), "agent_results": {},
                "experiment_group": experiment["group"],
                "ranking_strategy": experiment["config"].get("rerank", "rule_based"),
                "user_profile": None, "raw_products": [], "ranked_products": [],
                "available_ids": set(), "final_products": [], "marketing_copies": [],
                "total_latency_ms": 0.0}

    async def parallel_phase1(self, state):
        profile, recall = await asyncio.gather(
            self.user_profile_agent.run(user_id=state["user_id"], context=state["context"]),
            self.product_rec_agent.run(user_profile=None, num_items=state["num_items"] * 2),
        )
        # Merge results, never entire snapshots. Neither branch mutates input state.
        return {"user_profile": getattr(profile, "profile", None) if profile.success else None,
                "raw_products": getattr(recall, "products", []) if recall.success else [],
                "agent_results": {**state["agent_results"], "user_profile": profile,
                                  "product_recall": recall}}

    async def parallel_phase2(self, state):
        ranked, inventory = await asyncio.gather(
            self.product_rec_agent.run(user_profile=state["user_profile"],
                candidates=state["raw_products"], strategy=state["ranking_strategy"],
                num_items=state["num_items"]),
            self.inventory_agent.run(products=state["raw_products"]),
        )
        return {"ranked_products": (getattr(ranked, "products", []) if ranked.success
                                    else state["raw_products"]),
                "available_ids": (set(getattr(inventory, "available_products", []))
                                  if inventory.success else set()),
                "agent_results": {**state["agent_results"], "rerank": ranked,
                                  "inventory": inventory}}

    async def filter_products(self, state):
        # Use canonical checked candidates, rejecting unknown/duplicate ranking IDs.
        checked = {p.product_id: p for p in state["raw_products"] if p.stock > 0
                   and p.product_id in state["available_ids"]}
        final, seen = [], set()
        for product in state["ranked_products"]:
            pid = product.product_id
            if pid in checked and pid not in seen:
                final.append(checked[pid])
                seen.add(pid)
        return {"final_products": final[:state["num_items"]]}

    async def marketing_copy(self, state):
        result = await self.marketing_copy_agent.run(
            user_profile=state["user_profile"], products=state["final_products"])
        return {"marketing_copies": getattr(result, "copies", []) if result.success else [],
                "agent_results": {**state["agent_results"], "marketing_copy": result}}

    async def aggregate(self, state):
        return {"total_latency_ms": (time.perf_counter() - state["_start_time"]) * 1000}

    @staticmethod
    def response(state):
        return RecommendationResponse(request_id=state["request_id"], user_id=state["user_id"],
            products=state["final_products"], marketing_copies=state["marketing_copies"],
            experiment_group=state["experiment_group"], agent_results=state["agent_results"],
            total_latency_ms=state["total_latency_ms"])

    async def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        state = await self.initialize(request.model_dump())
        for phase in (self.parallel_phase1, self.parallel_phase2, self.filter_products,
                      self.marketing_copy, self.aggregate):
            state = {**state, **await phase(state)}
        return self.response(state)

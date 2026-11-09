import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from agents.base_agent import BaseAgent
from agents.product_rec_agent import ProductRecAgent
from models.schemas import (AgentResult, InventoryResult, Product, ProductRecResult,
                           RecommendationRequest, UserProfile, UserProfileResult)
from orchestrator.graph import build_recommendation_graph
from orchestrator.supervisor import SupervisorOrchestrator


def product(pid="p", stock=10, category="A"):
    return Product(product_id=pid, name=pid, category=category, price=10, stock=stock)


@pytest.fixture
def workflow():
    w = SupervisorOrchestrator()
    w.user_profile_agent.run = AsyncMock(return_value=UserProfileResult(profile=UserProfile(user_id="u")))
    return w


@pytest.mark.parametrize("graph", [False, True])
@pytest.mark.parametrize("inventory_failed", [False, True])
@pytest.mark.parametrize("stock", [0, 10])
async def test_no_available_products_never_reappear(workflow, graph, inventory_failed, stock):
    p = product(stock=stock)
    workflow.product_rec_agent.run = AsyncMock(return_value=ProductRecResult(products=[p]))
    workflow.inventory_agent.run = AsyncMock(return_value=InventoryResult(
        success=not inventory_failed, available_products=[p.product_id] if inventory_failed else []))
    req = RecommendationRequest(user_id="u", num_items=1)
    if graph:
        response = workflow.response(await build_recommendation_graph(workflow).ainvoke(req.model_dump()))
    else:
        response = await workflow.recommend(req)
    assert response.products == []
    assert response.marketing_copies == []


@pytest.mark.parametrize("graph", [False, True])
async def test_shared_candidates_partial_stock_and_unknown_ids(workflow, graph):
    a, b, alien = product("a"), product("b", stock=0), product("unknown")
    workflow.product_rec_agent.run = AsyncMock(side_effect=[
        ProductRecResult(products=[a,b]), ProductRecResult(products=[alien,b,a,a])])
    workflow.inventory_agent.run = AsyncMock(return_value=InventoryResult(available_products=["a","b","unknown"]))
    req = RecommendationRequest(user_id="u", num_items=3)
    if graph:
        result = workflow.response(await build_recommendation_graph(workflow).ainvoke(req.model_dump()))
    else:
        result = await workflow.recommend(req)
    assert [p.product_id for p in result.products] == ["a"]
    assert workflow.product_rec_agent.run.call_args_list[1].kwargs["candidates"] == [a,b]
    assert workflow.inventory_agent.run.call_args.kwargs["products"] == [a,b]


async def test_branch_updates_preserve_outputs_without_mutating_input(workflow):
    state = await workflow.initialize({"user_id":"u", "num_items":2})
    state["user_profile"] = UserProfile(user_id="stale")
    state["ranked_products"] = [product("stale")]
    old_results = state["agent_results"]
    one = await workflow.parallel_phase1(state)
    assert state["user_profile"].user_id == "stale"
    assert old_results == {}
    assert one["user_profile"].user_id == "u"
    two = await workflow.parallel_phase2({**state, **one})
    assert all(p.product_id != "stale" for p in two["ranked_products"])
    assert set(two["agent_results"]) == {"user_profile","product_recall","rerank","inventory"}


async def test_compiled_graph_resets_stale_state_and_isolates_requests(workflow):
    graph = build_recommendation_graph(workflow)
    original = {"user_id":"u", "num_items":2, "user_profile":UserProfile(user_id="stale"),
                "ranked_products":[product("stale")], "agent_results":{"old":None}}
    a,b = await asyncio.gather(graph.ainvoke(original), graph.ainvoke({"user_id":"v", "num_items":1}))
    assert a["user_profile"].user_id == "u"
    assert len(a["final_products"]) == 2 and len(b["final_products"]) == 1
    assert a["request_id"] != b["request_id"]
    assert a["agent_results"] is not b["agent_results"]
    assert "old" not in a["agent_results"]
    assert original["agent_results"] == {"old":None}


async def test_rerank_failure_falls_back_only_to_checked_stock(workflow):
    a,b = product("a"),product("b",stock=0)
    workflow.product_rec_agent.run = AsyncMock(side_effect=[ProductRecResult(products=[a,b]),
        AgentResult(agent_name="product_rec",success=False)])
    workflow.inventory_agent.run = AsyncMock(return_value=InventoryResult(available_products=["a"]))
    response = await workflow.recommend(RecommendationRequest(user_id="u"))
    assert response.products == [a]
    assert not response.agent_results["rerank"].success


async def test_rule_and_llm_paths_apply_assignment(workflow):
    for strategy in ("rule_based","llm"):
        workflow.ab_engine.assign = lambda uid: {"group":strategy,"config":{"rerank":strategy}}
        workflow.product_rec_agent.run = AsyncMock(return_value=ProductRecResult(products=[product()]))
        response = await workflow.recommend(RecommendationRequest(user_id="u"))
        assert response.experiment_group == strategy
        assert workflow.product_rec_agent.run.call_args.kwargs["strategy"] == strategy
    workflow.experiments_enabled = False
    state = await workflow.initialize({"user_id":"u"})
    assert state["ranking_strategy"] == "rule_based"
    assert state["experiment_group"] == "control"


async def test_ranking_reuses_candidates_and_deduplicates():
    agent = ProductRecAgent()
    agent._recall = AsyncMock(side_effect=AssertionError("Must not recall again"))
    agent.llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content='["b","b","alien","a"]'))
    result = await agent.run(candidates=[product("a"),product("b")], user_profile=UserProfile(user_id="u"), strategy="llm", num_items=2)
    assert [p.product_id for p in result.products] == ["b","a"]
    agent.llm.ainvoke.reset_mock()
    result = await agent.run(candidates=[product("a"),product("b",category="B")], user_profile=UserProfile(user_id="u",preferred_categories=["B"]), strategy="rule_based", num_items=1)
    assert result.products[0].product_id == "b"
    agent.llm.ainvoke.assert_not_called()


class SlowAgent(BaseAgent):
    async def _execute(self, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled = True


async def test_timeout_cancels_and_returns_sanitized_failure():
    agent = SlowAgent("slow", timeout=0.01)
    result = await asyncio.wait_for(agent.run(), timeout=1)
    assert not result.success and result.error == "agent timed out"
    assert agent.cancelled and agent.error_rate == 1


async def test_timeout_includes_retry_backoff():
    class BrokenAgent(BaseAgent):
        async def _execute(self, **kwargs):
            raise RuntimeError("secret-api-key")
    agent = BrokenAgent("broken", timeout=0.01)
    result = await asyncio.wait_for(agent.run(), timeout=1)
    assert result.error == "agent timed out"
    agent = BrokenAgent("broken", max_retries=1)
    result = await agent.run()
    assert not result.success and result.error == "agent execution failed"
    assert "secret" not in result.model_dump_json()


async def test_caller_cancellation_propagates():
    agent = SlowAgent("slow")
    task = asyncio.create_task(agent.run())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert agent.cancelled


@pytest.mark.parametrize("kind,content", [("profile",'[]'), ("rank",'{}'), ("copy",'[{"product_id":"alien","copy":"text"}]')])
async def test_invalid_model_output_is_controlled(kind,content,workflow):
    agent = {"profile":workflow.user_profile_agent,"rank":workflow.product_rec_agent,
             "copy":workflow.marketing_copy_agent}[kind]
    # The fixture overrides run for profile; exercise the real class method here.
    agent.max_retries = 1
    agent.llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=content))
    result = await BaseAgent.run(agent, user_id="u", user_profile=UserProfile(user_id="u"),
                                 strategy="llm",candidates=[product()],products=[product()])
    assert not result.success and result.error == "agent execution failed"


def test_api_both_routes_validation_metrics_and_outcomes():
    import main
    with TestClient(main.app) as client:
        assert client.get('/health').json()['mode'] == 'offline'
        for route in ('recommend','recommend/graph'):
            response = client.post('/api/v1/'+route,json={'user_id':'demo','num_items':2})
            assert response.status_code == 200, response.text
            data = response.json()
            assert len(data['products']) == 2 and len(data['marketing_copies']) == 2
            assert len(data['agent_results']) == 5
            assert data['agent_results']['inventory']['available_products']
            for n in (0,-1,51):
                assert client.post('/api/v1/'+route,json={'user_id':'u','num_items':n}).status_code == 422
        assert client.get('/api/v1/metrics').json()['agents']['product_recall']['call_count'] >= 2
        assert client.post('/api/v1/experiments/missing/outcome?group=x&success=true').status_code == 404
        assert client.post('/api/v1/experiments/rec_strategy/outcome?group=control&success=true').status_code == 200


def test_graph_not_initialized_is_503(monkeypatch):
    import main
    monkeypatch.setattr(main,'rec_graph',None)
    with TestClient(main.app) as client:
        monkeypatch.setattr(main,'rec_graph',None)
        assert client.post('/api/v1/recommend/graph',json={'user_id':'u'}).status_code == 503


async def test_inventory_thresholds_and_limits(workflow):
    ps = [product(str(n), stock=n) for n in (0,50,100,300,301)]
    for p in ps: p.tags = ['新品']
    result = await workflow.inventory_agent.run(products=ps)
    assert result.success
    assert result.available_products == ['50','100','300','301']
    assert result.purchase_limits == {'50':1,'100':2,'300':3}
    assert [a['level'] for a in result.low_stock_alerts] == ['critical','warning']


async def test_retry_recovers_and_agent_settings_are_applied(monkeypatch):
    from config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv('ECOM_AGENT_TIMEOUT_PRODUCT_REC','0.25')
    try:
        agent = ProductRecAgent()
        assert agent.timeout == 0.25
    finally:
        get_settings.cache_clear()
    from tenacity import wait_none
    class FlakyAgent(BaseAgent):
        def __init__(self): super().__init__('flaky'); self.calls = 0
        async def _execute(self, **kwargs):
            self.calls += 1
            if self.calls == 1: raise RuntimeError('transient')
            return AgentResult(agent_name='flaky')
    # Avoid real backoff while exercising retry behavior.
    import agents.base_agent as base
    original = base.wait_exponential
    monkeypatch.setattr(base,'wait_exponential',lambda **kwargs:wait_none())
    flaky = FlakyAgent()
    result = await flaky.run()
    assert result.success and flaky.calls == 2 and flaky.error_rate == 0
    monkeypatch.setattr(base,'wait_exponential',original)


def test_live_mode_needs_key_without_constructing_client(monkeypatch):
    from config import get_settings
    from services.llm import create_model
    monkeypatch.setenv('ECOM_LLM_MODE','live')
    monkeypatch.setenv('ECOM_LLM_API_KEY','')
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError,match='requires a private'):
            create_model('profile',temperature=0,max_tokens=10)
    finally:
        get_settings.cache_clear()

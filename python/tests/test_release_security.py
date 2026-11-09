"""Release regressions: no raw provider analysis or unexpected copy metadata."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from agents.marketing_copy_agent import MarketingCopyAgent
from agents.user_profile_agent import UserProfileAgent
from models.schemas import Product


async def test_profile_does_not_return_raw_model_analysis():
    agent = UserProfileAgent()
    agent.llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=json.dumps({
        'segments':['active'], 'price_range':[0,100], 'private_analysis':'PRIVATE_SENTINEL'})))
    result = await agent.run(user_id='demo',context={})
    assert result.success
    assert result.data == {}
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()


async def test_copy_discards_unknown_provider_metadata():
    agent = MarketingCopyAgent()
    agent.llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=json.dumps([
        {'product_id':'p','copy':'Demo copy','private_metadata':'PRIVATE_SENTINEL'}])))
    p = Product(product_id='p', name='Demo', category='demo', price=1, stock=1)
    result = await agent.run(products=[p])
    assert result.success
    assert result.data == {}
    assert result.copies == [{'product_id':'p','copy':'Demo copy'}]
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()

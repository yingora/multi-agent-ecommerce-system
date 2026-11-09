import numpy as np
import pytest
from services.ab_test import ABTestEngine, Experiment


def test_seeded_thompson_sampling_and_outcomes():
    a,b = ABTestEngine(rng=np.random.default_rng(42)),ABTestEngine(rng=np.random.default_rng(42))
    for engine in (a,b):
        engine.record_outcome('rec_strategy','treatment_llm',True)
        engine.record_outcome('rec_strategy','control',False)
    assert [a.assign_thompson('u') for _ in range(20)] == [b.assign_thompson('u') for _ in range(20)]
    group = a.experiments['rec_strategy'].groups[1]
    assert group.successes == 2 and group.failures == 1


def test_sampler_uses_posterior_parameters():
    class FakeRng:
        def __init__(self): self.parameters = []
        def beta(self,a,b): self.parameters.append((a,b)); return a/(a+b)
    rng = FakeRng()
    engine = ABTestEngine(rng=rng)
    engine.record_outcome('rec_strategy','treatment_llm',True)
    assert engine.assign_thompson('u')['group'] == 'treatment_llm'
    assert rng.parameters == [(1,1),(2,1)]


def test_disabled_and_invalid_experiments():
    engine = ABTestEngine()
    engine.experiments['rec_strategy'].enabled = False
    assert engine.assign('u')['group'] == engine.assign_thompson('u')['group'] == 'control'
    with pytest.raises(KeyError): engine.record_outcome('rec_strategy','missing',True)
    with pytest.raises(KeyError): engine.record_outcome('missing','control',True)
    with pytest.raises(ValueError): ABTestEngine(bucket_count=0)
    with pytest.raises(ValueError): engine.register_experiment(Experiment(id='bad',name='bad',groups=[]))

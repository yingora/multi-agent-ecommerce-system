"""Hash-based experiment assignments and in-memory metric/posterior helpers.
Thompson Sampling is an experimental standalone function, not a serving policy."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Experiment:
    id: str
    name: str
    groups: list[ExperimentGroup]
    enabled: bool = True
    start_time: float = 0.0
    end_time: float = 0.0


@dataclass
class ExperimentGroup:
    name: str
    weight: int = 50
    config: dict[str, Any] = field(default_factory=dict)
    # Thompson Sampling state
    successes: int = 1
    failures: int = 1


class ABTestEngine:
    """Bucket-based A/B test engine with optional Thompson Sampling."""

    def __init__(self, bucket_count: int = 100, rng=None):
        if bucket_count <= 0:
            raise ValueError("bucket_count must be positive")
        self.rng = rng if rng is not None else np.random.default_rng()
        self.bucket_count = bucket_count
        self.experiments: dict[str, Experiment] = {}
        self._metrics: list[dict[str, Any]] = []
        self._init_default_experiments()

    def _init_default_experiments(self):
        self.register_experiment(
            Experiment(
                id="rec_strategy",
                name="推荐策略实验",
                groups=[
                    ExperimentGroup(name="control", weight=50, config={"rerank": "rule_based"}),
                    ExperimentGroup(name="treatment_llm", weight=50, config={"rerank": "llm"}),
                ],
            )
        )
        self.register_experiment(
            Experiment(
                id="copy_style",
                name="文案风格实验",
                groups=[
                    ExperimentGroup(name="formal", weight=50, config={"style": "formal"}),
                    ExperimentGroup(name="casual", weight=50, config={"style": "casual"}),
                ],
            )
        )

    def register_experiment(self, exp: Experiment):
        if (not exp.groups or len({g.name for g in exp.groups}) != len(exp.groups)
                or any(g.weight < 0 or g.successes <= 0 or g.failures <= 0 for g in exp.groups)
                or sum(g.weight for g in exp.groups) <= 0):
            raise ValueError("Invalid experiment groups, weights or Beta priors")
        self.experiments[exp.id] = exp

    def assign(self, user_id: str, experiment_id: str = "rec_strategy") -> dict[str, Any]:
        """Assign user to an experiment group using consistent hashing."""
        exp = self.experiments.get(experiment_id)
        if not exp or not exp.enabled:
            return {"group": "control", "config": {}}

        bucket = self._hash_bucket(user_id, experiment_id)
        group = self._bucket_to_group(bucket, exp.groups)
        return {"group": group.name, "config": group.config}

    def assign_thompson(self, user_id: str, experiment_id: str = "rec_strategy") -> dict[str, Any]:
        """Experimental process-local sampler; not used by serving routes.

        user_id is not used: repeated assignments are intentionally non-sticky.
        """
        exp = self.experiments.get(experiment_id)
        if not exp or not exp.enabled:
            return {"group": "control", "config": {}}

        samples = []
        for g in exp.groups:
            sample = self.rng.beta(g.successes, g.failures)
            samples.append((sample, g))

        best = max(samples, key=lambda x: x[0])[1]
        return {"group": best.name, "config": best.config}

    def record_outcome(self, experiment_id: str, group_name: str, success: bool):
        """Update Thompson Sampling posterior with observed outcome."""
        exp = self.experiments.get(experiment_id)
        if not exp or group_name not in {g.name for g in exp.groups}:
            raise KeyError("Unknown experiment or group")
        for g in exp.groups:
            if g.name == group_name:
                if success:
                    g.successes += 1
                else:
                    g.failures += 1
                break

    def record_metric(
        self,
        experiment_id: str,
        group_name: str,
        metric_name: str,
        value: float,
        user_id: str = "",
    ):
        self._metrics.append({
            "experiment_id": experiment_id,
            "group": group_name,
            "metric": metric_name,
            "value": value,
            "user_id": user_id,
            "timestamp": time.time(),
        })

    def get_stats(self, experiment_id: str) -> dict[str, Any]:
        """Aggregate metrics per group for a given experiment."""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return {}
        relevant = [m for m in self._metrics if m["experiment_id"] == experiment_id]
        stats: dict[str, dict[str, list[float]]] = {}
        for m in relevant:
            grp = m["group"]
            metric = m["metric"]
            if grp not in stats:
                stats[grp] = {}
            if metric not in stats[grp]:
                stats[grp][metric] = []
            stats[grp][metric].append(m["value"])

        result: dict[str, Any] = {}
        for grp, metrics in stats.items():
            result[grp] = {}
            for metric_name, values in metrics.items():
                arr = np.array(values)
                result[grp][metric_name] = {
                    "count": len(values),
                    "mean": float(arr.mean()),
                    "std": float(arr.std()),
                    "min": float(arr.min()),
                    "max": float(arr.max()),
                }
        return result

    def _hash_bucket(self, user_id: str, experiment_id: str) -> int:
        raw = f"{user_id}:{experiment_id}"
        h = hashlib.md5(raw.encode()).hexdigest()
        return int(h[:8], 16) % self.bucket_count

    def _bucket_to_group(
        self, bucket: int, groups: list[ExperimentGroup]
    ) -> ExperimentGroup:
        total_weight = sum(g.weight for g in groups)
        cumulative = 0
        normalized_bucket = bucket * total_weight / self.bucket_count
        for g in groups:
            cumulative += g.weight
            if normalized_bucket < cumulative:
                return g
        return groups[-1]

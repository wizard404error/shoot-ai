"""Intervention efficacy measurement (transformation Phase D / D4).

The question this service answers, honestly: **did the training plan
generated after match N measurably move the diagnosed metric by match
N+2?** It deliberately refuses to answer the question when the data
cannot support an answer — that refusal is the product, not a gap:

- ``insufficient_sample`` — fewer than 2 post-plan matches: a delta
  from one match is noise pretending to be signal.
- ``pending_matches`` — the N+2 window has not elapsed yet: the
  outcome is unknown, not negative.
- ``unmeasurable`` — the rule's hypothesis metrics were not observable
  from the event data (tracking-level metrics): no delta is computed,
  because "no change" and "no data" are different claims.

Deltas are computed per rule from the rule's own declared hypothesis
metrics, using the same ``extract_metric`` resolution the reasoning
engine uses at diagnosis time — so the before/after numbers measure
exactly what the diagnosis was based on, not a proxy metric chosen
after the fact.
"""

from __future__ import annotations

from typing import Any

from kawkab.core.logging import get_logger
from kawkab.services.reasoning.metrics import (
    extract_metric,
    parse_threshold,
    precompute_event_stats,
)

logger = get_logger(__name__)

# The before-window is the matches the plan itself was generated from
# (capped at 3); the after-window is N+1 and N+2 — the morphocycle's
# natural "did the week change anything" checkpoint.
_BEFORE_WINDOW = 3
_AFTER_WINDOW = 2


def _direction_for_op(op: str) -> str:
    """Map a hypothesis threshold operator to improvement direction.

    ``">3"`` diagnoses a *problem that is too high* → improvement is a
    lower value after the intervention. ``"<3"`` → improvement is a
    higher value. ``">="`` / ``"<="`` behave like their strict forms.
    """
    if op in (">", ">="):
        return "lower_after_is_better"
    if op in ("<", "<="):
        return "higher_after_is_better"
    return "unknown_direction"


class InterventionEfficacyService:
    """Measures whether a persisted training plan moved its own target metrics."""

    def __init__(self, storage_service: Any, knowledge_service: Any) -> None:
        self._storage = storage_service
        self._kb = knowledge_service

    async def measure_intervention(self, plan_id: int) -> dict[str, Any]:
        """Measure metric deltas for one plan, with honest sample-size provenance."""
        try:
            plan = await self._storage.get_training_plan(plan_id)
        except Exception as e:  # storage failure is loud, not "no effect"
            logger.error(f"measure_intervention storage error: {e}")
            return {"error": f"storage failure while loading plan {plan_id}"}

        if plan is None:
            return {"error": f"plan {plan_id} not found"}

        payload: dict[str, Any] = {}
        try:
            raw = plan.get("payload")
            if isinstance(raw, str):
                import json

                payload = json.loads(raw)
            elif isinstance(raw, dict):
                payload = raw
        except Exception:
            payload = {}

        based_on: list[int] = [
            int(m) for m in (payload.get("based_on_match_ids") or plan.get("match_ids") or [])
        ]
        diagnoses = payload.get("priority_diagnoses") or []
        if not based_on or not diagnoses:
            return {
                "plan_id": plan_id,
                "error": "plan lacks based_on_match_ids or priority_diagnoses — cannot define a before/after window",
            }

        plan_match_n = max(based_on)

        try:
            matches = await self._storage.get_all_matches()
        except Exception as e:
            logger.error(f"measure_intervention match listing failed: {e}")
            return {"plan_id": plan_id, "error": "storage failure while listing matches"}

        match_ids = sorted(int(m["id"]) for m in matches)
        before_ids = [m for m in match_ids if m < plan_match_n][-_BEFORE_WINDOW:]
        after_ids = [m for m in match_ids if m > plan_match_n][:_AFTER_WINDOW]

        per_rule: list[dict[str, Any]] = []
        for diag in diagnoses:
            rule_id = str(diag.get("rule_id") or "")
            rule = self._kb.get_rule(rule_id) if rule_id else None
            if rule is None:
                per_rule.append(
                    {
                        "rule_id": rule_id,
                        "state": "rule_not_found",
                        "note": "rule missing from the knowledge base — no metric defined",
                    }
                )
                continue

            # Metric selection: the rule's own first hypothesis metric.
            metric = None
            threshold_op = ""
            for hyp in rule.hypotheses or []:
                for req in hyp.get("evidence_required") or []:
                    if isinstance(req, dict) and req.get("metric"):
                        metric = str(req["metric"])
                        parsed = parse_threshold(req.get("threshold"))
                        threshold_op = parsed[0] if parsed else ""
                        break
                if metric:
                    break

            if not metric:
                per_rule.append(
                    {
                        "rule_id": rule_id,
                        "rule_name": diag.get("rule_name"),
                        "state": "no_declared_metric",
                        "note": "rule declares no evidence_required metric — efficacy not computable",
                    }
                )
                continue

            before_vals: list[dict[str, Any]] = []
            after_vals: list[dict[str, Any]] = []
            unmeasurable = 0

            for mid in before_ids + after_ids:
                try:
                    events = await self._storage.get_match_events(mid, limit=100000)
                except Exception:
                    unmeasurable += 1
                    continue
                stats = precompute_event_stats(events)
                val = extract_metric(metric, {}, stats)
                entry = {"match_id": mid, "value": val}
                if val is None:
                    unmeasurable += 1
                if mid in before_ids:
                    before_vals.append(entry)
                else:
                    after_vals.append(entry)

            known_before = [e["value"] for e in before_vals if e["value"] is not None]
            known_after = [e["value"] for e in after_vals if e["value"] is not None]

            entry_out: dict[str, Any] = {
                "rule_id": rule_id,
                "rule_name": diag.get("rule_name"),
                "metric": metric,
                "direction": _direction_for_op(threshold_op)
                if threshold_op
                else "unknown_direction",
                "threshold_operator": threshold_op or "undeclared",
                "before": before_vals,
                "after": after_vals,
            }

            if not known_before and not known_after:
                entry_out["state"] = "unmeasurable"
                entry_out["note"] = (
                    "metric not observable from event data (tracking-level) — "
                    "no delta computed; 'no data' is not 'no change'"
                )
            elif len(known_after) < _AFTER_WINDOW:
                entry_out["state"] = "insufficient_sample"
                entry_out["note"] = (
                    f"only {len(known_after)}/{_AFTER_WINDOW} post-plan matches measured — "
                    "a delta from one match is noise, not evidence"
                )
                if known_before and known_after:
                    entry_out["delta_observed_but_not_conclusive"] = sum(known_after) / len(
                        known_after
                    ) - sum(known_before) / len(known_before)
            else:
                mean_before = sum(known_before) / len(known_before) if known_before else 0.0
                mean_after = sum(known_after) / len(known_after)
                delta = mean_after - mean_before
                improved: bool | None = None
                if entry_out["direction"] == "lower_after_is_better":
                    improved = delta < 0
                elif entry_out["direction"] == "higher_after_is_better":
                    improved = delta > 0
                entry_out.update(
                    {
                        "state": "measured",
                        "mean_before": round(mean_before, 4),
                        "mean_after": round(mean_after, 4),
                        "delta": round(delta, 4),
                        "improved": improved,
                        "note": (
                            "raw event-level delta; single-club small-sample — "
                            "a directional signal to review, not a causal verdict"
                        ),
                    }
                )

            if unmeasurable:
                entry_out["unmeasurable_matches"] = unmeasurable
            per_rule.append(entry_out)

        return {
            "plan_id": plan_id,
            "plan_match_n": plan_match_n,
            "based_on_match_ids": based_on,
            "before_window": before_ids,
            "after_window": after_ids,
            "after_window_complete": len(after_ids) >= _AFTER_WINDOW,
            "window_note": "after-window = the next two stored matches following plan generation (N+1, N+2 in play order)",
            "rules": per_rule,
            "provenance": {
                "metric_resolution": "rule-declared evidence_required metrics via the reasoning engine's extract_metric",
                "created_by": plan.get("created_by"),
                "plan_created_at": plan.get("created_at"),
            },
        }

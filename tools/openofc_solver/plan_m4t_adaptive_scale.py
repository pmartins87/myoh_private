from __future__ import annotations

"""Evidence-driven scale planner for M4S sealed Fantasy/Fantasy measurements."""

from dataclasses import asdict, dataclass
import argparse, hashlib, json
from pathlib import Path
from typing import Mapping, Sequence

M4S_SCHEMA = "openofc-m4s-heldout-report-v1"
PLAN_SCHEMA = "openofc-m4t-adaptive-scale-plan-v1"
AUTHORITY = "EVIDENCE_DRIVEN_SCALE_PLANNER_NOT_POLICY_AUTHORITY"
COUNTS = (14, 15, 16, 17)


def _bytes(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(payload: Mapping[str, object]) -> str:
    raw = dict(payload); raw.pop("sha256", None)
    return hashlib.sha256(_bytes(raw)).hexdigest()


def state(button, p0, p1):
    return f"b{button}:p0f{p0}:p1f{p1}"


def all_states():
    return tuple(state(b, a, c) for a in COUNTS for c in COUNTS for b in (0, 1))


def coverage_tiers():
    t0 = tuple(state(b, 14, 14) for b in (0, 1))
    pairs1 = ((14, 15), (15, 14), (15, 15))
    t1 = tuple(state(b, a, c) for a, c in pairs1 for b in (0, 1))
    pairs2 = tuple((a, c) for a in (14, 15, 16) for c in (14, 15, 16)
                   if (a, c) not in ((14, 14),) + pairs1)
    t2 = tuple(state(b, a, c) for a, c in pairs2 for b in (0, 1))
    used = set(t0 + t1 + t2)
    return t0, t1, t2, tuple(s for s in all_states() if s not in used)


@dataclass(frozen=True)
class Requirements:
    seeds: int = 3
    worlds: int = 6
    gap_samples: int = 12
    def __post_init__(self):
        if min(self.seeds, self.worlds, self.gap_samples) <= 0:
            raise ValueError("evidence requirements must be positive")


@dataclass(frozen=True)
class Targets:
    mean_support_gap: float | None = None
    max_deviation: float | None = None
    mean_q_mae: float | None = None
    max_q_error: float | None = None
    @property
    def complete(self):
        return all(v is not None for v in asdict(self).values())
    def __post_init__(self):
        if any(v is not None and v < 0 for v in asdict(self).values()):
            raise ValueError("error targets must be non-negative")


def validate_report(r):
    if r.get("schema") != M4S_SCHEMA: raise ValueError("unsupported M4S report schema")
    if r.get("sha256") != sha(r): raise ValueError("M4S report SHA-256 mismatch")
    if not isinstance(r.get("heldout"), list) or not isinstance(r.get("config"), Mapping):
        raise ValueError("M4S report missing config/heldout")
    needed = ("base_seed","train_worlds_per_state","heldout_worlds_per_state",
              "synthetic_worlds","max_candidates","selfplay_iterations",
              "epochs_per_iteration","temperature","model_buckets",
              "replay_capacity","support_gap_samples")
    if any(k not in r["config"] for k in needed): raise ValueError("M4S config incomplete")


def signature(r):
    cfg = dict(r["config"]); cfg.pop("base_seed", None)
    return hashlib.sha256(_bytes({
        "generator": r["generator_fingerprint"],
        "continuation": r["continuation_fingerprint"],
        "states": sorted(r["states"]), "config": cfg})).hexdigest()


def validate_set(reports):
    if not reports: raise ValueError("M4T requires M4S reports")
    for r in reports: validate_report(r)
    if len({signature(r) for r in reports}) != 1:
        raise ValueError("M4S reports are not the same experiment configuration")
    seeds = [int(r["config"]["base_seed"]) for r in reports]
    if len(seeds) != len(set(seeds)): raise ValueError("duplicate M4S base_seed")
    return signature(reports[0])


def summarize(reports):
    validate_set(reports); grouped = {}
    for r in reports:
        seed0 = int(r["config"]["base_seed"])
        for row in r["heldout"]: grouped.setdefault(row["state"], []).append((seed0, row))
    out = {}
    for s, rows in sorted(grouped.items()):
        dev = [float(x["support_restricted_deviation"]) for _, x in rows]
        mae = [float(x["action_value_mae"]) for _, x in rows]
        qmax = [float(x["action_value_max_abs_error"]) for _, x in rows]
        gap_sum = gap_n = 0; gap_max = None
        for _, x in rows:
            n = int(x["support_gap_samples_per_player"])
            for k in ("p0_sampled_exact_support_gap", "p1_sampled_exact_support_gap"):
                if x.get(k) is not None and n > 0:
                    v = float(x[k]); gap_sum += v*n; gap_n += n
                    gap_max = v if gap_max is None else max(gap_max, v)
        out[s] = {
            "independent_seeds": len({seed0 for seed0, _ in rows}),
            "heldout_worlds": len(rows), "support_gap_samples": gap_n,
            "mean_deviation": sum(dev)/len(dev), "max_deviation": max(dev),
            "mean_q_mae": sum(mae)/len(mae), "max_q_error": max(qmax),
            "mean_support_gap": gap_sum/gap_n if gap_n else None,
            "max_support_gap": gap_max,
        }
    return out


def decide(e, req: Requirements, t: Targets):
    reasons = []
    if e["independent_seeds"] < req.seeds: reasons.append("independent_seeds")
    if e["heldout_worlds"] < req.worlds: reasons.append("heldout_worlds")
    if e["support_gap_samples"] < req.gap_samples: reasons.append("support_gap_samples")
    ready = not reasons
    checks = {
        "support_ok": None if t.mean_support_gap is None or e["mean_support_gap"] is None else e["mean_support_gap"] <= t.mean_support_gap,
        "policy_ok": None if t.max_deviation is None else e["max_deviation"] <= t.max_deviation,
        "q_mae_ok": None if t.mean_q_mae is None else e["mean_q_mae"] <= t.mean_q_mae,
        "q_max_ok": None if t.max_q_error is None else e["max_q_error"] <= t.max_q_error,
    }
    if not ready: status = "MORE_EVIDENCE_REQUIRED"
    elif not t.complete: status = "TARGET_CALIBRATION_REQUIRED"; reasons.append("numeric_targets")
    elif all(v is True for v in checks.values()): status = "STATE_BUDGETS_PASS"
    else: status = "SCALE_REQUIRED"
    return {"status": status, "evidence_ready": ready, "reasons": reasons, **checks}


def next_seeds(sig, existing, count):
    used = set(existing); out = []; nonce = 0
    while len(out) < count:
        d = hashlib.sha256(f"M4T-SEED|{sig}|{nonce}".encode()).digest(); nonce += 1
        x = 1_000_000_000 + int.from_bytes(d[:4], "big") % 1_000_000_000
        if x not in used: used.add(x); out.append(x)
    return out


def next_coverage(decisions):
    passed = {s for s, d in decisions.items() if d["status"] == "STATE_BUDGETS_PASS"}
    tiers = coverage_tiers()
    for i, tier in enumerate(tiers):
        if not all(s in decisions for s in tier): return ()
        if not all(s in passed for s in tier): return ()
        if i+1 < len(tiers):
            nxt = tuple(s for s in tiers[i+1] if s not in decisions)
            if nxt: return nxt
    return ()


def scaled(cfg, support, policy, function):
    x = dict(cfg); x.pop("base_seed", None)
    if support:
        x["synthetic_worlds"] = max(2, int(x["synthetic_worlds"])*2)
        x["max_candidates"] = max(8, int(x["max_candidates"])*2)
    if policy:
        x["selfplay_iterations"] = max(2, int(x["selfplay_iterations"])*2)
        x["epochs_per_iteration"] = max(2, int(x["epochs_per_iteration"])*2)
    if function:
        x["model_buckets"] = max(1<<16, int(x["model_buckets"])*2)
        x["replay_capacity"] = max(100000, int(x["replay_capacity"])*2)
        x["epochs_per_iteration"] = max(2, int(x["epochs_per_iteration"])*2)
    return x


def build_plan(reports, req: Requirements, targets: Targets):
    sig = validate_set(reports); evidence = summarize(reports)
    decisions = {s: decide(e, req, targets) for s, e in evidence.items()}
    seeds = [int(r["config"]["base_seed"]) for r in reports]
    short = any(not d["evidence_ready"] for d in decisions.values())
    sf = any(d["support_ok"] is False for d in decisions.values())
    pf = any(d["policy_ok"] is False for d in decisions.values())
    qf = any(d["q_mae_ok"] is False or d["q_max_ok"] is False for d in decisions.values())
    actions = []
    if short:
        missing = max(1, req.seeds - min(e["independent_seeds"] for e in evidence.values()))
        actions.append({"kind":"MEASURE_MORE_INDEPENDENT_EVIDENCE","priority":1,
                        "suggested_base_seeds":next_seeds(sig,seeds,missing),
                        "preserve_generator_config":True})
    elif not targets.complete:
        actions.append({"kind":"CALIBRATE_AND_SUPPLY_NUMERIC_TARGETS","priority":1})
    else:
        p = 1
        for failure, kind, generator in ((sf,"EXPAND_PROPOSAL_SUPPORT",True),
                                         (pf,"TRAIN_SELFPLAY_LONGER",False),
                                         (qf,"EXPAND_FUNCTION_APPROXIMATOR",False)):
            if failure: actions.append({"kind":kind,"priority":p,"changes_generator_fingerprint":generator}); p += 1
        if not (sf or pf or qf) and all(d["status"]=="STATE_BUDGETS_PASS" for d in decisions.values()):
            nxt = next_coverage(decisions)
            if nxt: actions.append({"kind":"EXPAND_FANTASY_COUNT_COVERAGE","priority":1,"states":list(nxt)})
            elif set(decisions)==set(all_states()): actions.append({"kind":"OUTER_CONTINUATION_INTEGRATION_CANDIDATE","priority":1})
            else: actions.append({"kind":"FILL_CURRENT_COVERAGE_TIER","priority":1})
    plan = {
        "schema":PLAN_SCHEMA,"authority":AUTHORITY,"promotion_blocked":True,
        "experiment_signature":sig,"input_report_sha256":[r["sha256"] for r in reports],
        "independent_base_seeds":seeds,"evidence_requirements":asdict(req),
        "error_targets":asdict(targets),"state_evidence":evidence,
        "state_decisions":decisions,"recommended_actions":actions,
        "recommended_next_config_without_seed":scaled(reports[0]["config"], sf and not short and targets.complete, pf and not short and targets.complete, qf and not short and targets.complete),
        "outer_continuation_ready_candidate":any(a["kind"]=="OUTER_CONTINUATION_INTEGRATION_CANDIDATE" for a in actions),
    }
    plan["sha256"] = sha(plan); return plan


def load(path):
    x = json.loads(path.read_text(encoding="utf-8")); validate_report(x); return x


def main():
    p = argparse.ArgumentParser(); p.add_argument("--report", type=Path, action="append", required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--min-independent-seeds", type=int, default=3); p.add_argument("--min-heldout-worlds-per-state", type=int, default=6); p.add_argument("--min-support-gap-samples-per-state", type=int, default=12)
    p.add_argument("--target-mean-support-gap", type=float); p.add_argument("--target-max-support-deviation", type=float); p.add_argument("--target-action-value-mae", type=float); p.add_argument("--target-action-value-max", type=float)
    a = p.parse_args(); reports = [load(x) for x in a.report]
    plan = build_plan(reports, Requirements(a.min_independent_seeds,a.min_heldout_worlds_per_state,a.min_support_gap_samples_per_state), Targets(a.target_mean_support_gap,a.target_max_support_deviation,a.target_action_value_mae,a.target_action_value_max))
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(plan,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(plan["recommended_actions"],sort_keys=True,indent=2))


if __name__ == "__main__": main()

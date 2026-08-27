from __future__ import annotations
import copy
from plan_m4t_adaptive_scale import Targets, Requirements, all_states, sha, build_plan, coverage_tiers, validate_report, validate_set


def fake(seed, states=("b0:p0f14:p1f14","b1:p0f14:p1f14"), gap=.1, dev=.1, mae=.1, qmax=.2, worlds=2, samples=2, generator="g1"):
    held=[]
    for s in states:
        for w in range(worlds):
            held.append({"state":s,"world_index":w,"p0_candidates":4,"p1_candidates":4,"p0_jokers":0,"p1_jokers":0,
                         "support_restricted_deviation":dev,"p0_support_deviation":dev/2,"p1_support_deviation":dev/2,
                         "action_value_mae":mae,"action_value_max_abs_error":qmax,
                         "p0_sampled_exact_support_gap":gap,"p1_sampled_exact_support_gap":gap,
                         "support_gap_samples_per_player":samples})
    x={"schema":"openofc-m4s-heldout-report-v1","authority":"x","promotion_blocked":True,
       "generator_fingerprint":generator,"continuation_fingerprint":"c1","states":list(states),
       "config":{"base_seed":seed,"train_worlds_per_state":2,"heldout_worlds_per_state":worlds,
                 "synthetic_worlds":2,"max_candidates":8,"selfplay_iterations":2,"epochs_per_iteration":2,
                 "temperature":1.0,"model_buckets":65536,"replay_capacity":100000,"support_gap_samples":samples},
       "train_iterations":[],"heldout":held,"heldout_aggregate":{},"model_checkpoint_sha256":"m","error_budgets":{},"next_action":"x"}
    x["sha256"]=sha(x); return x


def req(): return Requirements(3,6,12)
def targets(): return Targets(.2,.2,.2,.3)

def main():
    r=fake(1); validate_report(r); bad=copy.deepcopy(r); bad["heldout"][0]["action_value_mae"]=99
    try: validate_report(bad); raise AssertionError("tamper accepted")
    except ValueError as e: assert "SHA-256" in str(e)
    try: validate_set([fake(1),fake(1)]); raise AssertionError("duplicate accepted")
    except ValueError as e: assert "duplicate" in str(e)
    try: validate_set([fake(1),fake(2,generator="g2")]); raise AssertionError("mixed accepted")
    except ValueError as e: assert "same experiment" in str(e)

    p=build_plan([fake(1)],req(),targets()); assert p["recommended_actions"][0]["kind"]=="MEASURE_MORE_INDEPENDENT_EVIDENCE"
    p=build_plan([fake(i,gap=.4) for i in (1,2,3)],req(),targets()); assert "EXPAND_PROPOSAL_SUPPORT" in [a["kind"] for a in p["recommended_actions"]]; assert p["recommended_next_config_without_seed"]["max_candidates"]==16
    p=build_plan([fake(i,dev=.5,mae=.4,qmax=.6) for i in (1,2,3)],req(),targets()); kinds=[a["kind"] for a in p["recommended_actions"]]; assert "TRAIN_SELFPLAY_LONGER" in kinds and "EXPAND_FUNCTION_APPROXIMATOR" in kinds; assert p["recommended_next_config_without_seed"]["model_buckets"]==131072
    p=build_plan([fake(i) for i in (1,2,3)],req(),Targets()); assert p["recommended_actions"][0]["kind"]=="CALIBRATE_AND_SUPPLY_NUMERIC_TARGETS"
    p=build_plan([fake(i) for i in (1,2,3)],req(),targets()); assert p["recommended_actions"][0]["kind"]=="EXPAND_FANTASY_COUNT_COVERAGE"; assert set(p["recommended_actions"][0]["states"])==set(coverage_tiers()[1])
    p=build_plan([fake(i,states=all_states()) for i in (1,2,3)],req(),targets()); assert p["recommended_actions"][0]["kind"]=="OUTER_CONTINUATION_INTEGRATION_CANDIDATE" and p["outer_continuation_ready_candidate"] and p["promotion_blocked"]
    print("OPENOFC_M4T_ADAPTIVE_SCALE=PASS")

if __name__=="__main__": main()

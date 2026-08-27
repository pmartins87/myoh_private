from __future__ import annotations

from fantasy_response_frontier import mask_pair_count
from normal_fantasy_feasibility import parse_counts, terminal_state


def test_terminal_probe_states_cover_all_fantasy_sizes() -> None:
    for count in (14, 15, 16, 17):
        state = terminal_state(20260826 + count, count)
        assert state.terminal()
        assert state.normal_board.complete()
        assert len(state.plan.fantasy_packet) == count
        assert len(state.normal_discards) == 4
        assert len(set(state.plan.all_cards())) == count + 17


def test_mask_pair_growth_warns_against_blind_exact_training() -> None:
    counts = [mask_pair_count(count) for count in (14, 15, 16, 17)]
    assert counts == [252252, 756756, 2018016, 4900896]
    assert counts == sorted(counts)
    assert counts[-1] / counts[0] > 19.0


def test_count_parser_is_strict() -> None:
    assert parse_counts("14,16,17") == (14, 16, 17)
    try:
        parse_counts("14,14")
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate count must fail")


def main() -> None:
    test_terminal_probe_states_cover_all_fantasy_sizes()
    test_mask_pair_growth_warns_against_blind_exact_training()
    test_count_parser_is_strict()
    print(
        "OPENOFC_M4G_FEASIBILITY_PLUMBING=PASS "
        "F17_vs_F14_mask_growth=GT19X exact_scale=MEASURE_BEFORE_TRAINING"
    )


if __name__ == "__main__":
    main()

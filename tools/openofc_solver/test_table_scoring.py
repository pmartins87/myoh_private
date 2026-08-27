from __future__ import annotations

from engine import Board, Card
from table_scoring import PairScore, score_table, scoring_order, settle_pair_scores


def C(text: str) -> Card:
    return Card.parse(text)


def test_scoring_order() -> None:
    assert scoring_order(2, 1) == ((0, 1),)
    assert scoring_order(2, 0) == ((1, 0),)
    assert scoring_order(3, 2) == ((0, 1), (0, 2), (1, 2))
    assert scoring_order(3, 0) == ((1, 2), (1, 0), (2, 0))


def test_sequential_cap_is_zero_sum_and_order_sensitive() -> None:
    # Rule order: A beats B for 15, A beats C for 5, then B beats C for 4.
    # Everyone starts with 10.  The first transfer caps A at +10 and B at -10;
    # A cannot receive the later 5 from C, while B can still win 4 back from C.
    pairs = (
        PairScore(0, 1, 15),
        PairScore(0, 2, 5),
        PairScore(1, 2, 4),
    )
    settlements, net = settle_pair_scores(
        pairs, starting_funds=(10.0, 10.0, 10.0), blind=1.0
    )
    assert tuple(round(x, 9) for x in net) == (10.0, -6.0, -4.0)
    assert abs(sum(net)) < 1e-9
    assert settlements[0].applied_transfer == 10.0
    assert settlements[0].unsettled_gap == 5.0
    assert settlements[1].applied_transfer == 0.0
    assert settlements[1].unsettled_gap == 5.0
    assert settlements[2].applied_transfer == 4.0
    assert settlements[2].unsettled_gap == 0.0


def test_uncapped_settlement_matches_raw_pair_transfers() -> None:
    pairs = (
        PairScore(0, 1, 6),
        PairScore(0, 2, -3),
        PairScore(1, 2, 2),
    )
    settlements, net = settle_pair_scores(
        pairs, starting_funds=(1000.0, 1000.0, 1000.0), blind=2.0
    )
    assert not any(x.unsettled_gap for x in settlements)
    # A +12 vs B, loses 6 to C; B loses 12 then wins 4 from C.
    assert net == (6.0, -8.0, 2.0)


def test_real_board_pair_scoring_and_money_conservation() -> None:
    first = Board(
        top=(C("2c"), C("3d"), C("4s")),
        middle=(C("5c"), C("5d"), C("6h"), C("7s"), C("8c")),
        bottom=(C("9c"), C("9d"), C("Th"), C("Js"), C("Qc")),
    )
    second = Board(
        top=(C("6c"), C("7d"), C("8s")),
        middle=(C("Tc"), C("Td"), C("Jh"), C("Qs"), C("Kc")),
        bottom=(C("Ac"), C("Ad"), C("2h"), C("3s"), C("4c")),
    )
    result = score_table(
        (first, second),
        dealer=1,
        starting_funds=(1000.0, 1000.0),
        blind=1.0,
    )
    assert len(result.pair_scores) == 1
    assert len(result.settlements) == 1
    assert not result.cap_bound
    assert abs(sum(result.net_profit)) < 1e-9
    assert result.net_profit[0] == -result.net_profit[1]


def main() -> None:
    test_scoring_order()
    test_sequential_cap_is_zero_sum_and_order_sensitive()
    test_uncapped_settlement_matches_raw_pair_transfers()
    test_real_board_pair_scoring_and_money_conservation()
    print("OPENOFC_TABLE_SCORING_TEST=PASS")


if __name__ == "__main__":
    main()

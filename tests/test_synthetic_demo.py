from scripts.run_synthetic_backtest import run_demo


def test_synthetic_demo_runs_end_to_end():
    result = run_demo()
    assert len(result.fills) == 3
    assert result.fees_paid > 0.0
    assert result.gross_total_pnl != result.net_total_pnl
    assert dict(result.final_positions)["SYNTH-100-C"] == -6.0

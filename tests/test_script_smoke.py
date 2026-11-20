"""Smoke tests: the documented commands run verbatim on committed/generated data."""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_phase1_uses_committed_sample(monkeypatch, capsys):
    from scripts import run_phase1

    monkeypatch.chdir(REPO_ROOT)
    run_phase1.main()
    assert "call price=" in capsys.readouterr().out


def test_benchmark_main_uses_committed_sample(monkeypatch, capsys):
    from benchmarks import benchmark_simulator

    monkeypatch.chdir(REPO_ROOT)
    benchmark_simulator.main()
    assert "Pricing benchmark" in capsys.readouterr().out


def test_walk_forward_synthetic(tmp_path):
    from scripts import run_walk_forward

    output = tmp_path / "wf.json"
    folds = run_walk_forward.main(["--synthetic", "informed", "--seed", "1", "--output", str(output)])
    payload = json.loads(output.read_text())
    assert payload["synthetic"] is True
    assert payload["configuration"]["synthetic_scenario"] == "informed"
    assert len(folds) == len(payload["folds"]) == 3


def test_walk_forward_missing_real_data_has_clear_error(tmp_path, capsys):
    from scripts import run_walk_forward

    with pytest.raises(SystemExit) as excinfo:
        run_walk_forward.main([
            "--events", str(tmp_path / "missing.csv"),
            "--arrival-panel", str(tmp_path / "missing_panel.csv"),
        ])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "real market data not found" in err
    assert "--synthetic" in err


def test_synthetic_experiment_writes_labelled_outputs(tmp_path):
    from scripts import run_synthetic_experiment

    summary = run_synthetic_experiment.main([
        "--scenarios", "random_walk", "--seeds", "2", "--n-events", "600",
        "--bootstrap", "200", "--output-dir", str(tmp_path),
    ])
    assert list(summary["scenario"]) == ["random_walk"]
    report = (tmp_path / "synthetic_walkforward.md").read_text()
    assert "SYNTHETIC" in report
    assert (tmp_path / "synthetic_walkforward.csv").exists()
    assert (tmp_path / "synthetic_walkforward_seeds.csv").exists()
    low, high = summary.loc[0, ["diff_ci95_low", "diff_ci95_high"]]
    assert low <= summary.loc[0, "mean_diff"] <= high


def test_generate_synthetic_data_script(tmp_path):
    from scripts import generate_synthetic_data

    generate_synthetic_data.main([
        "--sample-ticks", str(tmp_path / "ticks.csv"),
        "--research-events", "trending", "--output-dir", str(tmp_path),
    ])
    assert (tmp_path / "ticks.csv").exists()
    assert (tmp_path / "research_events_trending_seed0.csv").exists()
    assert (tmp_path / "arrival_panel_trending_seed0.csv").exists()

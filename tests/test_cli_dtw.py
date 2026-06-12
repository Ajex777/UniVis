"""Tests for the UniVis DTW command-line entrypoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from pika_fixtures import write_pika_raw_episode
from univis.cli_dtw import DTWCLI
from univis.utils.json_io import read_json


def test_cli_compare_writes_json_and_png(tmp_path: Path) -> None:
    """Verify compare exports GUI-equivalent JSON plus a static PNG."""

    source = tmp_path / "raw"
    write_pika_raw_episode(source, "episode0", frames=56)
    write_pika_raw_episode(source, "episode1", frames=56)
    output = tmp_path / "dtw_compare"

    code = DTWCLI().run([
        "compare",
        "--source",
        str(source),
        "--current",
        "episode1",
        "--reference",
        "episode0",
        "--output",
        str(output),
    ])

    json_files = list(output.glob("compare_episode1_vs_episode0_*.json"))
    png_files = list(output.glob("compare_episode1_vs_episode0_*.png"))
    assert code == 0
    assert len(json_files) == 1
    assert len(png_files) == 1
    assert png_files[0].stat().st_size > 0
    payload = read_json(json_files[0])
    assert payload["current_episode_id"] == "episode1"
    assert payload["reference_episode_id"] == "episode0"
    assert "visual_links" in payload["left"]


def test_cli_compare_accepts_input_format_alias(tmp_path: Path) -> None:
    """Verify `--if` and format aliases are accepted case-insensitively."""

    source = tmp_path / "raw"
    write_pika_raw_episode(source, "episode0", frames=56)
    write_pika_raw_episode(source, "episode1", frames=56)
    output = tmp_path / "dtw_compare_alias"

    code = DTWCLI().run([
        "compare",
        "--source",
        str(source),
        "--if",
        "pikaraw",
        "--current",
        "episode1",
        "--reference",
        "episode0",
        "--output",
        str(output),
    ])

    assert code == 0
    assert len(list(output.glob("compare_episode1_vs_episode0_*.json"))) == 1


def test_cli_stats_all_excludes_reference_and_writes_json(tmp_path: Path) -> None:
    """Verify stats --all compares every non-reference episode."""

    source = tmp_path / "raw"
    write_pika_raw_episode(source, "episode0", frames=56)
    write_pika_raw_episode(source, "episode1", frames=56)
    write_pika_raw_episode(source, "episode2", frames=56)
    output = tmp_path / "dtw_stats"

    code = DTWCLI().run([
        "stats",
        "--source",
        str(source),
        "--reference",
        "episode0",
        "--all",
        "--output",
        str(output),
    ])

    json_files = list(output.glob("stats_episode0_*.json"))
    assert code == 0
    assert len(json_files) == 1
    payload = read_json(json_files[0])
    assert payload["reference_episode_id"] == "episode0"
    assert payload["selected_episode_ids"] == ["episode1", "episode2"]
    assert all(item["episode_id"] != "episode0" for item in payload["abnormal_episodes"])


def test_cli_unknown_input_format_prints_candidates(capsys) -> None:
    """Verify bad format values print available names and aliases."""

    with pytest.raises(SystemExit) as exc:
        DTWCLI().run([
            "stats",
            "--source",
            "/tmp/missing",
            "--if",
            "unknown-format",
            "--reference",
            "episode0",
            "--all",
        ])
    err = capsys.readouterr().err
    assert exc.value.code == 2
    assert "unknown input format" in err
    assert "PikaRawEpisodeAdapter" in err
    assert "PIKARaw" in err

import json
from pathlib import Path

import larped_cli as cli

REPORT = json.loads((Path(__file__).parent / "fixtures" / "turf.json").read_text())


def test_render_has_verdict_flags_tree_and_disclaimer():
    out = cli.render(REPORT)
    assert out.splitlines()[1] == "Strong larp signals"
    assert "Red flags" in out and "Money trail" in out and "Not financial advice." in out
    assert "\033[" not in out  # no colour codes unless asked


def test_saved_report_first_then_scan(monkeypatch):
    calls = []

    def fake(path, timeout=300):
        calls.append(path)
        return (200, {"stale": True}) if path.startswith("/api/report") else (200, {"headline": "fresh"})
    monkeypatch.setattr(cli, "fetch", fake)
    assert cli.get_report("M" * 44)["headline"] == "fresh"
    assert calls == ["/api/report/" + "M" * 44, "/api/scan/" + "M" * 44]
    calls.clear()
    monkeypatch.setattr(cli, "fetch", lambda p, timeout=300: (calls.append(p), (200, {"headline": "saved"}))[1])
    assert cli.get_report("M" * 44)["headline"] == "saved" and len(calls) == 1


def test_errors_are_readable(monkeypatch):
    monkeypatch.setattr(cli, "fetch", lambda p, timeout=300: (404, {}) if "report" in p else (429, {}))
    try:
        cli.get_report("M" * 44)
        raise AssertionError("expected exit")
    except SystemExit as e:
        assert "too many scans" in str(e)
    assert cli.main(["short"]) == 2

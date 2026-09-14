import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.core.repository_analysis import RepositoryAnalyzer
from harness.core.security import ToolSecurityError


class FakeAgent:
    class Settings:
        WORKSPACE = Path(tempfile.gettempdir())

    settings = Settings()

    def orchestrate(self, tasks, **kwargs):
        assert kwargs["tools"] == ["list_dir", "read_file", "grep"]
        assert kwargs["workers"] == 4
        return [json.dumps({"summary": "ok", "findings": [{
            "severity": "high", "title": "示例问题", "file": "app.py", "line": 3,
            "evidence": "证据", "impact": "影响", "recommendation": "建议",
            "confidence": "high",
        }]}) for _ in tasks]


def test_repository_analyzer_returns_four_categories_and_deduplicates():
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        FakeAgent.Settings.WORKSPACE = workspace
        (workspace / "app.py").write_text("print('ok')", encoding="utf-8")
        report = RepositoryAnalyzer(FakeAgent()).analyze(".")
        assert report.status == "completed"
        assert len(report.results) == 4
        assert {result.role for result in report.results} == {
            "security", "performance", "testing", "architecture"
        }
        assert len(report.findings) == 4
        assert "发现项：4" in report.to_markdown()


def test_repository_analyzer_rejects_workspace_escape_and_invalid_focus():
    with tempfile.TemporaryDirectory() as directory:
        FakeAgent.Settings.WORKSPACE = Path(directory)
        (Path(directory) / "repo").mkdir()
        analyzer = RepositoryAnalyzer(FakeAgent())
        with pytest.raises(ToolSecurityError):
            analyzer.analyze("../outside")
        with pytest.raises(ValueError):
            analyzer.analyze("repo", focus=["unknown"])

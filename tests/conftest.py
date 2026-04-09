from __future__ import annotations

from pathlib import Path

import pytest


FILE_MARKERS: dict[str, tuple[str, ...]] = {
    "test_feishu_login.py": ("ui", "auth"),
    "test_intelligent_review_flow.py": ("ui", "review_flow", "regression"),
    "test_checklist_module.py": ("ui", "checklist", "regression"),
    "test_review_rule_module.py": ("ui", "review_rule", "regression"),
    "test_review_checklist_import.py": ("ui", "checklist_import", "smoke", "regression"),
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        filename = Path(str(item.fspath)).name
        for marker_name in FILE_MARKERS.get(filename, ()):
            item.add_marker(getattr(pytest.mark, marker_name))

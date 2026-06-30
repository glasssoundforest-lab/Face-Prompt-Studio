"""
fps-tools/tests/unit/test_comfyui_backup_node.py

FacePromptBackupNode のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_comfyui_backup_node.py -v
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.nodes.face_prompt_backup import FacePromptBackupNode


@pytest.fixture(autouse=True)
def isolate_backup_manager(tmp_path, monkeypatch):
    """各テストで独立した BackupManager を使うようにモンキーパッチする"""
    import comfyui.nodes.face_prompt_backup as fb
    from backup.manager import BackupManager
    from backup.models import BackupTarget

    fb._backup_manager = None

    def _get_isolated_manager():
        source_dir = tmp_path / "rules"
        source_dir.mkdir(exist_ok=True)
        (source_dir / "base_rules.json").write_text('{"version": "1.0", "rules": []}')

        bm = BackupManager(
            backup_dir=tmp_path / "backup",
            max_count=5,
            source_dirs={BackupTarget.RULES: source_dir},
        )
        bm.setup()
        return bm

    monkeypatch.setattr(fb, "_get_backup_manager", _get_isolated_manager)
    yield


class TestFacePromptBackupNode:
    def test_registered(self):
        from comfyui import NODE_CLASS_MAPPINGS

        assert "FacePromptBackup" in NODE_CLASS_MAPPINGS

    def test_display_name(self):
        from comfyui import NODE_DISPLAY_NAME_MAPPINGS

        assert "🎭" in NODE_DISPLAY_NAME_MAPPINGS["FacePromptBackup"]

    def test_total_node_count_is_nine(self):
        from comfyui import NODE_CLASS_MAPPINGS

        assert len(NODE_CLASS_MAPPINGS) == 9

    def test_input_types_structure(self):
        types = FacePromptBackupNode.INPUT_TYPES()
        assert "action" in types["required"]

    def test_return_types(self):
        assert FacePromptBackupNode.RETURN_TYPES == ("STRING",)

    def test_function_name(self):
        assert FacePromptBackupNode.FUNCTION == "manage_backup"

    def test_list_action_no_crash(self):
        node = FacePromptBackupNode()
        (report,) = node.manage_backup(action="list")
        assert "Face Prompt Backup" in report
        assert "Statistics" in report

    def test_backup_rules_action_creates_backup(self):
        node = FacePromptBackupNode()
        (report,) = node.manage_backup(action="backup_rules")
        assert "[OK]" in report or "backup(backup_rules)" in report

    def test_restore_without_id_shows_error(self):
        node = FacePromptBackupNode()
        (report,) = node.manage_backup(action="restore", restore_id="")
        assert "restore_id" in report

    def test_restore_with_invalid_id(self):
        node = FacePromptBackupNode()
        (report,) = node.manage_backup(action="restore", restore_id="nonexistent_id")
        assert "[ERROR]" in report

    def test_backup_then_restore_flow(self, tmp_path: Path, monkeypatch):
        """同一 BackupManager インスタンスを共有して backup→restore の流れを検証する"""
        import comfyui.nodes.face_prompt_backup as fb
        from backup.manager import BackupManager
        from backup.models import BackupTarget

        source_dir = tmp_path / "rules2"
        source_dir.mkdir(exist_ok=True)
        (source_dir / "base_rules.json").write_text('{"version": "1.0", "rules": []}')

        shared_bm = BackupManager(
            backup_dir=tmp_path / "backup2",
            max_count=5,
            source_dirs={BackupTarget.RULES: source_dir},
        )
        shared_bm.setup()
        monkeypatch.setattr(fb, "_get_backup_manager", lambda: shared_bm)

        node = FacePromptBackupNode()
        (report1,) = node.manage_backup(action="backup_rules")

        match = re.search(r"rules_\d+_\d+_\d+_\S+\.json", report1)
        assert match is not None, f"バックアップIDが抽出できません: {report1}"
        backup_id = match.group(0)

        (report2,) = node.manage_backup(action="restore", restore_id=backup_id)
        assert "[OK]" in report2

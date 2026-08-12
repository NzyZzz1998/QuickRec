"""QuickRec Lite 首次配置导入对话框。"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from utils.config_migration import LiteConfigMigration, MigrationResult
from version import APP_VERSION


class ConfigMigrationDialog(QDialog):
    """让用户明确选择导入、使用默认值或取消启动。"""

    def __init__(self, migration: LiteConfigMigration, parent=None) -> None:
        super().__init__(parent)
        self._migration = migration
        self._feedback_text = ""
        self.setWindowTitle(f"QuickRec Lite {APP_VERSION} 首次设置")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        title = QLabel("检测到拆分前的 QuickRec 设置")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "可只复制保存路径和音频模式。旧配置不会被移动、删除或覆盖；"
                "快捷键和开机启动将使用 Lite 新默认值。"
            )
        )

        self._feedback = QLabel("")
        self._feedback.setWordWrap(True)
        layout.addWidget(self._feedback)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._btn_cancel = QPushButton("取消启动")
        self._btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self._btn_cancel)
        self._btn_defaults = QPushButton("使用 Lite 默认设置")
        self._btn_defaults.clicked.connect(self._use_defaults)
        buttons.addWidget(self._btn_defaults)
        self._btn_import = QPushButton("导入设置")
        self._btn_import.clicked.connect(self._import_settings)
        self._btn_import.setDefault(True)
        buttons.addWidget(self._btn_import)
        layout.addLayout(buttons)

    @property
    def feedback_text(self) -> str:
        return self._feedback_text

    def _import_settings(self) -> None:
        self._apply(self._migration.import_settings())

    def _use_defaults(self) -> None:
        self._apply(self._migration.use_defaults())

    def _apply(self, result: MigrationResult) -> None:
        if result.ok:
            details = "\n".join(result.warnings)
            self._set_feedback(details or "Lite 配置已安全创建。", error=False)
            self.accept()
            return
        message = result.message or "无法创建 Lite 配置，请重试或取消启动。"
        self._set_feedback(f"保存失败（{result.stage}）：{message}", error=True)

    def _set_feedback(self, text: str, *, error: bool) -> None:
        self._feedback_text = text
        self._feedback.setText(text)
        color = "#b42318" if error else "#067647"
        self._feedback.setStyleSheet(f"color: {color};")

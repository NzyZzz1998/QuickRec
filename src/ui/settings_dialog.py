"""
设置对话框模块

提供用户修改配置的界面。
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog
)

from config import ConfigManager


class SettingsDialog(QDialog):
    """设置对话框"""

    config_saved = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle("QuickRec 设置")
        self.setMinimumWidth(420)
        self.setFixedHeight(320)

        layout = QVBoxLayout(self)

        # 表单布局
        form = QFormLayout()

        # 保存路径
        path_layout = QHBoxLayout()
        self._edit_save_path = QLineEdit()
        self._edit_save_path.setReadOnly(True)
        path_layout.addWidget(self._edit_save_path)
        self._btn_browse = QPushButton("浏览...")
        self._btn_browse.setFixedWidth(70)
        self._btn_browse.clicked.connect(self._browse_save_path)
        path_layout.addWidget(self._btn_browse)
        form.addRow("保存路径:", path_layout)

        # 画质选择
        self._combo_quality = QComboBox()
        self._combo_quality.addItems(["high", "medium", "low"])
        self._combo_quality.setCurrentText("high")
        form.addRow("画质:", self._combo_quality)

        # 帧率选择
        self._combo_fps = QComboBox()
        self._combo_fps.addItems(["30", "60"])
        self._combo_fps.setCurrentText("30")
        form.addRow("帧率:", self._combo_fps)

        # 快捷键显示
        self._label_shortcut_start = QLabel("Ctrl+Shift+R")
        form.addRow("开始快捷键:", self._label_shortcut_start)

        self._label_shortcut_stop = QLabel("Ctrl+Shift+S")
        form.addRow("停止快捷键:", self._label_shortcut_stop)

        self._label_shortcut_pause = QLabel("Ctrl+Shift+P")
        form.addRow("暂停快捷键:", self._label_shortcut_pause)

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_save = QPushButton("保存")
        self._btn_save.setFixedSize(80, 32)
        self._btn_save.clicked.connect(self._save_config)
        btn_layout.addWidget(self._btn_save)

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setFixedSize(80, 32)
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        layout.addLayout(btn_layout)

    def _load_config(self):
        """从 ConfigManager 加载当前值到控件"""
        self._edit_save_path.setText(self._config.get("save_path"))
        self._combo_quality.setCurrentText(
            str(self._config.get("quality", "high"))
        )
        self._combo_fps.setCurrentText(
            str(self._config.get("fps", 30))
        )
        self._label_shortcut_start.setText(
            str(self._config.get("shortcut_start", "Ctrl+Shift+R"))
        )
        self._label_shortcut_stop.setText(
            str(self._config.get("shortcut_stop", "Ctrl+Shift+S"))
        )
        self._label_shortcut_pause.setText(
            str(self._config.get("shortcut_pause", "Ctrl+Shift+P"))
        )

    def _save_config(self):
        """从控件读取值，写入 ConfigManager"""
        self._config.set("save_path", self._edit_save_path.text())
        self._config.set("quality", self._combo_quality.currentText())
        self._config.set("fps", int(self._combo_fps.currentText()))
        self._config.save()
        self.config_saved.emit()
        self.accept()

    def _browse_save_path(self):
        """打开文件夹选择对话框"""
        path = QFileDialog.getExistingDirectory(
            self, "选择保存路径",
            self._edit_save_path.text()
        )
        if path:
            self._edit_save_path.setText(path)
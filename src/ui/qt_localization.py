"""Qt 内置标准按钮的简体中文本地化。"""

from PyQt5.QtCore import QTranslator
from PyQt5.QtWidgets import QApplication


class QuickRecQtTranslator(QTranslator):
    """补齐 Windows 打包环境中缺失的 Qt 标准按钮翻译。"""

    _BUTTON_LABELS = {
        "OK": "确定",
        "Open": "打开",
        "Save": "保存",
        "Cancel": "取消",
        "Close": "关闭",
        "Discard": "放弃",
        "Apply": "应用",
        "Reset": "重置",
        "Restore Defaults": "恢复默认",
        "Help": "帮助",
        "Save All": "全部保存",
        "Yes": "是",
        "Yes to All": "全部是",
        "No": "否",
        "No to All": "全部否",
        "Abort": "中止",
        "Retry": "重试",
        "Ignore": "忽略",
    }

    def translate(
        self,
        context: str | None,
        source_text: str | None,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        del context, disambiguation, n
        source = str(source_text or "")
        lookup = source.replace("&", "")
        return self._BUTTON_LABELS.get(lookup, "")


def install_qt_zh_cn(app: QApplication) -> QuickRecQtTranslator:
    """安装应用级标准按钮翻译，并由调用方持有引用。"""
    translator = QuickRecQtTranslator()
    install_translator = getattr(app, "installTranslator", None)
    if callable(install_translator):
        install_translator(translator)
    return translator

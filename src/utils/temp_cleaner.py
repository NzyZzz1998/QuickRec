"""
临时文件清理模块（v1.3 新增）

三层清理机制：
  第一层：录制正常结束/取消 → cleanup_session()
  第二层：程序正常退出 → atexit 钩子
  第三层：程序启动时扫描 → cleanup_stale()
"""

import atexit
import ctypes
import ctypes.wintypes
import logging
import os
import shutil
import tempfile
import time

logger = logging.getLogger("QuickRec")


class TempCleaner:
    BASE_DIR = os.path.join(tempfile.gettempdir(), "QuickRec")

    @classmethod
    def create_session_dir(cls) -> str:
        """创建录制会话临时目录，返回绝对路径"""
        name = f"session_{os.getpid()}_{int(time.time())}"
        path = os.path.join(cls.BASE_DIR, name)
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def cleanup_session(cls, session_dir: str):
        """删除会话目录（第一/第二层）"""
        try:
            shutil.rmtree(session_dir)
        except OSError:
            pass

    @classmethod
    def _is_pid_alive(cls, pid: int) -> bool:
        if os.name == "nt":
            process_query_limited_information = 0x1000
            still_active = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    @classmethod
    def cleanup_stale(cls):
        """启动时扫描并清理无活跃进程的遗留会话目录（第三层）"""
        if not os.path.isdir(cls.BASE_DIR):
            return
        current_pid = os.getpid()
        for entry in os.listdir(cls.BASE_DIR):
            if not entry.startswith("session_"):
                continue
            try:
                pid = int(entry.split("_")[1])
            except (IndexError, ValueError):
                continue
            if pid == current_pid:
                continue
            if not cls._is_pid_alive(pid):
                try:
                    shutil.rmtree(os.path.join(cls.BASE_DIR, entry))
                    logger.info(f"已清理崩溃遗留目录: {entry}")
                except OSError:
                    pass

    @classmethod
    def register_atexit(cls, session_dir: str):
        """注册程序退出时清理钩子（第二层）"""
        atexit.register(cls.cleanup_session, session_dir)

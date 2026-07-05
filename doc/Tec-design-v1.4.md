# QuickRec v1.4 详细技术设计文档

> 版本: v1.4
> 创建时间: 2026-07-04
> 状态: 已完成 / 待发布
> 前置版本: v1.3（详见 Tec-design-v1.3.md）

---

## 1. 版本概述

### 1.1 v1.4 新增/变更目标清单

v1.4 是稳定性与工程化大型优化版本，不新增用户可见功能。目标是在 v1.3 已有能力基础上，补齐测试、CI、架构边界、异常路径和发布质量。当前实现已完成并通过发布前验证。

| 编号 | 目标 | 说明 | PRD 编号 |
|-----|------|------|---------|
| Q1 | 测试基线修复 | 默认测试恢复全绿：`175 passed / 23 deselected`；区分默认测试、UI 测试、硬件/系统集成测试 | Q1 |
| Q2 | 工程化配置 | 新增统一 `pyproject.toml`，固化 pytest、coverage、ruff、mypy 配置 | Q2 |
| Q3 | GitHub Actions CI | CI 执行 compile、lint、mypy、默认测试和 coverage，失败时阻断合并 | Q3 |
| Q4 | 架构解耦 | 拆分 `main.py` 与 `recorder_manager.py` 的职责，建立更清晰的应用、工作流、状态机、服务边界 | Q4 |
| Q5 | 公共事件接口 | 录制状态、保存完成、保存失败、窗口丢失、录制失败等必须通过公开接口传递 | Q5 |
| Q6 | 运行时稳定性 | 补齐 FFmpeg、临时文件、系统计时器、磁盘监控、退出流程、特殊窗口、连续录制等异常路径 | Q6 |
| Q7 | 发布质量 | PyInstaller 打包可复现，冒烟验证可执行；稳定性优先恢复 cv2，体积记录为 `257.74MB` | Q7 |

**关键设计决策**：

1. **先工程基线，后架构重构**：M1 修复测试基线，M2 固化自动化质量门槛，M3 再做架构解耦，M4 用运行时稳定性和发布验证收口。
2. **测试分层**：pytest marker 固定为 `unit`、`ui`、`hardware`、`packaging`。默认 CI 不依赖真实桌面硬件能力，硬件相关测试单独运行。
3. **类型检查工具**：v1.4 指定使用 `mypy`，先覆盖核心模块，允许按阶段收紧。
4. **CI 平台**：指定 GitHub Actions。
5. **架构拆分为建议方案**：文档列出建议文件名和模块边界，实现时可根据代码实际调整，但必须满足边界和验收要求。
6. **打包体积目标调整为稳定性优先**：曾尝试移除 cv2 达到 `186.36MB`，但 dxcam 默认捕获链路依赖 cv2；最终恢复 OpenCV，排除 `opencv_videoio_ffmpeg*.dll`，发布体积记录为 `257.74MB`。

### 1.2 v1.4 不包含

- 录制历史管理窗口。
- 多显示器录制选择。
- 编码参数 UI（CRF / preset）和高级用户设置。
- 视频剪辑、拼接、裁剪等后处理功能。
- 外置 FFmpeg。
- 替换 OpenCV、Qt、FFmpeg 等核心依赖来达成体积目标。
- 新增特殊窗口录制兼容能力；v1.4 只要求失败稳定、提示清晰、日志可诊断、不崩溃。

---

## 2. 模块设计

### 2.1 测试基线设计 — 更新

**职责**：恢复可可信的测试基线，为后续架构解耦提供回归保护。

**现状问题**：

| 问题 | 现象 | 处理方向 |
|-----|------|---------|
| VideoEncoder 旧接口测试 | 旧测试按 3 参数构造，v1.3 实现已要求 `ffmpeg_path` | 更新夹具，增加 FFmpeg 路径缺失、启动失败、编码失败测试 |
| RecorderManager stop 语义漂移 | 旧测试期待 `stop()` 同步返回 mp4，现实现为异步停止 | 明确异步契约，测试状态变化和 on_saved 回调 |
| ScreenCapturer 生命周期测试漂移 | 旧测试未显式 `start()` 即 `capture_frame()` | 拆分生命周期单测和真实 dxcam 捕获测试 |
| 硬件依赖未隔离 | dxcam / 音频 / Windows 桌面能力影响默认测试稳定性 | 使用 marker 隔离 `hardware` 测试 |

**pytest marker 设计**：

```toml
[tool.pytest.ini_options]
markers = [
  "unit: pure logic tests without Qt, hardware, or subprocess side effects",
  "ui: tests that require QApplication or PyQt widgets",
  "hardware: tests that require Windows desktop, dxcam, audio device, or real screen capture",
  "packaging: PyInstaller/package smoke tests",
]
```

**测试目录治理规则**：

1. 测试文件不再逐个手写 `sys.path.insert(0, ...)`；统一由 `pyproject.toml` 或测试运行入口处理。
2. 默认测试集只包含稳定、可重复、无需真实桌面设备的测试。
3. 真实 dxcam、音频设备、托盘、全局快捷键、PyInstaller 产物验证必须使用 marker 标识。
4. 对 FFmpeg、dxcam、pyaudio、soundcard、pystray 等外部依赖优先使用 mock/fake 测试核心状态流。
5. 测试名称必须表达行为，例如 `test_stop_transitions_to_saving_then_idle`，避免只表达实现细节。

默认测试命令建议：

```bash
python -m pytest -m "not hardware and not packaging"
```

硬件测试命令建议：

```bash
python -m pytest -m hardware
```

覆盖率目标：

```bash
python -m pytest -m "not hardware and not packaging" --cov=src --cov-report=term-missing --cov-fail-under=80
```

**测试夹具建议**：

```python
@pytest.fixture
def fake_config(tmp_path):
    config = ConfigManager.__new__(ConfigManager)
    config.config_path = tmp_path / "config.json"
    config._config = {
        **ConfigManager.defaults,
        "save_path": str(tmp_path),
        "quality": "low",
        "fps": 30,
        "audio_source": "none",
    }
    return config


@pytest.fixture
def fake_ffmpeg(tmp_path):
    exe = tmp_path / "ffmpeg.exe"
    exe.write_text("", encoding="utf-8")
    return str(exe)
```

**VideoEncoder 测试边界**：

| 用例 | 类型 | 说明 |
|-----|------|------|
| 构造命令参数 | unit | mock `subprocess.Popen`，验证 `rawvideo/bgr24/libx264/CRF/preset` |
| FFmpeg 路径缺失 | unit | 期望抛出可诊断异常或返回明确失败 |
| pipe 断开 | unit | mock stdin write 抛 BrokenPipeError，`write_frame()` 返回 False |
| 真实编码 | hardware | 写入少量帧，验证输出 MP4 可读 |

**RecorderManager 异步 stop 测试边界**：

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> RECORDING: start_*()
    RECORDING --> PAUSED: pause()
    PAUSED --> RECORDING: resume()
    RECORDING --> STOPPING: stop()
    PAUSED --> STOPPING: stop()
    STOPPING --> SAVING: record thread joined
    SAVING --> IDLE: finalize done / on_saved emitted
```

`stop()` 不再被测试为同步返回最终路径；测试应等待状态或回调事件，而不是假设文件立即存在。

### 2.2 工程化配置设计 — 新增

**职责**：集中管理测试、格式化、lint、类型检查、覆盖率配置，避免散落在命令行和测试文件中。

**建议文件**：`pyproject.toml`

**配置范围**：

| 工具 | 用途 | v1.4 要求 |
|-----|------|----------|
| pytest | 测试发现、marker、默认过滤 | 明确 marker，统一测试路径 |
| coverage / pytest-cov | 覆盖率统计 | 总覆盖率 `>= 80%` |
| ruff | lint + format | CI 必跑 |
| mypy | 类型检查 | 先覆盖核心模块，按阶段收紧 |

**导入路径要求**：

测试不应长期依赖每个文件内的 `sys.path.insert(0, ...)`。v1.4 应通过工程配置或包结构统一解决 `src` 导入路径，测试文件只表达测试意图。

**建议配置草案**：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra"
markers = [
  "unit: pure logic tests",
  "ui: PyQt widget tests",
  "hardware: Windows desktop/audio/dxcam tests",
  "packaging: PyInstaller/package smoke tests",
]

[tool.coverage.run]
source = ["src"]
branch = true
omit = [
  "src/rthook_dllpath.py",
]

[tool.coverage.report]
show_missing = true
fail_under = 80

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
warn_unused_ignores = true
no_implicit_optional = true
```

**ruff 收紧策略**：

- M2 阶段先保证新增配置可运行。
- 对历史代码可先采用局部忽略或较小规则集。
- 架构拆分后的新增模块必须按新规则编写。
- 不为了 lint 大规模改动无关 UI 样式代码。

### 2.3 GitHub Actions CI 设计 — 新增

**职责**：将 v1.4 质量门槛自动化，保证默认分支可重复验证。

**建议文件**：`.github/workflows/ci.yml`

**CI 阶段**：

```mermaid
flowchart TD
    A["checkout"] --> B["setup Python 3.12"]
    B --> C["install dependencies"]
    C --> D["compileall src"]
    D --> E["ruff format --check"]
    E --> F["ruff check"]
    F --> G["mypy src"]
    G --> H["pytest default suite"]
    H --> I["coverage >= 80%"]
```

**默认 CI 不包含**：

- 真实 dxcam 屏幕捕获。
- 真实音频设备捕获。
- PyInstaller 完整打包。

这些能力通过 `hardware` / `packaging` marker 和发布前 checklist 验证。

**CI 配置草案**：

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt
          python -m pip install pytest-cov ruff mypy
      - name: Compile
        run: python -m compileall -q src
      - name: Ruff format
        run: python -m ruff format --check .
      - name: Ruff lint
        run: python -m ruff check .
      - name: Mypy
        run: python -m mypy src
      - name: Tests
        run: python -m pytest -m "not hardware and not packaging" --cov=src --cov-report=term-missing --cov-fail-under=80
```

**CI 成功标准**：

- 所有步骤返回 0。
- 默认测试不依赖真实屏幕录制、系统声音设备或托盘交互。
- 失败日志能定位到 compile / lint / type / test / coverage 的具体阶段。

### 2.4 架构解耦设计 — 重构

**职责**：降低 `main.py` 和 `recorder_manager.py` 的职责集中度，明确 UI、录制工作流、录制引擎、平台适配层之间的边界。

**目标架构**：

```mermaid
flowchart TB
    subgraph UI["UI Layer"]
        Tray["tray_icon.py"]
        Toolbar["toolbar.py"]
        Settings["settings_dialog.py"]
        Selectors["area_selector.py / window_selector.py"]
    end

    subgraph App["Application Layer"]
        AppController["app_controller.py (建议)"]
        Workflow["workflows/recording_workflow.py (建议)"]
        Notify["services/notification_service.py (建议)"]
    end

    subgraph Recorder["Recorder Core"]
        Manager["recorder_manager.py"]
        StateMachine["recorder/state_machine.py (建议)"]
        Resources["recorder/resource_lifecycle.py (建议)"]
        WindowSvc["recorder/window_recording_service.py (建议)"]
    end

    subgraph Platform["Platform Adapters"]
        Capture["screen_capturer.py"]
        Encoder["video_encoder.py"]
        Audio["audio_capturer.py"]
        Disk["utils/disk_checker.py"]
        Temp["utils/temp_cleaner.py"]
    end

    UI --> App
    App --> Recorder
    Recorder --> Platform
```

**建议模块边界**：

| 建议模块 | 职责 | 说明 |
|---------|------|------|
| `app_controller.py` | Qt 应用生命周期、启动、退出收尾 | 可从 `main.py` 拆出 |
| `workflows/recording_workflow.py` | 全屏/区域/窗口录制流程编排，倒计时、暂停、停止、保存结果 | 可复用三种录制模式状态流 |
| `services/notification_service.py` | 托盘通知、错误提示、保存完成提示 | 统一用户提示文案 |
| `recorder/state_machine.py` | RecorderState 合法转移 | 可纯单元测试 |
| `recorder/resource_lifecycle.py` | dxcam、FFmpeg、音频、临时目录、系统计时器生命周期 | 连续录制和退出稳定性核心 |
| `recorder/window_recording_service.py` | 窗口句柄、窗口区域、窗口丢失和特殊窗口失败判断 | 降低 `RecorderManager` 体积 |

**强制边界要求**：

- UI 层不得访问 recorder 私有字段，例如 `_window_lost_bridge`。
- 状态变化、保存完成、保存失败、窗口丢失、录制失败必须通过公开事件、回调或信号接口传递。
- `RecorderManager` 应更偏向录制引擎门面，而不是同时承担所有状态机、资源管理和 UI 事件转发。

**建议类职责草案**：

```python
class AppController:
    """应用生命周期协调器。

    负责 QApplication、托盘、快捷键、设置窗口和退出流程的装配。
    不直接处理录制细节。
    """

    def start(self) -> int: ...
    def request_exit(self) -> None: ...


class RecordingWorkflow:
    """录制流程编排器。

    负责全屏/区域/窗口录制入口、倒计时、暂停、停止、取消和结果处理。
    """

    def start_fullscreen(self) -> None: ...
    def start_region(self, region: tuple[int, int, int, int]) -> None: ...
    def start_window(self, hwnd: int) -> None: ...
    def pause_resume(self) -> None: ...
    def stop(self, cancel: bool = False) -> None: ...


class RecorderStateMachine:
    """录制状态机。只处理状态转移，不操作 UI 和外部资源。"""

    def can_start(self) -> bool: ...
    def transition(self, event: str) -> RecorderState: ...
```

**拆分顺序建议**：

1. 先提取纯逻辑状态机，测试成本最低。
2. 再提取通知服务，不改变录制核心行为。
3. 再提取录制工作流，替换 `main.py` 中重复流程。
4. 最后收窄 `RecorderManager`，拆资源生命周期和窗口录制服务。

### 2.5 公共事件接口设计 — 新增

**职责**：为 UI 和录制核心之间建立稳定契约。

**建议事件**：

| 事件 | 参数 | 触发时机 |
|-----|------|---------|
| `state_changed` | old_state, new_state | 录制状态转移 |
| `recording_saved` | output_path, file_size_mb | 最终 MP4 保存成功 |
| `recording_failed` | reason, detail | 捕获、编码、混流、保存失败 |
| `window_lost` | reason | 目标窗口关闭或最小化 |
| `disk_warning` | free_mb, level | 录制前或录制中磁盘空间不足 |

事件实现可继续使用 PyQt `pyqtSignal`，也可在核心层使用回调/轻量事件对象，再由 Qt 桥接到主线程。具体实现留给开发阶段决定。

**事件对象草案**：

```python
from dataclasses import dataclass
from enum import Enum


class RecorderEventType(Enum):
    STATE_CHANGED = "state_changed"
    RECORDING_SAVED = "recording_saved"
    RECORDING_FAILED = "recording_failed"
    WINDOW_LOST = "window_lost"
    DISK_WARNING = "disk_warning"


@dataclass(frozen=True)
class RecorderEvent:
    type: RecorderEventType
    payload: dict
```

**Qt 桥接原则**：

- recorder 核心可以产生普通 Python 事件。
- Qt 层通过 bridge 将事件转发到主线程。
- UI 只订阅公开事件，不读取 recorder 私有字段。

```mermaid
sequenceDiagram
    participant Recorder
    participant EventBridge
    participant Workflow
    participant UI

    Recorder->>EventBridge: RecorderEvent(WINDOW_LOST)
    EventBridge->>Workflow: emit on Qt main thread
    Workflow->>UI: update toolbar/tray notification
```

### 2.6 运行时稳定性设计 — 更新

**职责**：让异常路径有清晰、可诊断、可恢复的行为。

| 场景 | v1.4 设计要求 | 验收 |
|-----|--------------|------|
| FFmpeg 路径为空或不可执行 | 启动录制前明确失败，提示用户并写日志 | 不在线程中静默崩溃 |
| FFmpeg 启动失败 | 捕获异常，触发 `recording_failed` | UI 收到失败提示 |
| FFmpeg 编码中断 | `write_frame` 返回失败后停止录制并进入失败/保存失败路径 | 不产生卡死线程 |
| `cleanup_stale()` | 应在应用启动流程中真实调用 | 崩溃残留 session 可被清理 |
| `timeBeginPeriod(1)` | 与 `timeEndPeriod(1)` 配对 | 退出后释放系统计时器设置 |
| 录制中磁盘空间不足 | 周期性检查保存磁盘空间，低于阈值提示或停止保存 | 不等到最终 move 才失败 |
| 退出流程 | 等待后台线程，超时后记录并提示 | 不无限卡退出 |
| 连续录制 | 至少连续 3 轮录制无资源锁死 | 自动或手工冒烟通过 |
| 特殊窗口失败 | 明确提示不可录制原因 | 不崩溃、不长时间阻塞主线程 |

**FFmpeg 启动前检查伪代码**：

```python
def validate_encoder(ffmpeg_path: str) -> tuple[bool, str]:
    if not ffmpeg_path:
        return False, "FFmpeg 路径为空"
    if not os.path.isfile(ffmpeg_path):
        return False, f"FFmpeg 不存在: {ffmpeg_path}"
    return True, ""
```

**录制中磁盘监控伪代码**：

```python
class DiskSpaceMonitor:
    def __init__(self, save_path: str, interval_sec: int = 30):
        self._save_path = save_path
        self._interval_sec = interval_sec

    def check(self) -> tuple[str, int]:
        status, free_mb = DiskChecker.check_before_recording(self._save_path)
        return status, free_mb
```

磁盘持续监控不要求每帧检查，建议以低频定时器或录制循环节流检查实现，避免明显 IO 开销。

**退出流程设计**：

```mermaid
flowchart TD
    A["用户退出"] --> B{"RecorderState == IDLE?"}
    B -- yes --> F["停止 hotkey/tray 并退出"]
    B -- no --> C["请求 stop(cancel=False)"]
    C --> D["等待后台线程 timeout"]
    D --> E{"完成?"}
    E -- yes --> F
    E -- no --> G["记录超时日志 + 用户提示"]
    G --> F
```

### 2.7 打包体积与发布验证设计 — 优化

**职责**：让打包可复现、产物可冒烟、体积有记录。

**目标**：PyInstaller 产物可复现、可启动、可验收，并记录体积构成。

**约束**：

- 不外置 FFmpeg。
- 不替换核心依赖。
- 不为了体积破坏全屏、区域、窗口录制、托盘、设置、音频等现有能力。

**可尝试方向**：

- PyInstaller excludes 精细化。
- 不必要资源和插件裁剪。
- UPX / strip 配置评估。
- 打包产物体积构成记录。

发布文档必须记录：

- 当前体积。
- 主要体积构成。
- 已尝试的优化项。
- 未达成原因。
- 后续可选方案。

**体积记录格式建议**：

| 项目 | 大小 | 说明 |
|-----|------|------|
| dist/QuickRec 总大小 | 257.74MB | 稳定性优先，保留 cv2 |
| FFmpeg | 94.67MB | 不允许外置 |
| OpenCV / cv2 | 71.38MB | dxcam 默认 processor 依赖 |
| NumPy / numpy.libs | 25.83MB | OpenCV / dxcam 依赖 |
| Qt / PyQt5 | 35.91MB | UI 必需 |
| 其他 | 约 30MB | PIL、pystray、soundcard、Python runtime 等 |

发布时体积目标按稳定性优先收口。后续 lite 分支可重新评估更小 FFmpeg 构建、opencv-python-headless 或替换捕获后端，但不进入 v1.4 发布范围。

---

### 2.8 v1.4 额外补充技术设计 — 发布后必须项

**职责**：承接 PRD `3.5.5 v1.4 额外补充需求（发布后必须项）`，将特殊窗口、音频链路、架构继续拆分、本地硬件验收、打包体积优化和 lite/full 未来规划转化为可执行的技术边界。

**定位**：
- 本节为 v1.4 系列发布后的补充设计，不改变 v1.4 已发布主线能力。
- 特殊窗口、音频链路、架构继续拆分、硬件验收和打包体积优化属于 v1.4 后续补充项。
- lite/full 仅做未来规划，不在 v1.4 实施分支拆分，不提供用户可见切换入口。

#### 2.8.1 特殊窗口兼容性补充设计

**设计目标**：
- 对游戏、UWP、DWM 自定义渲染等特殊窗口失败路径提供更明确的日志与诊断。
- 保持现有 dxcam 捕获链路稳定，不为了特殊窗口兼容性牺牲普通全屏、区域、常规窗口录制。
- 替代捕获后端只做研究记录，不在 v1.4 强制落地。

**诊断信息要求**：
| 字段 | 说明 |
|-----|------|
| hwnd | 选中窗口句柄 |
| title | 窗口标题，必要时脱敏或截断 |
| mode | 当前录制模式：fullscreen / region / window |
| rect | 捕获区域，获取失败时记录失败阶段 |
| foreground_result | 置前台、恢复窗口、获取窗口位置等关键调用结果 |
| failure_reason | 统一失败原因，例如 unsupported_window、rect_unavailable、foreground_denied |

**建议失败原因枚举**：
| reason | 触发场景 | 用户侧表现 |
|--------|---------|------------|
| `unsupported_window` | 游戏全屏、UWP、DWM 自定义渲染窗口无法稳定获取内容 | 提示该窗口可能不支持录制 |
| `rect_unavailable` | 无法获取窗口位置或窗口尺寸异常 | 取消录制启动，保持软件可用 |
| `foreground_denied` | Windows 前台锁或权限导致置前台失败 | 继续诊断，不阻塞主线程 |
| `capture_backend_failed` | dxcam 捕获链路启动失败 | 进入失败收口，不生成不可用录制 |

**替代捕获后端研究要求**：
- 记录候选方案适用场景、依赖变化、打包体积影响和迁移风险。
- 不在 PRD 外承诺具体后端名称和完成时间。
- 任何候选方案必须先通过普通录制回归，再考虑特殊窗口收益。

#### 2.8.2 音频链路兼容性补充设计

**设计目标**：
- 录制前进行轻量音频自检，提前发现不可用链路。
- 双音频不可用时允许自动降级，优先保证最终 MP4 可播放。
- 对空音频、短音频、异常 WAV 继续保持防御式处理。

**自检流程**：
```mermaid
flowchart TD
    A["开始录制请求"] --> B["读取 audio_source 设置"]
    B --> C["检查系统音频设备"]
    B --> D["检查麦克风设备"]
    C --> E{"系统音频可用?"}
    D --> F{"麦克风可用?"}
    E --> G["生成可用音频源集合"]
    F --> G
    G --> H{"目标音频源可满足?"}
    H -- yes --> I["按用户设置启动录制"]
    H -- no --> J{"存在可降级音频源?"}
    J -- yes --> K["降级并记录日志"]
    J -- no --> L["仅录制视频或阻断启动，按策略提示"]
    K --> I
    L --> M["进入可诊断失败或无音频录制"]
```

**自检检查项**：
| 检查项 | 处理策略 |
|--------|---------|
| 无系统音频设备 | 从 both 降级到 mic；若目标仅系统音频则提示不可用 |
| 无麦克风设备 | 从 both 降级到 system；若目标仅麦克风则提示不可用 |
| 设备占用或初始化失败 | 记录设备名、采样率、声道数和异常信息 |
| 音频文件为空或过短 | 混流前过滤该输入，避免生成不可播放 MP4 |
| 采样率或声道异常 | 尽量交给 FFmpeg 统一转码；失败时进入可诊断失败 |

**日志要求**：
- 自检开始、目标音频源、可用音频源、降级结果必须记录。
- 降级不应静默发生，日志需包含原始设置和最终设置。
- FFmpeg 混流失败必须保留命令摘要和输入文件状态。

#### 2.8.3 架构继续拆分设计

v1.4 已完成录制工作流、状态机、事件模型等初步解耦。额外补充不强制规定文件名，但要求继续按职责边界推进。

| 边界 | 技术设计要求 |
|------|--------------|
| 应用装配 | 入口只负责启动应用、装配依赖、注册托盘/热键，不承载录制业务判断 |
| 录制生命周期 | 开始、暂停、恢复、停止、取消、保存完成应由统一工作流编排 |
| 通知提示 | 系统通知、托盘提示、错误提示和日志上下文从录制核心中剥离 |
| 窗口录制 | 窗口句柄校验、区域换算、移动检测、特殊窗口失败原因独立维护 |
| 资源释放 | dxcam、FFmpeg、音频线程、临时目录、系统计时器释放顺序可测试 |

**约束**：
- 不因补充需求重新扩大 `main.py` 和 `RecorderManager` 职责。
- UI 层不得直接读取录制核心私有字段。
- 新增复杂判断必须优先沉淀为公共事件、状态或服务边界。

#### 2.8.4 本地硬件验收设计

**定位**：本地硬件验收为发布前必跑项，不进入 GitHub Actions 默认流程。

**建议命令**：
```bash
python scripts/hardware_smoke.py
```

**验收内容**：
| 验收项 | 标准 |
|--------|------|
| 真实录制 | 至少完成 3 秒真实桌面录制 |
| 视频流 | 输出 MP4 包含视频流，帧数非 0 |
| 文件状态 | 文件大小非 0，时长符合预期 |
| 进程退出 | 录制结束后无明显残留 QuickRec/FFmpeg 后台进程 |
| 临时目录 | session 目录按策略清理或保留可诊断残留 |
| 日志 | 包含捕获、编码、音频、保存、退出关键阶段 |

**边界**：
- 该脚本是验收要求，不代表 v1.4 必须新增用户入口。
- CI 只覆盖可模拟路径，硬件链路仍由本地发布前验证承担。

#### 2.8.5 打包体积优化补充设计

**原则**：
- 不设置固定体积上限。
- 不外置 FFmpeg。
- 不移除会破坏 dxcam 默认链路的 cv2。
- 所有体积优化必须通过录制与音频混流回归。

**具体尝试项**：
| 尝试项 | 目标 | 风险 | 验收 |
|--------|------|------|------|
| 体积构成脚本 | 统计 dist 内大文件、目录占比和依赖来源 | 统计口径不一致 | 输出可重复的体积报告 |
| FFmpeg 精简构建评估 | 评估更小 FFmpeg 是否满足 H.264/AAC/混流需求 | 编码器或滤镜缺失导致保存失败 | 全屏、区域、窗口、双音频混流均通过 |
| OpenCV headless 评估 | 验证 `opencv-python-headless` 是否满足 dxcam 处理器依赖 | 与 dxcam 打包兼容性不确定 | dxcam 捕获帧正常，打包产物可运行 |
| dxcam 处理器替代研究 | 评估不依赖 cv2 的帧格式转换路径 | 性能下降或色彩格式异常 | 录制帧稳定、颜色正确、CPU 不明显劣化 |
| PyInstaller excludes 收敛 | 继续排除未使用 Qt/PIL/测试资源/无关 DLL | 误删运行时必需资源 | 打包冒烟和手动验收通过 |
| lite 依赖边界评估 | 为未来 lite 分支减少功能依赖做准备 | 与 full 规划边界混淆 | 仅输出规划，不改 v1.4 主线功能 |

#### 2.8.6 lite/full 未来规划设计

**v1.4 边界**：
- 不拆分 lite/full 分支。
- 不新增 lite/full 模式切换。
- 不删除当前主线能力。
- 仅记录后续产品线方向、依赖边界和风险。

| 方向 | 定位 | 后续技术边界 |
|------|------|--------------|
| QuickRec Lite | 轻量级录屏工具 | 默认仅全屏录制；区域录制作为未来可选能力；不规划窗口录制；保留托盘 UI；保留当前音频能力但隐藏高级配置 |
| QuickRec Full | 创作者工作台 | 录制历史、素材管理、轻编辑、导出队列、质量诊断中心、模板与预设、更多兼容性策略 |

**关系原则**：
- lite 和 full 是未来不同演进方向，不要求在完全一致项目中长期共存。
- lite 的技术优先级是依赖收敛、入口轻量、录制可靠。
- full 的技术优先级是工作流完整性、质量可视化、项目化管理和扩展能力。

## 3. 新增依赖

### 3.1 运行时依赖

无新增运行时依赖。

### 3.2 开发依赖

| 依赖 | 用途 | 说明 |
-----|------|------|
| pytest-cov | 覆盖率统计 | 用于 `>= 80%` 门槛 |
| ruff | lint + format | CI 必跑 |
| mypy | 类型检查 | 先覆盖核心模块 |

---

## 4. 项目架构更新

### 4.1 目录结构变化（建议）

```text
QuickRec/
├── .github/
│   └── workflows/
│       └── ci.yml                 # v1.4 新增：GitHub Actions
├── pyproject.toml                 # v1.4 新增：工程配置
├── src/
│   ├── main.py                    # 保留入口，职责收窄
│   ├── app_controller.py          # 建议新增：应用生命周期
│   ├── workflows/
│   │   └── recording_workflow.py  # 建议新增：录制流程编排
│   ├── services/
│   │   └── notification_service.py# 建议新增：通知服务
│   └── recorder/
│       ├── recorder_manager.py    # 保留门面，职责收窄
│       ├── state_machine.py       # 建议新增：状态机
│       ├── resource_lifecycle.py  # 建议新增：资源生命周期
│       └── window_recording_service.py # 建议新增：窗口录制服务
└── tests/
    ├── ...                        # 现有测试更新 marker 和夹具
```

> 上述文件名为建议方案，实际实现可调整；但职责边界和验收目标不可省略。

### 4.2 模块依赖关系更新

```mermaid
flowchart LR
    Main["main.py"] --> AppController
    AppController --> Workflow
    Workflow --> RecorderManager
    Workflow --> NotificationService
    RecorderManager --> StateMachine
    RecorderManager --> ResourceLifecycle
    RecorderManager --> WindowRecordingService
    ResourceLifecycle --> ScreenCapturer
    ResourceLifecycle --> VideoEncoder
    ResourceLifecycle --> AudioCapturer
    ResourceLifecycle --> TempCleaner
    ResourceLifecycle --> DiskChecker
```

---

## 5. 模块测试计划

| 测试层 | marker | 覆盖内容 | CI 默认 |
|-------|--------|----------|--------|
| 纯逻辑测试 | `unit` | 配置、文件命名、状态机、磁盘判断、事件接口 | 是 |
| UI 测试 | `ui` | Toolbar、SettingsDialog、Selector 信号和基础状态 | 是，需 headless Qt 配置 |
| 硬件/系统测试 | `hardware` | dxcam、真实屏幕捕获、音频设备、全局快捷键 | 否 |
| 打包测试 | `packaging` | PyInstaller 构建和产物冒烟 | 否，发布前运行 |

v1.4 完成时默认测试必须全绿，coverage 总覆盖率必须 `>= 80%`。

---

## 6. 开发里程碑

| 阶段 | 目标 | 完成标准 |
|-----|------|---------|
| M1 | 工程基线修复 | 默认 pytest 全绿；marker 生效；coverage 接入 |
| M2 | CI / Lint / 类型检查 | GitHub Actions 跑通 compile、ruff、mypy、pytest、coverage |
| M3 | 架构解耦 | 核心职责拆分完成；UI 不再访问 recorder 私有字段；事件接口明确 |
| M4 | 运行时稳定性与发布收口 | 异常路径可诊断；连续录制通过；打包冒烟完成；体积有记录 |
| M5 | v1.4 额外补充设计 | 特殊窗口、音频链路、硬件验收、体积优化和 lite/full 规划形成可执行边界 |

---

## 7. 风险与应对

| 风险 | 影响 | 应对 |
|-----|------|------|
| 测试修复范围扩大 | M1 时间变长 | 先修默认测试，再隔离 hardware/packaging |
| mypy 初期噪音较多 | 类型检查难以一次性全绿 | 先覆盖核心模块，配置允许逐步收紧 |
| 架构解耦引入回归 | 影响已有录制流程 | M1/M2 先建立回归网，M3 小步拆分 |
| GitHub Actions 无真实桌面 | 无法覆盖 dxcam / 音频 / 托盘完整行为 | 硬件和打包测试通过 marker 与发布 checklist 执行 |
| 打包体积 `< 200MB` 无法达成 | 影响原体积目标 | 已改为稳定性优先；记录体积构成，恢复 cv2，继续排除 OpenCV videoio ffmpeg |
| 特殊窗口不可录制 | 用户仍可能遇到失败 | v1.4 不承诺新增兼容，只保证提示稳定、不崩溃、日志可诊断 |
| 音频设备差异大 | 不同 Windows 设备、驱动和声卡行为不一致 | 增加录制前轻量自检；失败时降级或进入可诊断失败 |
| 硬件验收无法 CI 化 | GitHub Actions 无真实桌面和音频设备 | 将 `scripts/hardware_smoke.py` 作为发布前本地验收要求 |
| lite/full 规划污染 v1.4 主线 | 可能引入过早分支复杂度 | v1.4 只记录规划边界，不实现分支拆分和用户入口 |

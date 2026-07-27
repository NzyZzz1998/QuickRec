# v1.9 原型验证

## 验证对象

- 原型：`doc/releases/v1.9/prototype/index.html`
- 样式：`doc/releases/v1.9/prototype/styles.css`
- 交互：`doc/releases/v1.9/prototype/app.js`
- 验证脚本：`doc/releases/v1.9/prototype/validation/validate-prototype.js`

## 自动验证范围

- 五个一级导航存在。
- 录制页全屏、区域和窗口三个模块不存在默认选中态。
- 三个录制模式按钮使用相同视觉层级。
- 顶部“选择录制模式”只定位模式区，不直接开始全屏录制。
- 项目页可打开。
- 新建项目表单可打开和取消。
- 添加素材选择器包含可用、已加入、共享和缺失状态。
- 项目内全屏、区域和窗口三个录制入口存在。
- 归档后进入只读状态并提供恢复入口。
- 项目文件缺失时提供重新定位入口。
- 安全删除中的独占视频默认不选择。
- 共享和归属不确定视频不可选择。
- `960×640` 最小窗口无横向溢出。
- 最小窗口可通过详情区滚动访问底部删除入口。
- 浏览器无 JavaScript 控制台错误或页面异常。

## 截图证据

- `projects-default-1440x1000.png`
- `projects-delete-1440x1000.png`
- `projects-min-960x640.png`
- `recording-modes-equal-1440x1000.png`

## 运行方式

先启动本地服务：

```powershell
python -m http.server 8769 --directory E:\codex\QuickRec\doc\releases\v1.9\prototype
```

再使用包含 Playwright 的 Node.js 环境运行：

```powershell
node doc\releases\v1.9\prototype\validation\validate-prototype.js
```

## 当前结论

自动验证和产品负责人确认均已通过；PyQt 实现及 D8 GUI 验收已经完成。该目录继续作为 v1.9 原型回归证据保留。

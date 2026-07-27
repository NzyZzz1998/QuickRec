# v1.9.1 原型验证

## 验证范围

- 五页工作台导航未回退。
- 项目素材列表和详情预览存在。
- PNG 静态素材可解码且不是空白图片。
- 选择素材后详情同步更新。
- 预览生成中禁止重复刷新。
- 预览失败保留再次刷新入口。
- 文件缺失禁用打开文件和目录，保留素材库恢复入口。
- 项目到素材库再返回项目的上下文链路。
- 重建当前项目预览的确认和进度。
- `1440×1000` 和 `960×640`。
- 100%、125%、150% 设备缩放表达。
- 浏览器控制台和脚本无错误。
- 页面不存在文档级横向溢出。

## 运行方式

先启动本地服务：

```powershell
python -m http.server 8770 --directory E:\codex\QuickRec\doc\releases\v1.9.1\prototype
```

再在仓库根目录运行：

```powershell
node doc\releases\v1.9.1\prototype\validation\validate-prototype.js
```

如本机 Playwright 位于额外 Node 模块目录，先把该目录加入 `NODE_PATH`。

## 截图

验证成功后生成：

```text
projects-preview-default-1440x1000.png
projects-preview-loading-1440x1000.png
projects-preview-failed-1440x1000.png
projects-preview-missing-1440x1000.png
library-return-context-1440x1000.png
projects-preview-rebuild-1440x1000.png
projects-preview-min-960x640.png
projects-preview-dpi-100.png
projects-preview-dpi-125.png
projects-preview-dpi-150.png
```

这些图片是原型验证证据，不是 QuickRec 打包程序 GUI 验收证据。

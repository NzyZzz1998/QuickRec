# v1.9.5 原型验证

先在原型目录启动本地服务：

```powershell
python -m http.server 8774 --bind 127.0.0.1 --directory E:\codex\QuickRec\doc\releases\v1.9.5\prototype
```

再运行：

```powershell
$env:NODE_PATH = "C:\Users\win\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
node E:\codex\QuickRec\doc\releases\v1.9.5\prototype\validation\validate-prototype.js
```

验证范围：

- HTML 引用资源存在。
- JavaScript 语法正确。
- UTF-8 文本无替换字符和常见乱码。
- 所有产品按钮都有可访问名称。
- 所有 `[data-contract]` 控件均已注册完整交互合同。
- 每个产品控件都有首次加入和后续优化元数据。
- 页面关系图的每个节点都有版本说明。
- v1.9.5 专项状态完整。
- 解绑、智能拖放、帧级导航和开发合同检查器可交互。
- 1440×900、1216×760、960×640 无横向溢出。

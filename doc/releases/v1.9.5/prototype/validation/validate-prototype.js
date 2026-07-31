"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { chromium } = require("playwright");

const prototypeRoot = path.resolve(__dirname, "..");
const baseUrl = process.env.PROTOTYPE_URL || "http://127.0.0.1:8774/index.html?page=projects";
const nodeExecutable = process.execPath;
const requiredContractFields = [
  "title",
  "trigger",
  "action",
  "success",
  "failure",
  "disabled",
  "cancel",
  "dataImpact",
];
const requiredStates = [
  "timeline-unlink-candidate",
  "timeline-unlinked",
  "timeline-relink-candidates",
  "timeline-relink-empty",
  "timeline-delete-gap",
  "timeline-drag-existing",
  "timeline-drag-auto-video",
  "timeline-drag-auto-pair",
  "timeline-drag-invalid",
  "timeline-track-limit",
  "timeline-fps-30",
  "timeline-fps-60",
  "timeline-fps-120",
  "timeline-shortcut-focus",
];

const failures = [];
const notes = [];

function check(condition, message) {
  if (!condition) failures.push(message);
}

function readUtf8(relativePath) {
  return fs.readFileSync(path.join(prototypeRoot, relativePath), "utf8");
}

function validateStaticFiles() {
  const expected = [
    "index.html",
    "app.js",
    "timeline.js",
    "export.js",
    "v195.js",
    "styles.css",
    "timeline.css",
    "export.css",
    "v195.css",
    "prototype-design.md",
  ];
  expected.forEach((file) => check(fs.existsSync(path.join(prototypeRoot, file)), `缺少原型文件：${file}`));

  const sourceFiles = expected.filter((file) => fs.existsSync(path.join(prototypeRoot, file)));
  sourceFiles.forEach((file) => {
    const text = readUtf8(file);
    const mojibakeToken = ["锟斤", "拷"].join("");
    check(!text.includes("\uFFFD"), `${file} 含 Unicode 替换字符`);
    check(!text.includes(mojibakeToken), `${file} 含常见乱码标记`);
  });

  ["app.js", "timeline.js", "export.js", "v195.js"].forEach((file) => {
    const result = spawnSync(nodeExecutable, ["--check", path.join(prototypeRoot, file)], {
      encoding: "utf8",
    });
    check(result.status === 0, `${file} JavaScript 语法检查失败：${result.stderr.trim()}`);
  });

  const html = readUtf8("index.html");
  const resourcePattern = /(?:src|href)="([^"#?]+)"/g;
  const localResources = [];
  for (const match of html.matchAll(resourcePattern)) {
    const target = match[1];
    if (!target.startsWith("http") && !target.startsWith("data:")) localResources.push(target);
  }
  localResources.forEach((resource) => {
    check(fs.existsSync(path.join(prototypeRoot, resource)), `HTML 引用资源不存在：${resource}`);
  });

  const flowNodes = [...html.matchAll(/class="flow-node(?: [^"]*)?"[\s\S]*?<\/div>/g)].map((match) => match[0]);
  check(flowNodes.length >= 20, `页面关系图节点不足：${flowNodes.length}`);
  flowNodes.forEach((node, index) => {
    check(node.includes("flow-version"), `页面关系图第 ${index + 1} 个节点缺少版本说明`);
  });
}

async function validateBrowser() {
  const browser = await chromium.launch({ headless: true });
  const viewportResults = [];

  for (const viewport of [
    { width: 1440, height: 900, name: "1440x900" },
    { width: 1216, height: 760, name: "1216x760" },
    { width: 960, height: 640, name: "960x640" },
  ]) {
    const page = await browser.newPage({ viewport });
    const runtimeErrors = [];
    page.on("pageerror", (error) => runtimeErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") runtimeErrors.push(message.text());
    });

    const response = await page.goto(baseUrl, { waitUntil: "networkidle" });
    check(response && response.ok(), `${viewport.name} 原型地址访问失败`);
    await page.waitForTimeout(200);

    const metrics = await page.evaluate((fields) => {
      const uniqueKeys = [...new Set([...document.querySelectorAll("[data-contract]")].map((element) => element.dataset.contract))];
      const missingContracts = uniqueKeys.filter((key) => {
        const spec = contracts[key];
        return !spec || !fields.every((field) => typeof spec[field] === "string" && spec[field].trim());
      });
      const buttonsWithoutName = [...document.querySelectorAll("button")].filter((button) => {
        const name = button.getAttribute("aria-label")
          || button.getAttribute("title")
          || button.textContent;
        return !name || !name.trim();
      }).length;
      const states = [...document.querySelectorAll("#prototypeState option")].map((option) => option.value);
      const contractElements = [...document.querySelectorAll("[data-contract]")];
      const flowNodesWithoutVersion = [...document.querySelectorAll(".flow-node")]
        .filter((node) => !node.querySelector(".flow-version")).length;
      return {
        title: document.title,
        language: document.documentElement.lang,
        replacementChars: document.body.innerText.split("\uFFFD").length - 1,
        contractCount: contractElements.length,
        registeredCount: contractElements.filter((element) => element.dataset.contractRegistered === "true").length,
        versionedCount: contractElements.filter((element) => element.dataset.versionIntroduced && element.dataset.versionOptimized).length,
        missingContracts,
        buttonsWithoutName,
        states,
        bodyWidth: document.body.scrollWidth,
        viewportWidth: window.innerWidth,
        flowNodesWithoutVersion,
      };
    }, requiredContractFields);

    check(runtimeErrors.length === 0, `${viewport.name} 运行时错误：${runtimeErrors.join("；")}`);
    check(metrics.title.includes("v1.9.5"), `${viewport.name} 页面标题不是 v1.9.5`);
    check(metrics.language === "zh-CN", `${viewport.name} 页面语言不是 zh-CN`);
    check(metrics.replacementChars === 0, `${viewport.name} 页面出现 Unicode 替换字符`);
    check(metrics.contractCount > 200, `${viewport.name} 产品控件合同数量异常：${metrics.contractCount}`);
    check(metrics.registeredCount === metrics.contractCount, `${viewport.name} 有控件未注册合同`);
    check(metrics.versionedCount === metrics.contractCount, `${viewport.name} 有控件缺少版本演进元数据`);
    check(metrics.missingContracts.length === 0, `${viewport.name} 合同字段不完整：${metrics.missingContracts.join(", ")}`);
    check(metrics.buttonsWithoutName === 0, `${viewport.name} 有 ${metrics.buttonsWithoutName} 个按钮没有可访问名称`);
    check(metrics.bodyWidth <= metrics.viewportWidth, `${viewport.name} 页面发生横向溢出`);
    check(metrics.flowNodesWithoutVersion === 0, `${viewport.name} 页面关系节点缺少版本说明`);
    requiredStates.forEach((state) => check(metrics.states.includes(state), `${viewport.name} 缺少演示状态：${state}`));

    await page.screenshot({
      path: path.join(__dirname, `v195-timeline-${viewport.name}.png`),
      fullPage: false,
    });
    viewportResults.push({ viewport: viewport.name, ...metrics });
    await page.close();
  }

  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  await page.click("#toggleVersionHistory");
  check(await page.locator("#versionEvolutionStrip").isVisible(), "版本脉络未显示");

  await page.click("#toggleClipLink");
  check(await page.locator("#modalLayer").isVisible(), "解绑确认弹窗未显示");
  check((await page.locator("#modalTitle").innerText()).includes("解绑"), "解绑弹窗标题不正确");
  await page.locator("#modalActions button").filter({ hasText: "取消" }).click();

  await page.selectOption("#prototypeState", "timeline-drag-auto-pair");
  check(await page.locator("#timelineDragOverlay").isVisible(), "自动新建音视频轨落点预览未显示");

  await page.selectOption("#prototypeState", "timeline-fps-120");
  check(await page.inputValue("#timelineEditingFps") === "120", "120 FPS 帧级状态未生效");
  const beforeFrame = await page.locator("#timelineCurrentTime").innerText();
  await page.keyboard.press("ArrowRight");
  const afterFrame = await page.locator("#timelineCurrentTime").innerText();
  check(beforeFrame !== afterFrame, "下一帧快捷键未移动播放头");

  await page.click("#toggleAnnotations");
  await page.click("#toggleClipLink");
  const inspector = await page.evaluate(() => [
    "contractTitle",
    "contractIntroduced",
    "contractOptimized",
    "contractTrigger",
    "contractAction",
    "contractSuccess",
    "contractFailure",
    "contractDisabled",
    "contractCancel",
    "contractDataImpact",
    "contractUndo",
    "contractShortcut",
  ].reduce((result, id) => {
    result[id] = document.getElementById(id)?.textContent.trim() || "";
    return result;
  }, {}));
  Object.entries(inspector).forEach(([field, value]) => check(Boolean(value), `开发合同检查器字段为空：${field}`));

  await page.screenshot({
    path: path.join(__dirname, "v195-contracts-1920x1080.png"),
    fullPage: false,
  });

  if (await page.locator("#modalLayer").isVisible()) {
    await page.evaluate(() => closeModal());
  }
  await page.click("#showFlow");
  check(await page.locator("#flowLayer").isVisible(), "页面关系与版本演进图未显示");
  check(await page.locator(".flow-node .flow-version").count() === await page.locator(".flow-node").count(), "页面关系节点的版本说明不完整");
  await page.screenshot({
    path: path.join(__dirname, "v195-flow-1920x1080.png"),
    fullPage: false,
  });
  await browser.close();
  return viewportResults;
}

(async () => {
  validateStaticFiles();
  const viewportResults = await validateBrowser();
  if (failures.length) {
    console.error(JSON.stringify({ ok: false, failures, notes, viewportResults }, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify({ ok: true, failures: [], notes, viewportResults }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

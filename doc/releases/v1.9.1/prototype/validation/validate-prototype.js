"use strict";

const { chromium } = require("playwright");

const BASE_URL = process.env.QUICKREC_PROTOTYPE_URL
  || "http://127.0.0.1:8770/index.html";
const OUTPUT = "doc/releases/v1.9.1/prototype/validation";

async function requireVisible(locator, message) {
  if (!await locator.isVisible()) {
    throw new Error(message);
  }
}

async function requireNoDocumentOverflow(page, label) {
  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
    clientHeight: document.documentElement.clientHeight,
  }));
  if (metrics.scrollWidth > metrics.clientWidth + 1) {
    throw new Error(`${label} 出现页面级横向溢出：${JSON.stringify(metrics)}`);
  }
  return metrics;
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
  });
  const browserErrors = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.push(`console:${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    browserErrors.push(`page:${error.message}`);
  });

  await page.goto(`${BASE_URL}?page=projects`, { waitUntil: "networkidle" });

  const navCount = await page.locator(".nav-button").count();
  if (navCount !== 5) {
    throw new Error(`导航数量应为 5，实际为 ${navCount}`);
  }

  const previewItems = page.locator(".project-preview-item");
  const previewCount = await previewItems.count();
  if (previewCount < 4) {
    throw new Error(`项目预览状态样本不足，实际为 ${previewCount}`);
  }

  const imagesValid = await page.locator(".project-preview-thumb img").evaluateAll(
    (images) => images.every((image) => image.complete && image.naturalWidth > 0),
  );
  if (!imagesValid) {
    throw new Error("项目预览列表存在空白或无法解码的 PNG");
  }

  await requireVisible(
    page.locator("#projectPreviewDetail"),
    "项目素材详情未显示",
  );
  await requireNoDocumentOverflow(page, "1440×1000 默认状态");
  await page.screenshot({
    path: `${OUTPUT}/projects-preview-default-1440x1000.png`,
    fullPage: true,
  });

  await previewItems.filter({ hasText: "诊断导出示例" }).click();
  const selectedName = await page.locator("#previewDetailName").textContent();
  if (!selectedName.includes("诊断导出示例")) {
    throw new Error(`选择素材后详情未更新：${selectedName}`);
  }

  await page.selectOption("#prototypeState", "preview-loading");
  await requireVisible(
    page.locator("#projectPreviewPlaceholder"),
    "预览生成中没有显示稳定占位状态",
  );
  if (!await page.locator("#refreshProjectPreview").isDisabled()) {
    throw new Error("预览生成中仍允许重复刷新");
  }
  await page.screenshot({
    path: `${OUTPUT}/projects-preview-loading-1440x1000.png`,
    fullPage: true,
  });

  await page.selectOption("#prototypeState", "preview-failed");
  await requireVisible(
    page.locator("#projectPreviewPlaceholder"),
    "预览失败没有显示失败占位",
  );
  if (await page.locator("#refreshProjectPreview").isDisabled()) {
    throw new Error("预览失败后没有保留再次刷新入口");
  }
  await page.screenshot({
    path: `${OUTPUT}/projects-preview-failed-1440x1000.png`,
    fullPage: true,
  });

  await page.selectOption("#prototypeState", "preview-missing");
  if (
    !await page.locator("#openProjectMaterial").isDisabled()
    || !await page.locator("#openProjectMaterialFolder").isDisabled()
  ) {
    throw new Error("文件缺失时打开文件或目录没有禁用");
  }
  if (await page.locator("#locateProjectMaterial").isDisabled()) {
    throw new Error("文件缺失时素材库恢复入口被禁用");
  }
  await page.screenshot({
    path: `${OUTPUT}/projects-preview-missing-1440x1000.png`,
    fullPage: true,
  });

  await page.locator("#locateProjectMaterial").click();
  await requireVisible(
    page.locator("#projectReturnBanner"),
    "从项目跳转素材库后没有返回上下文",
  );
  await page.screenshot({
    path: `${OUTPUT}/library-return-context-1440x1000.png`,
    fullPage: true,
  });
  await page.locator("#returnToProject").click();
  await requireVisible(
    page.locator('[data-page-panel="projects"].is-active'),
    "返回项目后项目页未恢复",
  );

  await page.selectOption("#prototypeState", "default");
  await page.click('[data-page="projects"]');
  await page.locator("#rebuildProjectPreviews").click();
  await requireVisible(
    page.locator('#modalActions [data-contract="projects.preview-rebuild"]'),
    "重建预览确认入口未显示",
  );
  await page.locator('#modalActions [data-contract="projects.preview-rebuild"]').click();
  await requireVisible(
    page.locator(".preview-rebuild-progress"),
    "重建预览进度未显示",
  );
  await page.screenshot({
    path: `${OUTPUT}/projects-preview-rebuild-1440x1000.png`,
    fullPage: true,
  });
  await page.waitForTimeout(1700);

  await page.setViewportSize({ width: 960, height: 640 });
  await page.goto(`${BASE_URL}?page=projects&embed=1`, {
    waitUntil: "networkidle",
  });
  const minMetrics = await requireNoDocumentOverflow(page, "960×640 最小窗口");
  await page.locator("#projectPreviewDetail").scrollIntoViewIfNeeded();
  await requireVisible(
    page.locator("#projectPreviewDetail"),
    "最小窗口无法访问素材详情",
  );
  await page.screenshot({
    path: `${OUTPUT}/projects-preview-min-960x640.png`,
    fullPage: true,
  });

  const dpiResults = [];
  for (const scale of [1, 1.25, 1.5]) {
    const dpiPage = await browser.newPage({
      viewport: { width: 1200, height: 760 },
      deviceScaleFactor: scale,
    });
    const errors = [];
    dpiPage.on("pageerror", (error) => errors.push(error.message));
    await dpiPage.goto(`${BASE_URL}?page=projects&embed=1`, {
      waitUntil: "networkidle",
    });
    const metrics = await requireNoDocumentOverflow(
      dpiPage,
      `${Math.round(scale * 100)}% DPI`,
    );
    const detailVisible = await dpiPage.locator("#projectPreviewDetail").isVisible();
    if (!detailVisible || errors.length) {
      throw new Error(
        `${Math.round(scale * 100)}% DPI 验证失败：${errors.join(" | ")}`,
      );
    }
    await dpiPage.screenshot({
      path: `${OUTPUT}/projects-preview-dpi-${Math.round(scale * 100)}.png`,
      fullPage: true,
    });
    dpiResults.push({ scale, metrics });
    await dpiPage.close();
  }

  if (browserErrors.length) {
    throw new Error(browserErrors.join(" | "));
  }

  console.log(JSON.stringify({
    status: "PASS",
    navCount,
    previewCount,
    imagesValid,
    selectedName,
    minMetrics,
    dpiResults,
  }));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});

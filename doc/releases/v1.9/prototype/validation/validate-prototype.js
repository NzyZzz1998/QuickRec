"use strict";

const { chromium } = require("playwright");

const BASE_URL = process.env.QUICKREC_PROTOTYPE_URL
  || "http://127.0.0.1:8769/index.html";

async function requireVisible(locator, message) {
  if (!await locator.isVisible()) {
    throw new Error(message);
  }
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

  await page.click('[data-page="record"]');
  const modeCards = page.locator(".mode-card");
  if (await modeCards.count() !== 3) {
    throw new Error("录制页应展示三个平级模式模块");
  }
  if (await page.locator(".mode-card.is-selected").count() !== 0) {
    throw new Error("录制模式不应存在默认选中态");
  }
  const modeActions = page.locator(".mode-card .mode-action");
  for (let index = 0; index < await modeActions.count(); index += 1) {
    if (!await modeActions.nth(index).evaluate(
      (node) => node.classList.contains("button-secondary")
        && !node.classList.contains("button-primary"),
    )) {
      throw new Error("三个录制模式按钮的视觉层级不一致");
    }
  }
  await page.click("#chooseRecordMode");
  await page.waitForTimeout(150);
  await page.screenshot({
    path: "doc/releases/v1.9/prototype/validation/recording-modes-equal-1440x1000.png",
    fullPage: true,
  });
  await page.click('[data-page="projects"]');

  await requireVisible(
    page.locator('[data-page-panel="projects"]'),
    "项目页未显示",
  );
  await page.screenshot({
    path: "doc/releases/v1.9/prototype/validation/projects-default-1440x1000.png",
    fullPage: true,
  });

  await page.click("#createProject");
  await requireVisible(page.locator("#createProjectName"), "创建项目弹窗未显示");
  await page.click('#modalActions [data-contract="modal.cancel"]');

  await page.click("#addProjectMaterial");
  const pickerRows = await page.locator(".modal-picker .picker-row").count();
  if (pickerRows < 4) {
    throw new Error(`素材选择器状态不足，实际为 ${pickerRows}`);
  }
  await page.click('#modalActions [data-contract="modal.cancel"]');

  await page.click("#recordToProject");
  const recordingModes = await page.locator(
    '#modalActions [data-contract^="projects.record-"]',
  ).count();
  if (recordingModes !== 3) {
    throw new Error(`项目录制模式应为 3，实际为 ${recordingModes}`);
  }
  await page.click('#modalActions [data-contract="modal.cancel"]');

  await page.click("#archiveProject");
  await page.click('#modalActions [data-contract="projects.archive-confirm"]');
  await requireVisible(
    page.locator("#restoreProject"),
    "项目归档后没有显示恢复入口",
  );
  await page.click("#restoreProject");

  await page.click("#deleteProject");
  const selectable = page.locator(
    '.delete-row:not(.is-disabled) input[type="checkbox"]',
  );
  const selectableCount = await selectable.count();
  for (let index = 0; index < selectableCount; index += 1) {
    if (await selectable.nth(index).isChecked()) {
      throw new Error("独占视频在删除确认中被默认勾选");
    }
  }
  const disabledCount = await page.locator(
    ".delete-row.is-disabled input:disabled",
  ).count();
  if (disabledCount < 2) {
    throw new Error("共享或归属不确定素材的删除保护不足");
  }
  await page.screenshot({
    path: "doc/releases/v1.9/prototype/validation/projects-delete-1440x1000.png",
    fullPage: true,
  });
  await page.click('#modalActions [data-contract="modal.cancel"]');

  await page.selectOption("#prototypeState", "project-missing");
  await requireVisible(
    page.locator("#projectStatusBanner"),
    "项目缺失状态条未显示",
  );
  await page.click("#projectStatusAction");
  await requireVisible(
    page.locator('#modalActions [data-contract="projects.relink"]'),
    "项目重新定位入口未显示",
  );
  await page.click('#modalActions [data-contract="modal.cancel"]');

  await page.setViewportSize({ width: 960, height: 640 });
  await page.goto(`${BASE_URL}?page=projects&embed=1`, {
    waitUntil: "networkidle",
  });
  await page.screenshot({
    path: "doc/releases/v1.9/prototype/validation/projects-min-960x640.png",
    fullPage: true,
  });
  await page.locator("#deleteProject").scrollIntoViewIfNeeded();

  const viewportMetrics = await page.evaluate(() => {
    const deleteRect = document
      .querySelector("#deleteProject")
      .getBoundingClientRect();
    return {
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      viewportHeight: window.innerHeight,
      projectVisible: Boolean(
        document.querySelector('[data-page-panel="projects"].is-active'),
      ),
      deleteRect: {
        left: deleteRect.left,
        right: deleteRect.right,
        top: deleteRect.top,
        bottom: deleteRect.bottom,
      },
      navVisible: Array.from(document.querySelectorAll(".nav-button"))
        .every((node) => {
          const rect = node.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        }),
    };
  });

  if (!viewportMetrics.projectVisible || !viewportMetrics.navVisible) {
    throw new Error(
      `最小窗口结构不可用：${JSON.stringify(viewportMetrics)}`,
    );
  }
  if (
    viewportMetrics.deleteRect.top < 0
    || viewportMetrics.deleteRect.bottom > viewportMetrics.viewportHeight
  ) {
    throw new Error(
      `最小窗口无法滚动访问删除入口：${JSON.stringify(viewportMetrics)}`,
    );
  }
  if (browserErrors.length) {
    throw new Error(browserErrors.join(" | "));
  }

  console.log(JSON.stringify({
    status: "PASS",
    navCount,
    modeCards: await modeCards.count(),
    pickerRows,
    recordingModes,
    selectableCount,
    disabledCount,
    viewportMetrics,
  }));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});

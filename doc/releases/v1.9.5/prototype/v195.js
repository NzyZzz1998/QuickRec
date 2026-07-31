"use strict";

(() => {
  const withMeta = (spec, meta = {}) => Object.assign(spec, meta);
  const v195Contracts = {
    "timeline.previous-frame": withMeta(contract(
      "播放头向前一帧",
      "剪辑工作台已打开，焦点不在输入、按钮、菜单或弹窗中。",
      "按项目编辑帧率把播放头减去一帧；按住 Shift 时改为向前 1 秒。",
      "播放头、预览画面和帧时间码同步更新，并限制在时间线起点以内。",
      "播放运行时无法寻址时保留原位置，展示失败阶段和诊断入口。",
      "录制中、模态操作、文本输入焦点、时间线不可读或保存回滚中。",
      "该操作即时完成；到达时间线起点后继续触发不会改变状态。",
      "只改变同进程播放头，不写项目、素材、导出计划或用户配置。",
    ), { shortcut: "Left；Shift+Left 向前 1 秒。" }),
    "timeline.next-frame": withMeta(contract(
      "播放头向后一帧",
      "剪辑工作台已打开，焦点不在输入、按钮、菜单或弹窗中。",
      "按项目编辑帧率把播放头增加一帧；按住 Shift 时改为向后 1 秒。",
      "播放头、预览画面和帧时间码同步更新，不能越过最后片段结束点。",
      "播放运行时无法寻址时保留原位置，展示失败阶段和诊断入口。",
      "录制中、模态操作、文本输入焦点、时间线不可读或保存回滚中。",
      "该操作即时完成；到达播放终点后继续触发不会空播。",
      "只改变同进程播放头，不写项目、素材、导出计划或用户配置。",
    ), { shortcut: "Right；Shift+Right 向后 1 秒。" }),
    "timeline.delete-gap": withMeta(contract(
      "普通删除并保留空隙",
      "已选中可写、未锁定的片段或有效关联组，当前没有录制、保存或模态事务。",
      "显示一次确认；关联片段按完整关联组删除，未关联片段只删除当前片段，其他片段位置逐字保持。",
      "目标从时间线消失，原区间显示为空隙，项目原子保存并产生一条撤销记录。",
      "校验或保存失败时恢复片段、选择、历史和项目文件，不留下半删除状态。",
      "无选择、轨道锁定、项目只读、版本未知、录制中、保存中或存在未提交候选。",
      "取消确认不改变片段、播放头、选择或项目文件。",
      "只删除时间线片段引用；不删除项目素材、中央索引、原始视频或既有导出。",
    ), { shortcut: "Delete。" }),
    "timeline.ripple-menu": withMeta(contract(
      "打开删除方式菜单",
      "时间线工具栏可用；当前可没有选择，以便用户查看操作说明。",
      "打开紧邻垃圾桶的菜单，展示“全局波纹删除”和 Shift+Delete。",
      "菜单保持在按钮下方；选择操作后进入波纹影响预览。",
      "菜单定位失败时关闭菜单，不触发删除。",
      "模态对话框已打开或应用正在退出。",
      "点击外部、按 Esc 或再次点击箭头关闭菜单，不修改项目。",
      "菜单本身只改变界面状态，不写项目。",
    ), { shortcut: "Shift+Delete 可绕过菜单直接进入影响预览。" }),
    "timeline.ripple-delete-v195": withMeta(contract(
      "全局波纹删除",
      "已选中可写、未锁定片段或关联组，当前没有录制、保存或其他候选。",
      "计算删除区间、锁定冲突、受影响轨道和片段；先展示影响预览，确认后收拢全部允许移动的后续片段。",
      "目标删除、后续片段整体前移、总时长更新，并以一个事务原子保存。",
      "锁定轨或交叉区间冲突会禁用确认；保存失败时整体回滚。",
      "无选择、只读、版本未知、录制中、保存中或存在冲突。",
      "取消影响预览时不删除、不移动、不写项目。",
      "只修改时间线片段及位置；不删除真实媒体。沿用 v1.9.3 全局波纹算法。",
    ), { shortcut: "Shift+Delete。" }),
    "timeline.unlink": withMeta(contract(
      "解绑关联音视频",
      "当前片段属于恰含一条视频和一条音频的有效关联组；双方轨道未锁定，项目可写。",
      "显示身份保持摘要；确认后只把双方 link_group_id 清空，不改变任何身份、位置、时长或源范围。",
      "两个片段显示“未关联”，当前片段保持选中，后续可独立移动、裁剪、分割和删除。",
      "保存失败时恢复原 link_group_id、选择和历史，不出现单侧解绑。",
      "无有效关联组、轨道锁定、只读、版本未知、录制中、保存中或已有模态事务。",
      "取消确认保持原关联关系；素材缺失不阻止解绑。",
      "写项目 timeline 扩展；不修改原媒体、中央素材索引、缓存或导出历史。",
    ), { shortcut: "Ctrl+L；已关联时执行解绑。" }),
    "timeline.unlink-confirm": withMeta(contract(
      "确认解绑",
      "解绑影响摘要已展示，关联组仍满足原始校验。",
      "以一个事务清空双方 link_group_id，并执行一次项目原子保存。",
      "显示已解绑反馈；按钮语义切换为“重新关联”。",
      "事务或保存失败时完整回滚并保留对话框中的错误说明。",
      "候选过期、任一轨锁定、项目状态变化或保存中。",
      "取消返回时间线，双方保持关联。",
      "产生一条可撤销命令；不会改变媒体文件。",
    ), { shortcut: "Enter 可提交当前主按钮；Esc 取消。" }),
    "timeline.relink": withMeta(contract(
      "严格重新关联",
      "当前片段未关联、素材存在、项目可写，且存在满足全部兼容条件的异类轨片段。",
      "打开只含兼容候选的列表；不自动移动、裁剪或对齐任何片段。",
      "确认后双方保留原 clip_id，写入同一个新 link_group_id，并原子保存。",
      "无候选时显示逐项原因；保存失败时双方继续保持未关联。",
      "当前片段已关联、素材缺失、轨道锁定、只读、录制中、保存中或版本未知。",
      "取消关闭候选列表，不创建空关联。",
      "只写双方 link_group_id；不改变轨道、时间位置、源范围或媒体文件。",
    ), { shortcut: "Ctrl+L；未关联时打开候选。" }),
    "timeline.relink-confirm": withMeta(contract(
      "确认重新关联",
      "已选择一条仍满足素材、轨道、时间、源范围和文件状态兼容条件的候选。",
      "重新校验候选并生成新的全局唯一 link_group_id，双方一次性写入。",
      "当前片段保持选中，两个片段显示新的关联状态并完成原子保存。",
      "候选过期、保存失败或任一状态变化时零修改，列表保留最新原因。",
      "没有选择候选或候选不再兼容。",
      "取消不修改两个片段。",
      "产生一条可撤销命令；撤销后双方恢复未关联。",
    ), { shortcut: "Enter 提交；Esc 取消。" }),
    "timeline.editing-fps": withMeta(contract(
      "项目编辑帧率",
      "项目时间线从未包含片段，项目可写且 quickrec.editing 扩展版本可读。",
      "在 30、60、120 FPS 中选择项目统一编辑基准；底层时间继续使用整数微秒。",
      "帧时间码、逐帧导航、吸附和输入统一使用新帧率；显式保存后写项目扩展。",
      "扩展损坏、版本未知或保存失败时保留原帧率并进入安全状态。",
      "时间线已出现过片段后永久锁定；项目只读、录制中或保存中也禁用。",
      "离开未保存草稿时按保存、放弃、取消合同处理。",
      "写 extensions[\"quickrec.editing\"].editing_fps；不量化或改写旧片段微秒位置。",
    ), { shortcut: "无。该项目级属性只能通过可见下拉框修改。" }),
    "timeline.drag-drop": withMeta(contract(
      "把项目素材拖入时间线",
      "素材可解析、项目可写、没有录制/保存/模态事务，且拖动指针进入时间线。",
      "持续计算目标轨、帧级时间、吸附来源、关联音频落点、冲突和是否需要自动建轨。",
      "有效落点显示完整候选；松开后以一个事务加入片段并保存。",
      "无效类型、锁定轨、越界、轨道上限或保存失败时说明原因且零修改。",
      "素材缺失、只读、版本未知、保存中，或悬停的明确目标轨已锁定。",
      "按 Esc、拖出时间线或在无效位置松开会取消，不创建空轨。",
      "成功只写时间线片段/必要轨道；不复制、移动或修改源视频。",
    ), { shortcut: "Esc 取消当前拖放候选。" }),
    "timeline.auto-track": withMeta(contract(
      "条件性自动创建轨道",
      "不存在兼容未锁定轨，或全部兼容未锁定轨在候选区间冲突；对应类型尚未达到 8 条。",
      "候选明确标注将新建的视频轨、音频轨或关联轨对及稳定插入位置。",
      "新轨与片段作为一个事务提交；视频轨加在视频组顶部，音频轨加在音频组底部。",
      "创建、加入或保存任一步失败时删除本事务产生的片段和空轨。",
      "明确悬停轨已锁定、类型不兼容、轨道达到上限、只读或保存中。",
      "拖放取消时不创建轨道。",
      "一个撤销动作同时移除新增片段和仍为空的新轨。",
    ), { shortcut: "无；由拖放落点规则自动触发，但必须在松开前可见。" }),
    "timeline.drag-cancel": withMeta(contract(
      "取消拖放候选",
      "当前存在素材拖放、吸附或自动建轨候选。",
      "清除候选轮廓、目标轨、吸附线、自动建轨标签和临时状态。",
      "素材列表、轨道、片段、选择和项目文件保持原样。",
      "清理异常时下一次拖动前强制重置交互状态。",
      "当前没有候选时无需执行。",
      "该动作本身就是取消。",
      "不写业务数据。",
    ), { shortcut: "Esc。" }),
    "timeline.shortcut-focus": withMeta(contract(
      "快捷键焦点保护",
      "输入框、时间码、按钮、列表、菜单或模态对话框拥有键盘焦点。",
      "保留控件原生按键语义，阻止时间线窗口级快捷键误触发。",
      "Space 点击聚焦按钮；Delete 删除输入字符；方向键导航输入或列表。",
      "焦点路由异常时不执行破坏性命令，并记录冲突控件类型。",
      "该规则始终优先于时间线快捷键，不可由页面绕过。",
      "焦点离开控件后恢复时间线快捷键。",
      "只决定输入路由，不写项目。",
    ), { shortcut: "适用于 Space、Delete、Shift+Delete、方向键、Ctrl+B、Ctrl+L、Ctrl+Z/Y。" }),
    "timeline.timecode-input": withMeta(contract(
      "帧时间码输入",
      "项目编辑帧率有效，输入控件可编辑且项目状态允许跳转。",
      "解析 HH:MM:SS:FF，使用有理数帧换算和四舍五入映射到整数微秒。",
      "播放头落到最近项目帧；重新格式化为对应 30/60/120 FPS 位数。",
      "格式、帧号或边界非法时显示行内错误，播放头保持原位置。",
      "播放运行时不可用、项目版本未知或模态事务冲突。",
      "Esc 恢复进入输入前的时间码。",
      "只改变播放头，不改片段或项目文件。",
    ), { shortcut: "输入期间所有时间线快捷键让出；Enter 应用，Esc 取消。" }),
  };

  Object.assign(contracts, v195Contracts);

  Object.assign(contracts, {
    "timeline.material-add": withMeta(contract(
      "把素材加入时间线",
      "素材可解析、项目可写，且至少存在有效落点或允许条件性自动建轨。",
      "按钮按稳定默认规则追加；拖动时实时显示目标轨、帧级时间、吸附来源、关联音频和自动建轨候选。",
      "片段及必要轨道以一个事务写入，选中新片段并完成一次原子保存。",
      "类型不兼容、锁定、冲突、轨道上限或保存失败时零修改并说明原因。",
      "素材缺失、只读、版本未知、录制中或保存中。",
      "拖动中按 Esc 或按钮链路失败均不留下空轨。",
      "只新增稳定片段引用和必要轨道，不复制或修改原视频。",
    ), {
      introduced: "v1.9.2",
      optimized: "v1.9.5 加入帧级吸附、落点预览、类型校验和条件性自动建轨。",
      undo: "成功后形成一条命令；若本次自动建轨，Ctrl+Z 同时移除片段和仍为空的新轨。",
    }),
    "timeline.clip": withMeta(contract(
      "时间线片段",
      "片段和来源引用存在；可写操作还要求轨道未锁定、项目可写且无保存事务。",
      "单击选择、双击跳转、拖动移动；关联状态决定操作作用于关联组还是单片段。",
      "有效操作原子保存，保持 clip_id；解绑后可独立编辑，重新关联后恢复联合编辑。",
      "重叠、类型、越界、锁定或保存失败时恢复原状态。",
      "项目只读、版本未知、保存中或来源操作需要媒体但文件缺失。",
      "拖动按 Esc 取消；右键菜单关闭时不执行命令。",
      "选择不写项目；成功编辑仅修改时间线，永不修改源媒体。",
    ), {
      introduced: "v1.9.2",
      optimized: "v1.9.3 增加裁剪/分割；v1.9.5 增加解绑、独立编辑、双删除与帧级吸附。",
    }),
  });

  const versionToggle = document.getElementById("toggleVersionHistory");
  const versionStrip = document.getElementById("versionEvolutionStrip");
  const stateSelect = document.getElementById("prototypeState");
  const workspace = document.getElementById("timelineWorkspace");
  const playButton = document.getElementById("timelinePlayPause");
  const seek = document.getElementById("timelineSeek");
  const currentTime = document.getElementById("timelineCurrentTime");
  const durationTime = document.querySelector(".timeline-duration");
  const footerStatus = document.getElementById("timelineFooterStatus");
  const fpsSelect = document.getElementById("timelineEditingFps");
  const previousFrameButton = document.getElementById("timelinePreviousFrame");
  const nextFrameButton = document.getElementById("timelineNextFrame");
  const deleteButton = document.getElementById("deleteTimelineClip");
  const rippleMenuButton = document.getElementById("openRippleDeleteMenu");
  const ripplePopover = document.getElementById("rippleDeletePopover");
  const rippleDeleteButton = document.getElementById("rippleDeleteTimelineClip");
  const linkButton = document.getElementById("toggleClipLink");
  const linkButtonLabel = document.getElementById("toggleClipLinkLabel");
  const linkState = document.getElementById("timelineLinkState");
  const dragOverlay = document.getElementById("timelineDragOverlay");
  const dragEyebrow = document.getElementById("dragContractEyebrow");
  const dragTitle = document.getElementById("dragContractTitle");
  const dragDetail = document.getElementById("dragContractDetail");
  const dragStatus = document.getElementById("dragContractStatus");
  const selectedVideo = document.querySelector('[data-clip-id="clip-v2"]');
  const linkedAudio = document.querySelector('[data-clip-id="clip-a2"]');
  const selectedLane = selectedVideo?.closest(".timeline-lane");
  let editingFps = 60;
  let linked = true;
  let forceNoRelinkCandidates = false;
  let materialDrag = null;
  let keyboardHandledAt = 0;

  function registerV195Contracts(root = document) {
    root.querySelectorAll("[data-contract]").forEach((element) => {
      if (!element.dataset.contractRegistered && contracts[element.dataset.contract]) {
        registerContractElement(element);
      }
    });
  }

  registerV195Contracts();

  function setVersionHistory(visible) {
    document.body.classList.toggle("show-version-history", visible);
    versionStrip.hidden = !visible;
    versionToggle.classList.toggle("is-active", visible);
    versionToggle.textContent = visible ? "收起版本脉络" : "版本脉络";
  }

  versionToggle.addEventListener("click", () => {
    setVersionHistory(!document.body.classList.contains("show-version-history"));
  });

  function formatFrameTime(milliseconds, fps = editingFps) {
    const frameDuration = 1000 / fps;
    const totalFrames = Math.max(0, Math.round(Number(milliseconds) / frameDuration));
    const frames = totalFrames % fps;
    const totalSeconds = Math.floor(totalFrames / fps);
    const seconds = totalSeconds % 60;
    const totalMinutes = Math.floor(totalSeconds / 60);
    const minutes = totalMinutes % 60;
    const hours = Math.floor(totalMinutes / 60);
    return [hours, minutes, seconds, frames].map((value) => String(value).padStart(2, "0")).join(":");
  }

  function updateFrameReadout() {
    const current = Number(seek.value);
    const duration = Number(seek.max);
    currentTime.textContent = formatFrameTime(current);
    durationTime.textContent = formatFrameTime(duration);
    footerStatus.textContent = `timeline schema v2 · editing ${editingFps} FPS · 微秒存储 · 撤销历史 1 / 50 · 总时长 ${formatFrameTime(duration)}`;
  }

  function movePlayheadBy(deltaMilliseconds) {
    const next = Math.max(Number(seek.min), Math.min(Number(seek.max), Number(seek.value) + deltaMilliseconds));
    seek.value = String(next);
    seek.dispatchEvent(new Event("input", { bubbles: true }));
    updateFrameReadout();
    showToast("播放头已移动", `${formatFrameTime(next)} · ${editingFps} FPS 项目帧。`, "success");
  }

  previousFrameButton.addEventListener("click", () => movePlayheadBy(-1000 / editingFps));
  nextFrameButton.addEventListener("click", () => movePlayheadBy(1000 / editingFps));
  seek.addEventListener("input", updateFrameReadout);
  fpsSelect.addEventListener("change", () => {
    editingFps = Number(fpsSelect.value);
    updateFrameReadout();
    showToast("项目编辑帧率草稿已更新", `${editingFps} FPS 仅在空时间线可选；仍需显式保存。`);
  });

  window.setInterval(() => {
    if (document.body.classList.contains("timeline-window-open")) updateFrameReadout();
  }, 160);
  updateFrameReadout();

  function setLinkedState(nextLinked, newGroup = "A2") {
    linked = nextLinked;
    [selectedVideo, linkedAudio].forEach((clip) => {
      if (!clip) return;
      clip.classList.toggle("is-unlinked", !linked);
      clip.dataset.linked = String(linked);
      const chip = clip.querySelector(".clip-link");
      if (chip) {
        chip.dataset.linkGroup = linked ? newGroup : "";
        chip.innerHTML = linked
          ? `<svg><use href="#i-link"></use></svg>${clip === selectedVideo ? newGroup : "V2"}`
          : "未关联";
      }
      const copy = clip.querySelector(".clip-copy small");
      if (copy && clip === linkedAudio) copy.textContent = linked ? "关联 V2" : "独立音频片段";
    });
    linkState.classList.toggle("is-linked", linked);
    linkState.classList.toggle("is-unlinked", !linked);
    linkState.innerHTML = linked
      ? `<svg><use href="#i-link"></use></svg>${newGroup} 已关联`
      : `<svg><use href="#i-unlink"></use></svg>未关联 · 可独立编辑`;
    linkButton.dataset.contract = linked ? "timeline.unlink" : "timeline.relink";
    linkButtonLabel.textContent = linked ? "解绑" : "重新关联";
    linkButton.querySelector("use").setAttribute("href", linked ? "#i-unlink" : "#i-link");
    linkButton.title = linked ? "解绑音视频 Ctrl+L" : "重新关联音视频 Ctrl+L";
    linkButton.dataset.contractRegistered = "false";
    delete linkButton.dataset.contractIndex;
    registerContractElement(linkButton);
    document.getElementById("timelineClipDetail").textContent = linked
      ? "源 00:12.000–00:33.000 · 关联音频 A2"
      : "源 00:12.000–00:33.000 · 当前为独立视频片段";
  }

  function showUnlinkDialog() {
    showModal({
      title: "解绑关联音视频？",
      text: "解绑只移除同步编辑关系。片段身份、轨道、时间位置、源范围和原媒体全部保持不变。",
      icon: "info",
      detailHtml: `
        <dl class="v195-dialog-summary">
          <div><dt>视频片段</dt><dd>clip-v2 · 视频 2 · 00:12:00–00:33:00</dd></div>
          <div><dt>音频片段</dt><dd>clip-a2 · 音频 2 · 00:12:00–00:33:00</dd></div>
          <div><dt>唯一变化</dt><dd>双方 link_group_id 从 A2 变为 null。</dd></div>
          <div><dt>后续行为</dt><dd>双方可独立移动、裁剪、分割和删除；可通过严格候选重新关联。</dd></div>
        </dl>
      `,
      actions: [
        { label: "取消", contract: "modal.cancel", onClick: closeModal },
        {
          label: "确认解绑",
          kind: "button-primary",
          contract: "timeline.unlink-confirm",
          onClick: () => {
            closeModal();
            setLinkedState(false);
            document.getElementById("timelineUndo").disabled = false;
            showToast("音视频已解绑", "双方身份和位置未变；现在可独立编辑。Ctrl+Z 可恢复。", "success");
          },
        },
      ],
    });
    registerV195Contracts(document.getElementById("modalLayer"));
  }

  function showRelinkDialog(noCandidates = forceNoRelinkCandidates) {
    const detailHtml = noCandidates
      ? `
        <div class="v195-dialog-summary">
          <div><dt>兼容结果</dt><dd>没有兼容候选。候选必须素材 ID、时间位置、时长和源范围全部一致。</dd></div>
          <div><dt>未自动修正</dt><dd>QuickRec 不会移动、裁剪或对齐片段来制造关联。</dd></div>
          <div><dt>下一步</dt><dd>关闭后独立调整片段；满足完整条件后再执行 Ctrl+L。</dd></div>
        </div>
      `
      : `
        <div class="relink-candidate-list">
          <label class="relink-candidate is-selected">
            <input type="radio" name="relinkCandidate" value="clip-a2" checked>
            <span class="relink-candidate-copy">
              <strong>诊断导出 · 音频 · A2</strong>
              <small>音频 2 · 00:12:00–00:33:00 · 源 00:12:00–00:33:00</small>
              <small>material_id 相同 · 文件存在 · 轨道未锁定</small>
            </span>
          </label>
        </div>
        <dl class="v195-dialog-summary">
          <div><dt>排除项</dt><dd>1 条音频因源范围不同被排除；1 条视频因类型相同被排除。</dd></div>
          <div><dt>提交结果</dt><dd>双方生成新的 link_group_id；不会恢复历史 A2。</dd></div>
        </dl>
      `;
    const actions = [{ label: "取消", contract: "modal.cancel", onClick: closeModal }];
    if (!noCandidates) {
      actions.push({
        label: "关联所选片段",
        kind: "button-primary",
        contract: "timeline.relink-confirm",
        onClick: () => {
          closeModal();
          setLinkedState(true, "A3");
          document.getElementById("timelineUndo").disabled = false;
          showToast("音视频已重新关联", "双方写入新的关联 ID A3；原片段身份保持。", "success");
        },
      });
    }
    showModal({
      title: noCandidates ? "没有兼容的关联候选" : "重新关联音视频",
      text: noCandidates
        ? "当前片段保持未关联，不会写入空关系。"
        : "列表只展示满足全部严格条件的异类轨片段。",
      icon: noCandidates ? "warning" : "info",
      detailHtml,
      actions,
    });
    registerV195Contracts(document.getElementById("modalLayer"));
  }

  linkButton.addEventListener("click", (event) => {
    if (document.querySelector(".workbench-body")?.classList.contains("show-contracts")) return;
    event.stopImmediatePropagation();
    if (linked) showUnlinkDialog();
    else showRelinkDialog();
  }, true);

  function showDeleteGapDialog() {
    const targetText = linked
      ? "当前视频与关联音频将作为一个组删除。"
      : "只删除当前选中的视频片段；独立音频保持。";
    showModal({
      title: "删除并保留空隙？",
      text: `${targetText} 其他片段不会移动，原始视频不会删除。`,
      icon: "warning",
      detailHtml: `
        <dl class="v195-dialog-summary">
          <div><dt>删除范围</dt><dd>时间线 00:12:00–00:33:00，${linked ? "关联组 A2" : "仅 clip-v2"}。</dd></div>
          <div><dt>后续片段</dt><dd>timeline_start_us 逐字保持，不执行波纹收拢。</dd></div>
          <div><dt>可恢复性</dt><dd>一次命令、一次保存，可通过 Ctrl+Z 撤销。</dd></div>
        </dl>
      `,
      actions: [
        { label: "取消", contract: "modal.cancel", onClick: closeModal },
        {
          label: "删除并保留空隙",
          kind: "button-primary",
          contract: "timeline.delete-gap",
          onClick: () => {
            closeModal();
            selectedVideo.classList.add("is-gap-deleted");
            if (linked) linkedAudio.classList.add("is-gap-deleted");
            selectedLane.classList.add("has-deleted-gap");
            selectedVideo.classList.remove("is-selected");
            document.getElementById("timelineUndo").disabled = false;
            showToast("片段已删除，空隙已保留", "其他片段位置未变化；Ctrl+Z 可撤销。", "success");
          },
        },
      ],
    });
    registerV195Contracts(document.getElementById("modalLayer"));
  }

  deleteButton.addEventListener("click", (event) => {
    if (document.querySelector(".workbench-body")?.classList.contains("show-contracts")) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    showDeleteGapDialog();
  }, true);

  function closeRippleMenu() {
    ripplePopover.hidden = true;
    rippleMenuButton.setAttribute("aria-expanded", "false");
  }

  rippleMenuButton.addEventListener("click", (event) => {
    event.stopPropagation();
    const opening = ripplePopover.hidden;
    ripplePopover.hidden = !opening;
    rippleMenuButton.setAttribute("aria-expanded", String(opening));
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#deleteActionGroup")) closeRippleMenu();
  });
  rippleDeleteButton.addEventListener("click", () => {
    closeRippleMenu();
    stateSelect.value = "timeline-ripple-preview";
    stateSelect.dispatchEvent(new Event("change", { bubbles: true }));
    showToast("已生成全局波纹影响预览", "确认前不会删除或移动任何片段。");
  });

  function setDragOverlay(mode, title, detail) {
    dragOverlay.hidden = false;
    dragOverlay.classList.toggle("is-auto", mode === "auto");
    dragOverlay.classList.toggle("is-invalid", mode === "invalid");
    dragEyebrow.textContent = mode === "auto" ? "条件性自动建轨候选" : mode === "invalid" ? "当前落点不可用" : "吸附到现有轨道";
    dragTitle.textContent = title;
    dragDetail.textContent = detail;
    dragStatus.textContent = mode === "invalid" ? "不可放置" : mode === "auto" ? "松开后新建" : "可放置";
  }

  function clearMaterialDrag() {
    materialDrag?.classList.remove("is-dragging");
    materialDrag = null;
    dragOverlay.hidden = true;
    document.querySelectorAll(".timeline-lane").forEach((lane) => {
      lane.classList.remove("is-material-drop-target", "is-material-drop-invalid", "is-material-drop-auto");
    });
  }

  function createDemoClip(lane, kind, name, start = 68) {
    const clip = document.createElement("button");
    clip.type = "button";
    clip.className = `timeline-clip clip-${kind} clip-blue`;
    clip.dataset.clipId = `clip-v195-${kind}-${Date.now()}`;
    clip.dataset.start = String(start);
    clip.dataset.duration = "15";
    clip.dataset.sourceStartMs = "0";
    clip.dataset.sourceEndMs = "9000";
    clip.dataset.materialDurationMs = "9000";
    clip.draggable = true;
    clip.dataset.contract = "timeline.clip";
    clip.innerHTML = kind === "video"
      ? `<span class="clip-grip"><svg><use href="#i-grip"></use></svg></span><span class="clip-copy"><strong>${name}</strong><small>智能拖放 · 9 秒</small></span>`
      : `<span class="clip-wave"></span><span class="clip-copy"><strong>${name} · 音频</strong><small>关联新视频</small></span>`;
    lane.appendChild(clip);
    registerV195Contracts(clip.parentElement);
    return clip;
  }

  function createAutoTrack(kind) {
    const rows = [...document.querySelectorAll(`.timeline-track-row[data-track-kind="${kind}"]`)];
    if (rows.length >= 8) return null;
    const row = document.createElement("div");
    row.className = "timeline-track-row is-v195-auto-track";
    row.dataset.trackId = `${kind}-auto-${Date.now()}`;
    row.dataset.trackKind = kind;
    row.dataset.locked = "false";
    const label = `${kind === "video" ? "视频" : "音频"} ${rows.length + 1}`;
    row.innerHTML = `
      <div class="timeline-track-header">
        <button type="button" class="track-grip" aria-label="调整${label}轨道顺序" data-contract="timeline.track-reorder"><svg><use href="#i-grip"></use></svg></button>
        <span class="track-kind-icon${kind === "audio" ? " is-audio" : ""}"><svg><use href="#i-${kind}"></use></svg></span>
        <button type="button" class="track-name" data-contract="timeline.track-rename">${label}</button>
        <span class="track-status">自动创建</span>
        <button type="button" class="track-lock" aria-label="锁定${label}" data-contract="timeline.track-lock"><svg><use href="#i-unlock"></use></svg></button>
        <button type="button" class="track-delete" aria-label="删除${label}" data-contract="timeline.track-delete"><svg><use href="#i-trash"></use></svg></button>
      </div>
      <div class="timeline-lane ${kind}-lane"><i class="timeline-playhead-line" style="left:21.52%"></i></div>
    `;
    const grid = document.getElementById("timelineGrid");
    if (kind === "video") {
      const firstVideo = grid.querySelector('.timeline-track-row[data-track-kind="video"]');
      grid.insertBefore(row, firstVideo);
    } else {
      grid.appendChild(row);
    }
    registerV195Contracts(row);
    return row;
  }

  document.querySelectorAll(".timeline-material-card:not(.is-missing)").forEach((card) => {
    card.draggable = true;
    card.tabIndex = 0;
    card.dataset.contract = "timeline.drag-drop";
    card.addEventListener("dragstart", (event) => {
      materialDrag = card;
      card.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "copy";
      event.dataTransfer.setData("text/plain", card.dataset.timelineMaterial || "material");
      setDragOverlay("existing", "视频 1 · 00:00:34:12", "吸附片段尾部；含音频素材会同步显示音频落点。");
    });
    card.addEventListener("dragend", clearMaterialDrag);
  });
  registerV195Contracts();

  document.querySelectorAll(".timeline-lane").forEach((lane) => {
    lane.addEventListener("dragover", (event) => {
      if (!materialDrag) return;
      event.preventDefault();
      const row = lane.closest(".timeline-track-row");
      const kind = row.dataset.trackKind;
      const locked = row.dataset.locked === "true";
      const forceAuto = event.shiftKey || lane.querySelectorAll(".timeline-clip").length >= 2;
      lane.classList.toggle("is-material-drop-invalid", locked);
      lane.classList.toggle("is-material-drop-auto", !locked && forceAuto);
      lane.classList.toggle("is-material-drop-target", !locked && !forceAuto);
      if (locked) {
        setDragOverlay("invalid", `${row.querySelector(".track-name").textContent.trim()} 已锁定`, "明确悬停锁定轨时不会静默绕过并自动新建轨道。");
      } else if (forceAuto) {
        setDragOverlay("auto", `将新建${kind === "video" ? "视频轨 + 关联音频轨" : "音频轨"}`, "现有兼容轨在候选区间冲突；松开后以一个事务创建并加入。");
      } else {
        setDragOverlay("existing", `${row.querySelector(".track-name").textContent.trim()} · 00:00:34:12`, "吸附到片段尾部；落点按 60 FPS 项目帧归一化。");
      }
    }, true);
    lane.addEventListener("dragleave", () => {
      lane.classList.remove("is-material-drop-target", "is-material-drop-invalid", "is-material-drop-auto");
    });
    lane.addEventListener("drop", (event) => {
      if (!materialDrag) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const row = lane.closest(".timeline-track-row");
      if (row.dataset.locked === "true") {
        showToast("目标轨道已锁定", "不会自动绕过明确悬停的锁定轨道。", "warning");
        clearMaterialDrag();
        return;
      }
      const auto = lane.classList.contains("is-material-drop-auto");
      const sourceName = materialDrag.querySelector("strong")?.textContent || "拖入素材";
      let targetLane = lane;
      let audioLane = null;
      if (auto) {
        const videoRow = createAutoTrack("video");
        const audioRow = createAutoTrack("audio");
        if (!videoRow || !audioRow) {
          showToast("轨道已达到上限", "视频或音频轨已达到 8 条；本次拖放零修改。", "warning");
          videoRow?.remove();
          audioRow?.remove();
          clearMaterialDrag();
          return;
        }
        targetLane = videoRow.querySelector(".timeline-lane");
        audioLane = audioRow.querySelector(".timeline-lane");
      } else if (row.dataset.trackKind === "video") {
        audioLane = document.querySelector('.timeline-track-row[data-track-kind="audio"]:not([data-locked="true"]) .timeline-lane');
      }
      const videoClip = createDemoClip(targetLane, row.dataset.trackKind === "audio" ? "audio" : "video", sourceName);
      if (audioLane && row.dataset.trackKind !== "audio") {
        const audioClip = createDemoClip(audioLane, "audio", sourceName);
        const newGroup = `A${Date.now().toString().slice(-3)}`;
        videoClip.dataset.linked = "true";
        audioClip.dataset.linked = "true";
      }
      document.getElementById("timelineUndo").disabled = false;
      showToast(
        auto ? "素材与新轨道已加入" : "素材已吸附到现有轨道",
        auto ? "新轨和关联片段属于一个可撤销事务。" : "落点、吸附和关联音频已原子保存。",
        "success",
      );
      clearMaterialDrag();
    }, true);
  });

  function showShortcutFocusDemo() {
    showModal({
      title: "快捷键焦点优先级",
      text: "在下方输入框中按 Space、Delete 或方向键，时间线不会播放、删除片段或移动播放头。",
      detailHtml: `
        <label class="field">
          <span>帧时间码</span>
          <input id="v195FocusInput" type="text" value="${formatFrameTime(Number(seek.value))}" data-contract="timeline.timecode-input">
          <small>格式 HH:MM:SS:FF；当前 ${editingFps} FPS。</small>
        </label>
        <dl class="v195-dialog-summary">
          <div><dt>焦点规则</dt><dd>输入与模态操作优先于所有时间线窗口级快捷键。</dd></div>
          <div><dt>关闭后</dt><dd>焦点回到剪辑画布，Space 和方向键恢复时间线语义。</dd></div>
        </dl>
      `,
      actions: [{ label: "关闭", contract: "modal.cancel", onClick: closeModal }],
    });
    registerV195Contracts(document.getElementById("modalLayer"));
    document.getElementById("v195FocusInput")?.focus();
  }

  function showDragState(mode) {
    const states = {
      existing: ["existing", "视频 1 · 00:00:34:12", "吸附片段尾部；落点为 60 FPS 项目帧。"],
      "auto-video": ["auto", "将新建视频轨 3", "全部现有视频轨冲突；新轨位于视频组顶部。"],
      "auto-pair": ["auto", "将新建视频轨 3 + 音频轨 3", "含音频 MP4；轨对和片段使用一个事务。"],
      invalid: ["invalid", "目标音频轨已锁定", "不会静默绕过锁定轨；解锁或选择其他轨道。"],
    };
    setDragOverlay(...states[mode]);
  }

  stateSelect.addEventListener("change", () => {
    const state = stateSelect.value;
    if (!state.startsWith("timeline-")) return;
    closeRippleMenu();
    dragOverlay.hidden = true;
    forceNoRelinkCandidates = false;
    if (state === "timeline-unlink-candidate") {
      if (!linked) setLinkedState(true, "A2");
      showUnlinkDialog();
    } else if (state === "timeline-unlinked") {
      setLinkedState(false);
      showToast("状态演示：音视频已解绑", "选中视频后移动、裁剪、分割和删除只作用于视频。");
    } else if (state === "timeline-relink-candidates") {
      setLinkedState(false);
      showRelinkDialog(false);
    } else if (state === "timeline-relink-empty") {
      setLinkedState(false);
      forceNoRelinkCandidates = true;
      showRelinkDialog(true);
    } else if (state === "timeline-delete-gap") {
      showDeleteGapDialog();
    } else if (state === "timeline-drag-existing") {
      showDragState("existing");
    } else if (state === "timeline-drag-auto-video") {
      showDragState("auto-video");
    } else if (state === "timeline-drag-auto-pair") {
      showDragState("auto-pair");
    } else if (state === "timeline-drag-invalid") {
      showDragState("invalid");
    } else if (state === "timeline-track-limit") {
      showDragState("invalid");
      dragTitle.textContent = "视频轨和音频轨均已达到 8 条";
      dragDetail.textContent = "本次拖放不会创建空轨或半成功片段；请先整理轨道。";
    } else if (/timeline-fps-(30|60|120)/.test(state)) {
      editingFps = Number(state.split("-").pop());
      fpsSelect.disabled = false;
      fpsSelect.value = String(editingFps);
      updateFrameReadout();
      showToast(`状态演示：${editingFps} FPS 项目帧`, `时间码按 ${editingFps} FPS 显示；实际非空项目中该控件锁定。`);
    } else if (state === "timeline-shortcut-focus") {
      showShortcutFocusDemo();
    }
  });

  function timelineHasModalOrMenu() {
    return !document.getElementById("modalLayer").hidden || !ripplePopover.hidden;
  }

  function focusOwnsShortcut(target) {
    if (!target) return false;
    return Boolean(target.closest("input, textarea, select, button, [role='menu'], [role='listbox'], [contenteditable='true']"));
  }

  document.addEventListener("keydown", (event) => {
    if (!document.body.classList.contains("timeline-window-open")) return;
    const focusProtected = timelineHasModalOrMenu() || focusOwnsShortcut(event.target);
    if (focusProtected) {
      if (["Space", "Delete", "ArrowLeft", "ArrowRight"].includes(event.code) || event.ctrlKey) {
        keyboardHandledAt = Date.now();
      }
      return;
    }
    const key = event.key.toLocaleLowerCase("en-US");
    let handled = true;
    if (event.code === "Space") {
      playButton.click();
    } else if (event.key === "ArrowLeft") {
      movePlayheadBy(event.shiftKey ? -1000 : -1000 / editingFps);
    } else if (event.key === "ArrowRight") {
      movePlayheadBy(event.shiftKey ? 1000 : 1000 / editingFps);
    } else if (event.ctrlKey && key === "l") {
      linkButton.click();
    } else if (event.shiftKey && event.key === "Delete") {
      rippleDeleteButton.click();
    } else if (event.key === "Delete") {
      deleteButton.click();
    } else if (event.key === "Escape" && materialDrag) {
      clearMaterialDrag();
    } else {
      handled = false;
    }
    if (handled) {
      keyboardHandledAt = Date.now();
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  const undoButton = document.getElementById("timelineUndo");
  undoButton.addEventListener("click", () => {
    if (selectedVideo.classList.contains("is-gap-deleted")) {
      selectedVideo.classList.remove("is-gap-deleted");
      linkedAudio.classList.remove("is-gap-deleted");
      selectedLane.classList.remove("has-deleted-gap");
      selectedVideo.classList.add("is-selected");
      showToast("已撤销普通删除", "片段与关联状态已恢复，其他片段位置始终未变。", "success");
    }
  }, true);

  document.querySelectorAll(".timeline-clip").forEach((clip) => {
    clip.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const isLinked = clip.dataset.linked !== "false" && !clip.classList.contains("is-unlinked");
      showModal({
        title: "片段操作",
        text: "右键菜单与工具栏、快捷键调用同一命令入口。",
        detailHtml: `
          <dl class="v195-dialog-summary">
            <div><dt>当前片段</dt><dd>${clip.querySelector("strong")?.textContent || "时间线片段"} · ${isLinked ? "关联编辑" : "独立编辑"}</dd></div>
            <div><dt>普通删除</dt><dd>Delete，保留空隙，不移动其他片段。</dd></div>
            <div><dt>波纹删除</dt><dd>Shift+Delete，先展示完整影响。</dd></div>
            <div><dt>关联操作</dt><dd>Ctrl+L，${isLinked ? "解绑音视频" : "打开严格重新关联候选"}。</dd></div>
          </dl>
        `,
        actions: [
          { label: "取消", contract: "modal.cancel", onClick: closeModal },
          { label: "分割", contract: "timeline.split", onClick: () => { closeModal(); document.getElementById("splitClipAtPlayhead").click(); } },
          { label: isLinked ? "解绑音视频" : "重新关联", contract: isLinked ? "timeline.unlink" : "timeline.relink", onClick: () => { closeModal(); linkButton.click(); } },
          { label: "删除并保留空隙", contract: "timeline.delete-gap", onClick: () => { closeModal(); showDeleteGapDialog(); } },
          { label: "全局波纹删除", contract: "timeline.ripple-delete-v195", onClick: () => { closeModal(); rippleDeleteButton.click(); } },
        ],
      });
      registerV195Contracts(document.getElementById("modalLayer"));
    });
  });

  document.addEventListener("click", (event) => {
    if (Date.now() - keyboardHandledAt < 40) event.stopPropagation();
  }, true);

  setLinkedState(true, "A2");
  updateFrameReadout();
})();

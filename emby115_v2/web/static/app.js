const DEFAULT_PATH_PAIRS = [
  {
    enabled: true,
    name: "movies",
    source: "D:\\115open\\tmp\\origin\\movies",
    target: "C:\\working-emby\\movies",
  },
  {
    enabled: true,
    name: "tvshows",
    source: "D:\\115open\\tmp\\origin\\tvshows",
    target: "C:\\working-emby\\tvshows",
  },
];
const FORM_STORAGE_KEY = "emby115_v2.webui.form.v1";
const METADATA_FORM_STORAGE_KEY = "emby115_v2.webui.metadata.form.v1";
const PENDING_ELEVATED_RUN_KEY = "emby115_v2.webui.pending_elevated_run.v1";
const SYMLINK_ACTIONS = new Set(["build_symlink_workspace", "scan_and_link"]);
const DEFAULT_METADATA_LIBRARIES = [
  { enabled: true, media_type: "movies", library_path: "C:\\working-emby\\movies" },
  { enabled: true, media_type: "tvshows", library_path: "C:\\working-emby\\tvshows" },
];
const MEDIA_TYPE_LABELS = {
  movies: "电影",
  tvshows: "电视剧",
};

const state = {
  busy: false,
  restoring: false,
};

const pathPairs = document.querySelector("#pathPairs");
const outputLog = document.querySelector("#outputLog");
const runButton = document.querySelector("#runButton");
const fullRunButton = document.querySelector("#fullRunButton");
const metadataRunButton = document.querySelector("#metadataRunButton");
const reportLinks = document.querySelector("#reportLinks");
const elevationModal = document.querySelector("#elevationModal");
const restartElevatedButton = document.querySelector("#restartElevatedButton");
const cancelElevationButton = document.querySelector("#cancelElevationButton");

function tokenHeaders() {
  const token = document.querySelector("#accessToken").value.trim();
  return token ? { "X-Access-Token": token } : {};
}

function withToken(url) {
  const token = document.querySelector("#accessToken").value.trim();
  if (!token) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}access_token=${encodeURIComponent(token)}`;
}

function appendLog(message) {
  const time = new Date().toLocaleTimeString();
  outputLog.textContent += `[${time}] ${message}\n`;
  outputLog.scrollTop = outputLog.scrollHeight;
}

function setBusy(busy) {
  state.busy = busy;
  runButton.disabled = busy;
  fullRunButton.disabled = busy;
  metadataRunButton.disabled = busy;
  runButton.textContent = busy ? "执行中" : "执行";
  fullRunButton.textContent = busy ? "执行中" : "执行完整流程";
  metadataRunButton.textContent = busy ? "执行中" : "执行元数据刮削";
}

async function parseJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
}

function showElevationPrompt() {
  elevationModal.classList.remove("hidden");
}

function hideElevationPrompt() {
  elevationModal.classList.add("hidden");
}

function readSavedForm() {
  try {
    const raw = localStorage.getItem(FORM_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

function currentFormConfig() {
  return {
    thread_count: Number(document.querySelector("#threadCount").value || 4),
    path_pairs: collectPathPairRows(),
    report_dir: document.querySelector("#reportDir").value.trim() || "reports",
    log_dir: document.querySelector("#logDir").value.trim() || "logs",
    extensions: document.querySelector("#extensions").value,
    dry_run: document.querySelector("#dryRun").checked,
  };
}

function saveFormConfig() {
  if (state.restoring) return;
  localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(currentFormConfig()));
}

function mediaTypeFromPairName(name) {
  const value = String(name || "").toLowerCase();
  return value === "tv" || value === "tvshow" || value === "tvshows" || value === "series" ? "tvshows" : "movies";
}

function collectPathPairRows() {
  return [...pathPairs.querySelectorAll(".path-row")].map((row) => ({
    enabled: row.querySelector(".pair-enabled").checked,
    name: row.dataset.mediaType,
    source: row.querySelector(".pair-source").value.trim(),
    target: row.querySelector(".pair-target").value.trim(),
  }));
}

function normalizePathPairs(config = {}) {
  const pairs = DEFAULT_PATH_PAIRS.map((pair) => ({ ...pair }));
  const seen = new Set();
  for (const item of config.path_pairs || []) {
    const mediaType = mediaTypeFromPairName(item?.name);
    if (seen.has(mediaType)) continue;
    const pair = pairs.find((entry) => entry.name === mediaType);
    if (!pair) continue;
    seen.add(mediaType);
    pair.enabled = item.enabled ?? true;
    pair.source = typeof item.source === "string" ? item.source : pair.source;
    pair.target = typeof item.target === "string" ? item.target : pair.target;
  }
  return pairs;
}

function applyPathPairs(config = {}) {
  for (const pair of normalizePathPairs(config)) {
    const row = document.querySelector(`.path-row[data-media-type="${pair.name}"]`);
    if (!row) continue;
    row.querySelector(".pair-enabled").checked = pair.enabled ?? true;
    row.querySelector(".pair-source").value = pair.source || "";
    row.querySelector(".pair-target").value = pair.target || "";
  }
}

function readSavedMetadataForm() {
  try {
    const raw = localStorage.getItem(METADATA_FORM_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

function collectMetadataLibraries() {
  return [...document.querySelectorAll(".metadata-library-row")].map((row) => ({
    enabled: row.querySelector(".metadata-library-enabled").checked,
    media_type: row.dataset.mediaType,
    library_path: row.querySelector(".metadata-library-path").value.trim(),
  }));
}

function normalizeMetadataLibraries(config = {}) {
  const output = config.metadata_output || {};
  const libraries = DEFAULT_METADATA_LIBRARIES.map((library) => ({ ...library }));
  if (Array.isArray(config.metadata_libraries)) {
    for (const item of config.metadata_libraries) {
      const mediaType = item?.media_type === "tvshows" ? "tvshows" : item?.media_type === "movies" ? "movies" : "";
      const library = libraries.find((entry) => entry.media_type === mediaType);
      if (!library) continue;
      library.enabled = item.enabled ?? true;
      library.library_path = typeof item.library_path === "string" ? item.library_path : library.library_path;
    }
    return libraries;
  }

  const legacyMediaType = output.media_type === "tvshows" ? "tvshows" : "movies";
  const legacyPath = output.library_path || "";
  if (legacyPath) {
    const library = libraries.find((entry) => entry.media_type === legacyMediaType);
    if (library) library.library_path = legacyPath;
  }
  return libraries;
}

function applyMetadataLibraries(config = {}) {
  for (const library of normalizeMetadataLibraries(config)) {
    const row = document.querySelector(`.metadata-library-row[data-media-type="${library.media_type}"]`);
    if (!row) continue;
    row.querySelector(".metadata-library-enabled").checked = library.enabled ?? true;
    row.querySelector(".metadata-library-path").value = library.library_path || "";
  }
}

function metadataOutputOptionsFromForm(primaryLibrary) {
  return {
    media_type: primaryLibrary?.media_type || "movies",
    library_path: primaryLibrary?.library_path || "",
    write_nfo: true,
    download_images: document.querySelector("#metadataDownloadImages").checked,
    download_episode_thumbs: document.querySelector("#metadataDownloadEpisodeThumbs").checked,
    download_season_posters: false,
    overwrite_existing: document.querySelector("#metadataOverwrite").checked,
    auto_rename: document.querySelector("#metadataAutoRename").checked,
  };
}

function metadataConfigFromForm() {
  const libraries = collectMetadataLibraries();
  const primaryLibrary = libraries.find((library) => library.enabled && library.library_path) || libraries[0];
  return {
    dry_run: document.querySelector("#metadataDryRun").checked,
    tmdb: {
      api_key: document.querySelector("#tmdbApiKey").value,
      language: document.querySelector("#tmdbLanguage").value.trim() || "zh-CN",
      fallback_language: document.querySelector("#tmdbFallbackLanguage").value.trim() || "en-US",
      image_language_priority: document
        .querySelector("#tmdbImageLanguages")
        .value.split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      timeout: Number(document.querySelector("#tmdbTimeout").value || 10),
      rate_limit_per_second: 4,
    },
    llm: {
      enabled: document.querySelector("#llmEnabled").checked,
      provider: document.querySelector("#llmProvider").value,
      base_url: document.querySelector("#llmBaseUrl").value.trim(),
      api_key: document.querySelector("#llmApiKey").value,
      model: document.querySelector("#llmModel").value.trim(),
      temperature: Number(document.querySelector("#llmTemperature").value || 0),
      timeout: Number(document.querySelector("#llmTimeout").value || 30),
      max_candidates_per_decision: 5,
    },
    metadata_libraries: libraries,
    metadata_output: metadataOutputOptionsFromForm(primaryLibrary),
    report: {
      output_dir: document.querySelector("#reportDir").value.trim() || "reports",
    },
    logging: {
      log_dir: document.querySelector("#logDir").value.trim() || "logs",
      log_level: "INFO",
    },
  };
}

function saveMetadataFormConfig() {
  if (state.restoring) return;
  localStorage.setItem(METADATA_FORM_STORAGE_KEY, JSON.stringify(metadataConfigFromForm()));
}

function applyMetadataConfig(config = {}) {
  const tmdb = config.tmdb || {};
  const llm = config.llm || {};
  const output = config.metadata_output || {};
  document.querySelector("#tmdbApiKey").value = tmdb.api_key ?? "";
  document.querySelector("#tmdbLanguage").value = tmdb.language || "zh-CN";
  document.querySelector("#tmdbFallbackLanguage").value = tmdb.fallback_language || "en-US";
  document.querySelector("#tmdbImageLanguages").value = Array.isArray(tmdb.image_language_priority)
    ? tmdb.image_language_priority.join(",")
    : tmdb.image_language_priority || "zh-CN,en-US,null";
  document.querySelector("#tmdbTimeout").value = tmdb.timeout || 10;
  document.querySelector("#llmEnabled").checked = llm.enabled ?? true;
  document.querySelector("#llmProvider").value = llm.provider || "openai_compatible";
  document.querySelector("#llmBaseUrl").value = llm.base_url || "";
  document.querySelector("#llmApiKey").value = llm.api_key || "";
  document.querySelector("#llmModel").value = llm.model || "";
  document.querySelector("#llmTemperature").value = llm.temperature ?? 0;
  document.querySelector("#llmTimeout").value = llm.timeout || 30;
  applyMetadataLibraries(config);
  document.querySelector("#metadataDownloadImages").checked = output.download_images ?? true;
  document.querySelector("#metadataDownloadEpisodeThumbs").checked = output.download_episode_thumbs ?? true;
  document.querySelector("#metadataOverwrite").checked = output.overwrite_existing ?? false;
  document.querySelector("#metadataAutoRename").checked = output.auto_rename ?? true;
}

function restoreFormConfig() {
  const saved = readSavedForm();
  const savedMetadata = readSavedMetadataForm();
  state.restoring = true;
  try {
    document.querySelector("#threadCount").value = saved?.thread_count || 4;
    document.querySelector("#reportDir").value = saved?.report_dir || "reports";
    document.querySelector("#logDir").value = saved?.log_dir || "logs";
    if (saved?.extensions) {
      document.querySelector("#extensions").value = saved.extensions;
    }
    document.querySelector("#dryRun").checked = saved?.dry_run ?? true;
    applyPathPairs(saved || {});
    applyMetadataConfig(savedMetadata || {});
    document.querySelector("#metadataDryRun").checked = savedMetadata?.dry_run ?? true;
  } finally {
    state.restoring = false;
  }
  saveFormConfig();
  saveMetadataFormConfig();
}

function collectPairs() {
  return collectPathPairRows()
    .filter((pair) => pair.enabled)
    .map((pair) => ({
      name: pair.name,
      source: pair.source,
      target: pair.target,
    }))
    .filter((pair) => pair.source && pair.target);
}

function buildPayload() {
  const extensions = document
    .querySelector("#extensions")
    .value.split(";")
    .map((item) => item.trim())
    .filter(Boolean);

  return {
    action: "build_symlink_workspace",
    dry_run: document.querySelector("#dryRun").checked,
    path_pairs: collectPairs(),
    symlink: {
      thread_count: Number(document.querySelector("#threadCount").value || 4),
      video_extensions: extensions,
      report_broken_links: true,
    },
    report: {
      output_dir: document.querySelector("#reportDir").value.trim() || "reports",
    },
    logging: {
      log_dir: document.querySelector("#logDir").value.trim() || "logs",
      log_level: "INFO",
    },
  };
}

async function checkHealth() {
  const dot = document.querySelector("#healthDot");
  const text = document.querySelector("#healthText");
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error(response.statusText);
    dot.className = "status-dot ok";
    text.textContent = "online";
  } catch (error) {
    dot.className = "status-dot error";
    text.textContent = "offline";
  }
}

async function waitForElevatedRestart(timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`/v1/admin/status?ts=${Date.now()}`, {
        cache: "no-store",
        headers: tokenHeaders(),
      });
      const data = await parseJson(response);
      if (response.ok && data.is_admin) {
        return true;
      }
    } catch (error) {
      // The old server exits before the elevated one binds the port.
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
  }
  return false;
}

function pendingSingleRun(payload) {
  return { kind: "single", payload };
}

function metadataLibrariesFromPathPairs(pathPairs) {
  return (pathPairs || [])
    .filter((pair) => pair.name && pair.target)
    .map((pair) => ({
      media_type: pair.name,
      library_path: pair.target,
    }));
}

function pendingFullWorkflow(symlinkPayload) {
  return {
    kind: "full_workflow",
    symlink_payload: symlinkPayload,
    metadata_libraries: metadataLibrariesFromPathPairs(symlinkPayload.path_pairs),
  };
}

function savePendingElevatedRun(run) {
  try {
    sessionStorage.setItem(
      PENDING_ELEVATED_RUN_KEY,
      JSON.stringify({
        run,
        created_at: Date.now(),
      }),
    );
  } catch (error) {
    appendLog("浏览器无法保存待恢复任务；管理员重启后请手动重新点击执行。");
  }
}

function clearPendingElevatedRun() {
  try {
    sessionStorage.removeItem(PENDING_ELEVATED_RUN_KEY);
  } catch (error) {
    // Ignore storage cleanup failures in restricted browser contexts.
  }
}

function readPendingElevatedRun() {
  try {
    const raw = sessionStorage.getItem(PENDING_ELEVATED_RUN_KEY);
    if (!raw) return null;
    const pending = JSON.parse(raw);
    const run = pending?.run || (pending?.payload ? pendingSingleRun(pending.payload) : null);
    if (!run || Date.now() - Number(pending.created_at || 0) > 10 * 60 * 1000) {
      clearPendingElevatedRun();
      return null;
    }
    return run;
  } catch (error) {
    clearPendingElevatedRun();
    return null;
  }
}

async function needsElevation(payload) {
  if (!SYMLINK_ACTIONS.has(payload.action)) return false;
  if (payload.dry_run) return false;
  const response = await fetch("/v1/admin/status", {
    headers: tokenHeaders(),
  });
  const data = await parseJson(response);
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }
  return data.requires_admin_for_symlink && !data.is_admin;
}

async function restartElevated() {
  restartElevatedButton.disabled = true;
  cancelElevationButton.disabled = true;
  appendLog("正在请求以管理员方式重启 WebUI，请在 Windows UAC 中选择同意。");
  try {
    const response = await fetch("/v1/admin/restart-elevated", {
      method: "POST",
      headers: tokenHeaders(),
    });
    const data = await parseJson(response);
    if (!response.ok) {
      throw new Error(data.detail || response.statusText);
    }
    if (data.status === "already_admin") {
      appendLog("当前 WebUI 已经是管理员权限，可以直接执行。");
      hideElevationPrompt();
      await resumePendingElevatedRun();
      return;
    }
    appendLog("已发起管理员重启，正在等待新服务上线。");
    if (await waitForElevatedRestart()) {
      appendLog("管理员 WebUI 已就绪，正在恢复执行。");
      window.location.reload();
      return;
    }
    appendLog("管理员 WebUI 未在预期时间内响应，请确认 UAC 已同意后手动刷新页面。");
  } catch (error) {
    appendLog(`管理员重启失败: ${error.message}`);
  } finally {
    restartElevatedButton.disabled = false;
    cancelElevationButton.disabled = false;
  }
}

async function executePayload(payload, options = {}) {
  const clearReports = options.clearReports ?? true;
  const reportLabel = options.reportLabel || "";
  if (state.busy) return { ok: false, error: "已有任务正在执行" };

  if (SYMLINK_ACTIONS.has(payload.action) && !payload.path_pairs.length) {
    appendLog("请至少勾选一个源目录和目标目录都有效的媒体库。");
    return { ok: false, error: "请至少勾选一个源目录和目标目录都有效的媒体库。" };
  }

  try {
    if (await needsElevation(payload)) {
      appendLog("当前 WebUI 不是管理员权限，真实创建符号链接前需要提权。");
      savePendingElevatedRun(options.pendingRun || pendingSingleRun(payload));
      showElevationPrompt();
      return { ok: false, requiresElevation: true };
    }
  } catch (error) {
    appendLog(`权限状态检查失败: ${error.message}`);
    return { ok: false, error: error.message };
  }

  setBusy(true);
  if (clearReports) {
    reportLinks.innerHTML = "";
  }
  const labelText = reportLabel ? ` (${reportLabel})` : "";
  appendLog(`提交 ${payload.action}${labelText}，dry-run=${payload.dry_run}`);

  try {
    const response = await fetch("/v1/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...tokenHeaders(),
      },
      body: JSON.stringify(payload),
    });
    const data = await parseJson(response);
    if (!response.ok) {
      if (data.requires_elevation) {
        appendLog(data.detail || "需要管理员权限。");
        savePendingElevatedRun(options.pendingRun || pendingSingleRun(payload));
        showElevationPrompt();
        return { ok: false, requiresElevation: true };
      }
      throw new Error(data.detail || response.statusText);
    }

    document.querySelector("#runId").textContent = data.run_id;
    document.querySelector("#actionName").textContent = data.action;
    document.querySelector("#runMode").textContent = data.dry_run ? "dry-run" : "run";
    const result = await streamRunEvents(data, { clearReports, reportLabel });
    appendLog(`执行结束${labelText} run_id=${data.run_id} status=${result.status}`);
    clearPendingElevatedRun();
    return { ok: result.status !== "failed", data: { ...data, ...result } };
  } catch (error) {
    appendLog(`执行失败${labelText}: ${error.message}`);
    return { ok: false, error: error.message };
  } finally {
    setBusy(false);
  }
}

function statusDisplay(status) {
  if (status === "success") return { className: "success", text: "成功" };
  if (status === "partial") return { className: "partial", text: "部分成功" };
  if (status === "failed") return { className: "failed", text: "失败" };
  return { className: "running", text: "执行中" };
}

function appendReportLinks(reports, reportLabel = "", clearReports = false, status = "") {
  const display = statusDisplay(status);
  const reportHtml = `
    <div class="report-link-group">
      <div class="report-link-title">
        ${reportLabel ? `<strong>${reportLabel}</strong>` : ""}
        <span class="result-status ${display.className}">${display.text}</span>
      </div>
      <a href="${withToken(reports.html_url)}" target="_blank" rel="noreferrer">打开 HTML 报告</a>
      <a href="${withToken(reports.json_url)}" target="_blank" rel="noreferrer">打开 JSON 报告</a>
      <span>${reports.html}</span>
      <span>${reports.json}</span>
    </div>
  `;
  if (clearReports) {
    reportLinks.innerHTML = reportHtml;
  } else {
    reportLinks.insertAdjacentHTML("beforeend", reportHtml);
  }
}

function parseEventData(event) {
  try {
    return JSON.parse(event.data || "{}");
  } catch (error) {
    return {};
  }
}

function streamRunEvents(run, options = {}) {
  if (!window.EventSource) {
    return pollRunStatus(run, options);
  }

  return new Promise((resolve, reject) => {
    let finalStatus = run.status || "queued";
    let reportRendered = false;
    const source = new EventSource(withToken(run.events_url || `/v1/runs/${run.run_id}/events`));
    source.addEventListener("status", (event) => {
      const data = parseEventData(event);
      finalStatus = data.status || finalStatus;
      appendLog(`状态更新: ${finalStatus}`);
    });
    source.addEventListener("log", (event) => {
      const data = parseEventData(event);
      if (data.line) appendLog(data.line);
    });
    source.addEventListener("report", (event) => {
      const data = parseEventData(event);
      if (data.reports) {
        appendReportLinks(data.reports, options.reportLabel, options.clearReports && !reportRendered, finalStatus);
        reportRendered = true;
      }
    });
    source.addEventListener("error", (event) => {
      const data = parseEventData(event);
      if (data.error) {
        appendLog(`后台任务错误: ${data.error}`);
        return;
      }
      if (!reportRendered && finalStatus !== "success" && finalStatus !== "partial" && finalStatus !== "failed") {
        source.close();
        reject(new Error("实时日志连接中断"));
      }
    });
    source.addEventListener("done", (event) => {
      const data = parseEventData(event);
      finalStatus = data.status || finalStatus;
      source.close();
      if (reportRendered) {
        updateLastReportStatus(finalStatus);
      }
      resolve({ status: finalStatus });
    });
  });
}

function updateLastReportStatus(status) {
  const groups = reportLinks.querySelectorAll(".report-link-group");
  const lastGroup = groups[groups.length - 1];
  if (!lastGroup) return;
  const badge = lastGroup.querySelector(".result-status");
  if (!badge) return;
  const display = statusDisplay(status);
  badge.className = `result-status ${display.className}`;
  badge.textContent = display.text;
}

async function pollRunStatus(run, options = {}) {
  while (true) {
    const response = await fetch(withToken(run.status_url || `/v1/runs/${run.run_id}`), {
      headers: tokenHeaders(),
    });
    const data = await parseJson(response);
    if (!response.ok) throw new Error(data.detail || response.statusText);
    if (data.status === "success" || data.status === "partial" || data.status === "failed") {
      if (data.reports?.html_url) {
        appendReportLinks(data.reports, options.reportLabel, options.clearReports, data.status);
      }
      if (data.error) appendLog(`后台任务错误: ${data.error}`);
      return { status: data.status };
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
}

async function runWorkflow(event) {
  event.preventDefault();
  await executePayload(buildPayload());
}

function buildMetadataPayload(action = "scrape_metadata", library = null) {
  const config = metadataConfigFromForm();
  const selectedLibrary = library || config.metadata_libraries.find((item) => item.enabled && item.library_path) || config.metadata_libraries[0];
  const metadataOutput = {
    ...config.metadata_output,
    media_type: selectedLibrary?.media_type || "movies",
    library_path: selectedLibrary?.library_path || "",
  };
  return {
    action,
    dry_run: config.dry_run,
    symlink: {
      video_extensions: document
        .querySelector("#extensions")
        .value.split(";")
        .map((item) => item.trim())
        .filter(Boolean),
    },
    ...config,
    metadata_output: metadataOutput,
  };
}

async function runMetadataWorkflow(event) {
  event.preventDefault();
  const libraries = collectMetadataLibraries().filter((library) => library.enabled && library.library_path);
  if (!libraries.length) {
    appendLog("不存在已勾选且路径有效的媒体库。");
    return;
  }

  let successCount = 0;
  let failedCount = 0;
  for (const [index, library] of libraries.entries()) {
    const label = MEDIA_TYPE_LABELS[library.media_type] || library.media_type;
    appendLog(`开始刮削${label}: ${library.library_path}`);
    const result = await executePayload(buildMetadataPayload("scrape_metadata", library), {
      clearReports: index === 0,
      reportLabel: label,
    });
    if (result.ok) {
      successCount += 1;
    } else {
      failedCount += 1;
    }
  }
  appendLog(`元数据刮削队列完成：成功 ${successCount}，失败 ${failedCount}`);
}

async function runFullWorkflow(event) {
  event.preventDefault();
  await runFullWorkflowPayload(buildPayload());
}

async function runFullWorkflowPayload(symlinkPayload, metadataLibraries = null) {
  const pairs = symlinkPayload.path_pairs || [];
  if (!pairs.length) {
    appendLog("请至少勾选一个源目录和目标目录都有效的媒体库。");
    return;
  }

  appendLog("开始完整流程：构建本地软链接工作区 -> 刮削媒体元数据。");
  const symlinkResult = await executePayload(symlinkPayload, {
    clearReports: true,
    reportLabel: "软链接工作区",
    pendingRun: pendingFullWorkflow(symlinkPayload),
  });
  if (symlinkResult.requiresElevation) {
    appendLog("完整流程已暂停：等待管理员权限后恢复软链接步骤。");
    return;
  }
  if (!symlinkResult.ok) {
    appendLog("软链接工作区步骤未成功完成，将继续尝试刮削已勾选目标目录。");
  }

  let successCount = symlinkResult.ok ? 1 : 0;
  let failedCount = symlinkResult.ok ? 0 : 1;
  const libraries = metadataLibraries || metadataLibrariesFromPathPairs(pairs);

  for (const library of libraries) {
    const label = `${MEDIA_TYPE_LABELS[library.media_type] || library.media_type}元数据`;
    appendLog(`完整流程开始${label}: ${library.library_path}`);
    const result = await executePayload(buildMetadataPayload("scrape_metadata", library), {
      clearReports: false,
      reportLabel: label,
    });
    if (result.ok) {
      successCount += 1;
    } else {
      failedCount += 1;
    }
  }

  appendLog(`完整流程结束：成功 ${successCount}，失败 ${failedCount}`);
}

async function testMetadataProvider(action) {
  await executePayload(buildMetadataPayload(action));
}

async function loadMetadataConfigFromServer() {
  try {
    const response = await fetch("/v1/config/metadata", { headers: tokenHeaders() });
    const data = await parseJson(response);
    if (!response.ok) throw new Error(data.detail || response.statusText);
    state.restoring = true;
    try {
      applyMetadataConfig(data.config);
      document.querySelector("#metadataDryRun").checked = true;
    } finally {
      state.restoring = false;
    }
    saveMetadataFormConfig();
    appendLog(`已从本地配置加载: ${data.path}`);
  } catch (error) {
    appendLog(`加载本地配置失败: ${error.message}`);
  }
}

async function saveMetadataConfigToServer() {
  try {
    const response = await fetch("/v1/config/metadata", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...tokenHeaders(),
      },
      body: JSON.stringify({ config: metadataConfigFromForm() }),
    });
    const data = await parseJson(response);
    if (!response.ok) throw new Error(data.detail || response.statusText);
    saveMetadataFormConfig();
    appendLog(`已保存到本地配置: ${data.path}`);
  } catch (error) {
    appendLog(`保存本地配置失败: ${error.message}`);
  }
}

async function resumePendingElevatedRun() {
  const pending = readPendingElevatedRun();
  if (!pending) return;
  const status = await fetch("/v1/admin/status", { headers: tokenHeaders() })
    .then(parseJson)
    .catch(() => ({}));
  if (!status.is_admin) {
    appendLog("检测到待恢复任务，但当前 WebUI 仍不是管理员权限。");
    return;
  }
  if (pending.kind === "full_workflow") {
    appendLog("检测到管理员重启前的完整流程任务，正在继续执行。");
    await runFullWorkflowPayload(pending.symlink_payload, pending.metadata_libraries);
    return;
  }
  appendLog("检测到管理员重启前的待执行任务，正在继续执行。");
  await executePayload(pending.payload);
}

document.querySelector("#runForm").addEventListener("input", saveFormConfig);
document.querySelector("#runForm").addEventListener("change", saveFormConfig);
document.querySelector("#metadataForm").addEventListener("input", saveMetadataFormConfig);
document.querySelector("#metadataForm").addEventListener("change", saveMetadataFormConfig);

document.querySelector("#clearButton").addEventListener("click", () => {
  outputLog.textContent = "";
  reportLinks.innerHTML = "";
  document.querySelector("#runId").textContent = "-";
  document.querySelector("#actionName").textContent = "-";
  document.querySelector("#runMode").textContent = "-";
});

document.querySelector("#runForm").addEventListener("submit", runWorkflow);
document.querySelector("#metadataForm").addEventListener("submit", runMetadataWorkflow);
fullRunButton.addEventListener("click", runFullWorkflow);
document.querySelector("#testTmdbButton").addEventListener("click", () => testMetadataProvider("test_tmdb_config"));
document.querySelector("#testLlmButton").addEventListener("click", () => testMetadataProvider("test_llm_config"));
document.querySelector("#loadMetadataConfigButton").addEventListener("click", loadMetadataConfigFromServer);
document.querySelector("#saveMetadataConfigButton").addEventListener("click", saveMetadataConfigToServer);
restartElevatedButton.addEventListener("click", restartElevated);
cancelElevationButton.addEventListener("click", hideElevationPrompt);

restoreFormConfig();
checkHealth();
resumePendingElevatedRun();

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
const CLOUD_FORM_STORAGE_KEY = "emby115_v2.webui.cloud.form.v1";
const SYMLINK_ACTIONS = new Set(["build_symlink_workspace", "scan_and_link"]);
const DEFAULT_METADATA_LIBRARIES = [
  { enabled: true, media_type: "movies", library_path: "C:\\working-emby\\movies" },
  { enabled: true, media_type: "tvshows", library_path: "C:\\working-emby\\tvshows" },
];
const MEDIA_TYPE_LABELS = {
  movies: "电影",
  tvshows: "电视剧",
};
const DEFAULT_CLOUD_LIBRARIES = [
  {
    enabled: true,
    media_type: "movies",
    source: "C:\\working-emby\\movies",
    target: "D:\\115open\\tmp\\organized\\movies",
  },
  {
    enabled: true,
    media_type: "tvshows",
    source: "C:\\working-emby\\tvshows",
    target: "D:\\115open\\tmp\\organized\\tvshows",
  },
];

const state = {
  busy: false,
  restoring: false,
  fullWorkflowActive: false,
  fullWorkflowCancelRequested: false,
  metadataWorkflowActive: false,
  metadataCancelRequested: false,
  cloudWorkflowActive: false,
  cloudCancelRequested: false,
  activeRunId: "",
  fullFlowLockedInputs: [],
};

const pathPairs = document.querySelector("#pathPairs");
const outputLog = document.querySelector("#outputLog");
const runButton = document.querySelector("#runButton");
const fullRunButton = document.querySelector("#fullRunButton");
const metadataRunButton = document.querySelector("#metadataRunButton");
const cloudRunButton = document.querySelector("#cloudRunButton");
const testCloudDrive2Button = document.querySelector("#testCloudDrive2Button");
const reportLinks = document.querySelector("#reportLinks");

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
  const actionLocked = busy || state.fullWorkflowActive || state.metadataWorkflowActive || state.cloudWorkflowActive;
  runButton.disabled = actionLocked;
  runButton.textContent = busy && !state.fullWorkflowActive && !state.metadataWorkflowActive && !state.cloudWorkflowActive ? "执行中" : "执行";
  if (state.metadataWorkflowActive) {
    metadataRunButton.disabled = state.metadataCancelRequested;
    metadataRunButton.textContent = state.metadataCancelRequested ? "正在取消" : "取消执行";
  } else {
    metadataRunButton.disabled = actionLocked;
    metadataRunButton.textContent = busy ? "执行中" : "执行元数据刮削";
  }
  if (state.cloudWorkflowActive) {
    cloudRunButton.disabled = state.cloudCancelRequested;
    cloudRunButton.textContent = state.cloudCancelRequested ? "正在取消" : "取消执行";
  } else {
    cloudRunButton.disabled = actionLocked;
    cloudRunButton.textContent = busy ? "执行中" : "执行网盘导入";
  }
  testCloudDrive2Button.disabled = actionLocked;
  if (state.fullWorkflowActive) {
    fullRunButton.disabled = state.fullWorkflowCancelRequested;
    fullRunButton.textContent = state.fullWorkflowCancelRequested ? "正在取消" : "取消执行";
  } else {
    fullRunButton.disabled = busy || state.metadataWorkflowActive || state.cloudWorkflowActive;
    fullRunButton.textContent = busy && !state.metadataWorkflowActive && !state.cloudWorkflowActive ? "执行中" : "执行完整流程";
  }
}

function pathPairsByMediaType(pathPairs) {
  return new Map(
    (pathPairs || [])
      .filter((pair) => pair.name && pair.target)
      .map((pair) => [pair.name, pair])
  );
}

function lockInputFromPair(row, inputSelector, pair, label) {
  const input = row.querySelector(inputSelector);
  if (!input || !pair?.target) return;
  const badge = row.querySelector(".full-flow-lock-badge");
  state.fullFlowLockedInputs.push({
    row,
    input,
    badge,
    value: input.value,
    disabled: input.disabled,
    title: input.title,
  });
  row.classList.add("full-flow-locked");
  input.value = pair.target;
  input.disabled = true;
  input.title = `执行完整流程时由“构建本地软链接工作区”的${label}输出接管`;
  if (badge) {
    badge.hidden = false;
  }
}

function lockFullFlowPathInputs(pathPairs) {
  unlockFullFlowPathInputs();
  const pairsByType = pathPairsByMediaType(pathPairs);
  for (const row of document.querySelectorAll(".metadata-library-row")) {
    lockInputFromPair(row, ".metadata-library-path", pairsByType.get(row.dataset.mediaType), "本地 symlink 工作区");
  }
  for (const row of document.querySelectorAll(".cloud-library-row")) {
    lockInputFromPair(row, ".cloud-library-source", pairsByType.get(row.dataset.mediaType), "本地 symlink 工作区");
  }
}

function unlockFullFlowPathInputs() {
  for (const item of state.fullFlowLockedInputs) {
    item.input.value = item.value;
    item.input.disabled = item.disabled;
    item.input.title = item.title;
    item.row.classList.remove("full-flow-locked");
    if (item.badge) {
      item.badge.hidden = true;
    }
  }
  state.fullFlowLockedInputs = [];
}

function requestFullWorkflowCancel() {
  if (!state.fullWorkflowActive || state.fullWorkflowCancelRequested) return;
  state.fullWorkflowCancelRequested = true;
  appendLog("已请求取消完整流程；当前步骤将安全结束，后续步骤不会再启动。");
  setBusy(state.busy);
  cancelActiveRun();
}

function requestMetadataCancel() {
  if (!state.metadataWorkflowActive || state.metadataCancelRequested) return;
  state.metadataCancelRequested = true;
  appendLog("已请求取消元数据刮削；当前后台任务将安全停止，后续媒体库不会再启动。");
  setBusy(state.busy);
  cancelActiveRun();
}

function requestCloudCancel() {
  if (!state.cloudWorkflowActive || state.cloudCancelRequested) return;
  state.cloudCancelRequested = true;
  appendLog("已请求取消网盘导入；当前后台任务将安全停止。");
  setBusy(state.busy);
  cancelActiveRun();
}

async function cancelActiveRun() {
  if (!state.activeRunId) return;
  try {
    const response = await fetch(`/v1/runs/${state.activeRunId}/cancel`, {
      method: "POST",
      headers: tokenHeaders(),
    });
    const data = await parseJson(response);
    if (!response.ok) {
      throw new Error(data.detail || response.statusText);
    }
    if (data.cancel_requested) {
      appendLog(`已通知后台任务取消 run_id=${state.activeRunId}`);
    }
  } catch (error) {
    appendLog(`取消后台任务失败: ${error.message}`);
  }
}

async function parseJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
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
    if (!raw) return null;
    const config = JSON.parse(raw);
    if (Number(config.metadata_form_version || 1) < 2) {
      config.metadata_output = {
        ...(config.metadata_output || {}),
        download_season_posters: true,
      };
      config.metadata_form_version = 2;
    }
    return config;
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
    download_season_posters: document.querySelector("#metadataDownloadSeasonPosters").checked,
    overwrite_existing: document.querySelector("#metadataOverwrite").checked,
    auto_rename: document.querySelector("#metadataAutoRename").checked,
  };
}

function metadataConfigFromForm() {
  const libraries = collectMetadataLibraries();
  const primaryLibrary = libraries.find((library) => library.enabled && library.library_path) || libraries[0];
  return {
    metadata_form_version: 2,
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
  document.querySelector("#metadataDownloadSeasonPosters").checked = output.download_season_posters ?? true;
  document.querySelector("#metadataOverwrite").checked = output.overwrite_existing ?? false;
  document.querySelector("#metadataAutoRename").checked = output.auto_rename ?? true;
}

function readSavedCloudForm() {
  try {
    const raw = localStorage.getItem(CLOUD_FORM_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

function collectCloudLibraries() {
  return [...document.querySelectorAll(".cloud-library-row")].map((row) => ({
    enabled: row.querySelector(".cloud-library-enabled").checked,
    media_type: row.dataset.mediaType,
    source: row.querySelector(".cloud-library-source").value.trim(),
    target: row.querySelector(".cloud-library-target").value.trim(),
  }));
}

function normalizeCloudLibraries(config = {}) {
  const libraries = DEFAULT_CLOUD_LIBRARIES.map((library) => ({ ...library }));
  const sourceRows = Array.isArray(config.cloud_libraries) ? config.cloud_libraries : config.path_pairs || [];
  const seen = new Set();
  for (const item of sourceRows) {
    const mediaType = item?.media_type === "tvshows" ? "tvshows" : mediaTypeFromPairName(item?.name || item?.media_type);
    if (seen.has(mediaType)) continue;
    const library = libraries.find((entry) => entry.media_type === mediaType);
    if (!library) continue;
    seen.add(mediaType);
    library.enabled = item.enabled ?? true;
    library.source = typeof item.source === "string" ? item.source : library.source;
    library.target = typeof item.target === "string" ? item.target : library.target;
  }
  return libraries;
}

function applyCloudConfig(config = {}) {
  const output = config.cloud_library_output || {};
  const cd2 = config.clouddrive2 || {};
  for (const library of normalizeCloudLibraries(config)) {
    const row = document.querySelector(`.cloud-library-row[data-media-type="${library.media_type}"]`);
    if (!row) continue;
    row.querySelector(".cloud-library-enabled").checked = library.enabled ?? true;
    row.querySelector(".cloud-library-source").value = library.source || "";
    row.querySelector(".cloud-library-target").value = library.target || "";
  }
  document.querySelector("#cloudWaitStrategy").value = output.upload_wait_strategy || "fixed";
  document.querySelector("#cloudWaitMinutes").value = output.wait_minutes ?? 60;
  document.querySelector("#cloudMetadataOnly").checked = !(output.move_videos_after_wait ?? false);
  document.querySelector("#cloudOverwriteMetadata").checked = output.overwrite_metadata ?? false;
  document.querySelector("#cloudOverwriteVideos").checked = output.overwrite_videos ?? false;
  document.querySelector("#cloudDryRun").checked = config.dry_run ?? true;
  document.querySelector("#cd2Endpoint").value = cd2.endpoint || "127.0.0.1:19798";
  document.querySelector("#cd2ApiToken").value = cd2.api_token || "";
  document.querySelector("#cd2PollInterval").value = cd2.poll_interval_seconds ?? 0.5;
  document.querySelector("#cd2SettleSeconds").value = cd2.settle_seconds ?? 30;
  document.querySelector("#cd2MaxWaitMinutes").value = cd2.max_wait_minutes ?? 60;
  document.querySelector("#cd2Timeout").value = cd2.timeout ?? 10;
}

function cloudConfigFromForm() {
  return {
    cloud_form_version: 1,
    dry_run: document.querySelector("#cloudDryRun").checked,
    cloud_libraries: collectCloudLibraries(),
    cloud_library_output: {
      wait_minutes: Number(document.querySelector("#cloudWaitMinutes").value || 0),
      move_videos_after_wait: !document.querySelector("#cloudMetadataOnly").checked,
      overwrite_metadata: document.querySelector("#cloudOverwriteMetadata").checked,
      overwrite_videos: document.querySelector("#cloudOverwriteVideos").checked,
      upload_wait_strategy: document.querySelector("#cloudWaitStrategy").value,
    },
    clouddrive2: {
      endpoint: document.querySelector("#cd2Endpoint").value.trim() || "127.0.0.1:19798",
      api_token: document.querySelector("#cd2ApiToken").value,
      timeout: Number(document.querySelector("#cd2Timeout").value || 10),
      poll_interval_seconds: Number(document.querySelector("#cd2PollInterval").value || 0.5),
      settle_seconds: Number(document.querySelector("#cd2SettleSeconds").value || 30),
      max_wait_minutes: Number(document.querySelector("#cd2MaxWaitMinutes").value || 60),
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

function saveCloudFormConfig() {
  if (state.restoring) return;
  localStorage.setItem(CLOUD_FORM_STORAGE_KEY, JSON.stringify(cloudConfigFromForm()));
}

function selectedCloudLibraries() {
  return collectCloudLibraries().filter((library) => library.enabled && library.source && library.target);
}

function buildCloudPayload(action = "build_cloud_scraped_library", libraries = null, dryRunOverride = null) {
  const config = cloudConfigFromForm();
  const selected = libraries || selectedCloudLibraries();
  return {
    action,
    dry_run: dryRunOverride ?? config.dry_run,
    path_pairs: selected.map((library) => ({
      name: library.media_type,
      source: library.source,
      target: library.target,
    })),
    symlink: {
      video_extensions: document
        .querySelector("#extensions")
        .value.split(";")
        .map((item) => item.trim())
        .filter(Boolean),
    },
    cloud_library_output: config.cloud_library_output,
    clouddrive2: config.clouddrive2,
    report: config.report,
    logging: config.logging,
  };
}

function restoreFormConfig() {
  const saved = readSavedForm();
  const savedMetadata = readSavedMetadataForm();
  const savedCloud = readSavedCloudForm();
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
    applyCloudConfig(savedCloud || {});
    document.querySelector("#metadataDryRun").checked = savedMetadata?.dry_run ?? true;
  } finally {
    state.restoring = false;
  }
  saveFormConfig();
  saveMetadataFormConfig();
  saveCloudFormConfig();
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

function metadataLibrariesFromPathPairs(pathPairs) {
  return (pathPairs || [])
    .filter((pair) => pair.name && pair.target)
    .map((pair) => ({
      media_type: pair.name,
      library_path: pair.target,
    }));
}

function cloudLibrariesFromPathPairs(pathPairs) {
  const cloudTargetsByType = new Map(
    collectCloudLibraries()
      .filter((library) => library.enabled && library.target)
      .map((library) => [library.media_type, library.target])
  );
  return (pathPairs || [])
    .filter((pair) => pair.name && pair.target && cloudTargetsByType.has(pair.name))
    .map((pair) => ({
      enabled: true,
      media_type: pair.name,
      source: pair.target,
      target: cloudTargetsByType.get(pair.name),
    }))
    .filter((library) => library.source && library.target);
}

function normalizePathForCompare(value) {
  return (value || "").trim().replace(/[\\/]+$/, "").replace(/\//g, "\\").toLowerCase();
}

function logFullFlowPathSources(pathPairs) {
  const metadataInputsByType = new Map(
    collectMetadataLibraries().map((library) => [library.media_type, library.library_path])
  );
  const cloudInputsByType = new Map(
    collectCloudLibraries().map((library) => [library.media_type, library])
  );

  appendLog("完整流程路径规则：使用上游输出作为下游输入；下游卡片中的输入路径仅用于单独运行。");
  for (const pair of pathPairs || []) {
    if (!pair.name || !pair.target) continue;
    const label = MEDIA_TYPE_LABELS[pair.name] || pair.name;
    const upstreamTarget = pair.target;
    const metadataInput = metadataInputsByType.get(pair.name) || "";
    const cloudInput = cloudInputsByType.get(pair.name) || {};
    const cloudSource = cloudInput.source || "";
    const cloudTarget = cloudInput.target || "";

    appendLog(`完整流程路径链路 ${label}: metadata library_path=${upstreamTarget}; cloud source=${upstreamTarget}; cloud target=${cloudTarget || "未配置网盘目标"}`);
    if (metadataInput && normalizePathForCompare(metadataInput) !== normalizePathForCompare(upstreamTarget)) {
      appendLog(`完整流程已覆盖${label}元数据输入：${metadataInput} -> ${upstreamTarget}`);
    }
    if (cloudSource && normalizePathForCompare(cloudSource) !== normalizePathForCompare(upstreamTarget)) {
      appendLog(`完整流程已覆盖${label}网盘导入 source：${cloudSource} -> ${upstreamTarget}`);
    }
  }
}

function cloudMoveNeedsConfirmation(payload) {
  return Boolean(
    payload
      && payload.action === "build_cloud_scraped_library"
      && !payload.dry_run
      && payload.cloud_library_output?.move_videos_after_wait
      && payload.path_pairs?.length
  );
}

function confirmCloudMoveIfNeeded(payload, libraries) {
  if (!cloudMoveNeedsConfirmation(payload)) return true;
  const lines = (libraries || [])
    .map((library) => `${MEDIA_TYPE_LABELS[library.media_type] || library.media_type}: ${library.source} -> ${library.target}`)
    .join("\n");
  return window.confirm(
    `网盘导入即将开始，将把 symlink 指向的真实视频移动到网盘新媒体库目录。\n\n${lines}\n\n该操作会让当前 C 盘 symlink 工作区中的链接变成过期链接。确认继续吗？`
  );
}

async function needsDeveloperMode(payload) {
  if (!SYMLINK_ACTIONS.has(payload.action)) return false;
  if (payload.dry_run) return false;
  const response = await fetch("/v1/symlink/capability", {
    headers: tokenHeaders(),
  });
  const data = await parseJson(response);
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }
  return data.requires_developer_mode && !data.can_create_symlink;
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
    if (await needsDeveloperMode(payload)) {
      appendLog("当前 Windows 用户无法创建符号链接。请到系统设置中打开开发者模式后重试。");
      return { ok: false, requiresDeveloperMode: true };
    }
  } catch (error) {
    appendLog(`符号链接能力检查失败: ${error.message}`);
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
      if (data.requires_developer_mode) {
        appendLog(data.detail || "请到系统设置中打开开发者模式后重试。");
        return { ok: false, requiresDeveloperMode: true };
      }
      throw new Error(data.detail || response.statusText);
    }

    document.querySelector("#runId").textContent = data.run_id;
    document.querySelector("#actionName").textContent = data.action;
    document.querySelector("#runMode").textContent = data.dry_run ? "dry-run" : "run";
    state.activeRunId = data.run_id;
    if (state.fullWorkflowCancelRequested || state.metadataCancelRequested) {
      await cancelActiveRun();
    }
    const result = await streamRunEvents(data, { clearReports, reportLabel });
    appendLog(`执行结束${labelText} run_id=${data.run_id} status=${result.status}`);
    return { ok: !["failed", "canceled"].includes(result.status), data: { ...data, ...result } };
  } catch (error) {
    appendLog(`执行失败${labelText}: ${error.message}`);
    return { ok: false, error: error.message };
  } finally {
    if (state.activeRunId) {
      state.activeRunId = "";
    }
    setBusy(false);
  }
}

function statusDisplay(status) {
  if (status === "success") return { className: "success", text: "成功" };
  if (status === "partial") return { className: "partial", text: "部分成功" };
  if (status === "failed") return { className: "failed", text: "失败" };
  if (status === "canceled") return { className: "partial", text: "已取消" };
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
      if (!reportRendered && !["success", "partial", "failed", "canceled"].includes(finalStatus)) {
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
    if (data.status === "success" || data.status === "partial" || data.status === "failed" || data.status === "canceled") {
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
  if (state.metadataWorkflowActive) {
    requestMetadataCancel();
    return;
  }
  const libraries = collectMetadataLibraries().filter((library) => library.enabled && library.library_path);
  if (!libraries.length) {
    appendLog("不存在已勾选且路径有效的媒体库。");
    return;
  }

  state.metadataWorkflowActive = true;
  state.metadataCancelRequested = false;
  setBusy(false);
  let successCount = 0;
  let failedCount = 0;
  try {
    for (const [index, library] of libraries.entries()) {
      if (state.metadataCancelRequested) {
        appendLog("元数据刮削已取消：后续媒体库任务不会启动。");
        break;
      }
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
      if (state.metadataCancelRequested) {
        appendLog("元数据刮削已取消：当前后台任务已停止，后续媒体库任务不会启动。");
        break;
      }
    }
    if (state.metadataCancelRequested) {
      appendLog(`元数据刮削队列已取消：已完成成功 ${successCount}，失败 ${failedCount}`);
    } else {
      appendLog(`元数据刮削队列完成：成功 ${successCount}，失败 ${failedCount}`);
    }
  } finally {
    state.metadataWorkflowActive = false;
    state.metadataCancelRequested = false;
    setBusy(false);
  }
}

async function runCloudLibraryWorkflow(event) {
  event.preventDefault();
  if (state.cloudWorkflowActive) {
    requestCloudCancel();
    return;
  }
  const libraries = selectedCloudLibraries();
  if (!libraries.length) {
    appendLog("请至少勾选一个本地 symlink 工作区和网盘目标目录都有效的媒体库。");
    return;
  }
  const payload = buildCloudPayload("build_cloud_scraped_library", libraries);
  if (!confirmCloudMoveIfNeeded(payload, libraries)) {
    appendLog("网盘导入已取消：用户未确认移动真实视频。");
    return;
  }

  state.cloudWorkflowActive = true;
  state.cloudCancelRequested = false;
  setBusy(false);
  try {
    const result = await executePayload(payload, {
      clearReports: true,
      reportLabel: "网盘已刮削媒体库",
    });
    if (state.cloudCancelRequested) {
      appendLog("网盘导入已取消。");
    } else if (result.ok) {
      appendLog("网盘导入完成。");
    } else {
      appendLog("网盘导入未成功完成，请打开报告审核。");
    }
  } finally {
    state.cloudWorkflowActive = false;
    state.cloudCancelRequested = false;
    setBusy(false);
  }
}

async function runCloudDrive2Probe() {
  if (state.cloudWorkflowActive) {
    requestCloudCancel();
    return;
  }
  const libraries = selectedCloudLibraries();
  if (!libraries.length) {
    appendLog("请至少勾选一个本地 symlink 工作区和网盘目标目录都有效的媒体库。");
    return;
  }

  state.cloudWorkflowActive = true;
  state.cloudCancelRequested = false;
  setBusy(false);
  try {
    appendLog("开始 CloudDrive2 上传探测：将写入一个小探测文件并观察挂载上传任务。");
    const result = await executePayload(buildCloudPayload("test_clouddrive2_upload_wait", [libraries[0]], false), {
      clearReports: true,
      reportLabel: "CloudDrive2 上传探测",
    });
    if (state.cloudCancelRequested) {
      appendLog("CloudDrive2 上传探测已取消。");
    } else if (result.ok) {
      appendLog("CloudDrive2 上传探测成功：可以考虑使用 clouddrive2_or_fixed 等待策略。");
    } else {
      appendLog("CloudDrive2 上传探测未成功，请打开报告查看是否未观测到 Mount 上传任务。");
    }
  } finally {
    state.cloudWorkflowActive = false;
    state.cloudCancelRequested = false;
    setBusy(false);
  }
}

async function runFullWorkflow(event) {
  event.preventDefault();
  if (state.fullWorkflowActive) {
    requestFullWorkflowCancel();
    return;
  }
  const symlinkPayload = buildPayload();
  state.fullWorkflowActive = true;
  state.fullWorkflowCancelRequested = false;
  lockFullFlowPathInputs(symlinkPayload.path_pairs);
  setBusy(false);
  try {
    await runFullWorkflowPayload(symlinkPayload);
  } finally {
    state.fullWorkflowActive = false;
    state.fullWorkflowCancelRequested = false;
    unlockFullFlowPathInputs();
    setBusy(false);
  }
}

async function runFullWorkflowPayload(symlinkPayload, metadataLibraries = null) {
  const pairs = symlinkPayload.path_pairs || [];
  if (!pairs.length) {
    appendLog("请至少勾选一个源目录和目标目录都有效的媒体库。");
    return;
  }

  appendLog("开始完整流程：构建本地软链接工作区 -> 刮削媒体元数据 -> 构建网盘已刮削媒体库。");
  logFullFlowPathSources(pairs);
  const symlinkResult = await executePayload(symlinkPayload, {
    clearReports: true,
    reportLabel: "软链接工作区",
  });
  if (symlinkResult.requiresDeveloperMode) {
    appendLog("完整流程已暂停：请到系统设置中打开开发者模式后重新执行。");
    return;
  }
  if (state.fullWorkflowCancelRequested) {
    appendLog("完整流程已取消：已停止启动后续元数据刮削步骤。");
    return;
  }
  if (!symlinkResult.ok) {
    appendLog("软链接工作区步骤未成功完成，完整流程已停止；请先处理报告中的前置条件问题。");
    return;
  }

  let successCount = symlinkResult.ok ? 1 : 0;
  let failedCount = symlinkResult.ok ? 0 : 1;
  let skippedCount = 0;
  const libraries = metadataLibraries || metadataLibrariesFromPathPairs(pairs);

  for (const library of libraries) {
    if (state.fullWorkflowCancelRequested) {
      appendLog("完整流程已取消：已停止启动后续媒体库任务。");
      break;
    }
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

  if (!state.fullWorkflowCancelRequested) {
    const cloudLibraries = cloudLibrariesFromPathPairs(pairs);
    if (!cloudLibraries.length) {
      skippedCount += 1;
      appendLog("完整流程跳过网盘导入：网盘导入卡片中没有勾选且目标路径有效的对应媒体库。");
    } else {
      const cloudPayload = buildCloudPayload("build_cloud_scraped_library", cloudLibraries);
      if (state.fullWorkflowCancelRequested) {
        appendLog("完整流程已取消：已停止启动网盘导入。");
      } else {
        appendLog("完整流程开始网盘导入：自动进入第三阶段，复制已刮削元数据并移动真实视频。");
        const result = await executePayload(cloudPayload, {
          clearReports: false,
          reportLabel: "网盘已刮削媒体库",
        });
        if (result.ok) {
          successCount += 1;
        } else {
          failedCount += 1;
        }
      }
    }
  }

  if (state.fullWorkflowCancelRequested) {
    appendLog(`完整流程已取消：已完成步骤成功 ${successCount}，失败 ${failedCount}，跳过 ${skippedCount}`);
  } else {
    appendLog(`完整流程结束：成功 ${successCount}，失败 ${failedCount}，跳过 ${skippedCount}`);
  }
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
      applyCloudConfig(data.config);
      document.querySelector("#metadataDryRun").checked = true;
    } finally {
      state.restoring = false;
    }
    saveMetadataFormConfig();
    saveCloudFormConfig();
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
      body: JSON.stringify({ config: { ...metadataConfigFromForm(), ...cloudConfigFromForm() } }),
    });
    const data = await parseJson(response);
    if (!response.ok) throw new Error(data.detail || response.statusText);
    saveMetadataFormConfig();
    saveCloudFormConfig();
    appendLog(`已保存到本地配置: ${data.path}`);
  } catch (error) {
    appendLog(`保存本地配置失败: ${error.message}`);
  }
}

document.querySelector("#runForm").addEventListener("input", saveFormConfig);
document.querySelector("#runForm").addEventListener("change", saveFormConfig);
document.querySelector("#metadataForm").addEventListener("input", saveMetadataFormConfig);
document.querySelector("#metadataForm").addEventListener("change", saveMetadataFormConfig);
document.querySelector("#cloudLibraryForm").addEventListener("input", saveCloudFormConfig);
document.querySelector("#cloudLibraryForm").addEventListener("change", saveCloudFormConfig);

document.querySelector("#clearButton").addEventListener("click", () => {
  outputLog.textContent = "";
  reportLinks.innerHTML = "";
  document.querySelector("#runId").textContent = "-";
  document.querySelector("#actionName").textContent = "-";
  document.querySelector("#runMode").textContent = "-";
});

document.querySelector("#runForm").addEventListener("submit", runWorkflow);
document.querySelector("#metadataForm").addEventListener("submit", runMetadataWorkflow);
document.querySelector("#cloudLibraryForm").addEventListener("submit", runCloudLibraryWorkflow);
fullRunButton.addEventListener("click", runFullWorkflow);
testCloudDrive2Button.addEventListener("click", runCloudDrive2Probe);
document.querySelector("#testTmdbButton").addEventListener("click", () => testMetadataProvider("test_tmdb_config"));
document.querySelector("#testLlmButton").addEventListener("click", () => testMetadataProvider("test_llm_config"));
document.querySelector("#loadMetadataConfigButton").addEventListener("click", loadMetadataConfigFromServer);
document.querySelector("#saveMetadataConfigButton").addEventListener("click", saveMetadataConfigToServer);

restoreFormConfig();
checkHealth();

const DEFAULT_PAIR = {
  name: "movies",
  source: "D:\\115open\\tmp\\origin\\movies",
  target: "C:\\working-emby\\movies",
};
const FORM_STORAGE_KEY = "emby115_v2.webui.form.v1";
const PENDING_ELEVATED_RUN_KEY = "emby115_v2.webui.pending_elevated_run.v1";

const state = {
  busy: false,
  restoring: false,
};

const pathPairs = document.querySelector("#pathPairs");
const outputLog = document.querySelector("#outputLog");
const runButton = document.querySelector("#runButton");
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
  runButton.textContent = busy ? "执行中" : "执行";
}

function escapeAttribute(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
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
    path_pairs: collectPairs(),
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

function restoreFormConfig() {
  const saved = readSavedForm();
  const pairs = saved?.path_pairs?.length ? saved.path_pairs : [DEFAULT_PAIR];
  state.restoring = true;
  try {
    pathPairs.innerHTML = "";
    document.querySelector("#threadCount").value = saved?.thread_count || 4;
    document.querySelector("#reportDir").value = saved?.report_dir || "reports";
    document.querySelector("#logDir").value = saved?.log_dir || "logs";
    if (saved?.extensions) {
      document.querySelector("#extensions").value = saved.extensions;
    }
    document.querySelector("#dryRun").checked = saved?.dry_run ?? true;
    pairs.forEach((pair) => addPair(pair));
  } finally {
    state.restoring = false;
  }
  saveFormConfig();
}

function addPair(pair = {}) {
  const row = document.createElement("div");
  const groupName = `media-type-${Date.now()}-${pathPairs.children.length}`;
  const mediaType = pair.name === "tvshows" ? "tvshows" : "movies";
  row.className = "path-row";
  row.innerHTML = `
    <div class="media-type-group" role="radiogroup" aria-label="媒体类型">
      <label class="radio-pill">
        <input class="pair-media-type" type="radio" name="${groupName}" value="movies" ${mediaType === "movies" ? "checked" : ""}>
        电影
      </label>
      <label class="radio-pill">
        <input class="pair-media-type" type="radio" name="${groupName}" value="tvshows" ${mediaType === "tvshows" ? "checked" : ""}>
        电视剧
      </label>
    </div>
    <input class="pair-source" value="${escapeAttribute(pair.source)}" placeholder="D:\\115open\\tmp\\origin\\movies">
    <input class="pair-target" value="${escapeAttribute(pair.target)}" placeholder="C:\\working-emby\\movies">
    <button type="button" class="remove-button">移除</button>
  `;
  row.querySelector(".remove-button").addEventListener("click", () => {
    if (pathPairs.children.length > 1) {
      row.remove();
      saveFormConfig();
    }
  });
  pathPairs.appendChild(row);
  saveFormConfig();
}

function collectPairs() {
  return [...pathPairs.querySelectorAll(".path-row")]
    .map((row, index) => ({
      name: row.querySelector(".pair-media-type:checked")?.value || `pair_${index + 1}`,
      source: row.querySelector(".pair-source").value.trim(),
      target: row.querySelector(".pair-target").value.trim(),
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

function savePendingElevatedRun(payload) {
  try {
    sessionStorage.setItem(
      PENDING_ELEVATED_RUN_KEY,
      JSON.stringify({
        payload,
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
    if (!pending?.payload || Date.now() - Number(pending.created_at || 0) > 10 * 60 * 1000) {
      clearPendingElevatedRun();
      return null;
    }
    return pending.payload;
  } catch (error) {
    clearPendingElevatedRun();
    return null;
  }
}

async function needsElevation(payload) {
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

async function executePayload(payload) {
  if (state.busy) return;

  if (!payload.path_pairs.length) {
    appendLog("请至少填写一个有效的源目录和目标目录。");
    return;
  }

  try {
    if (await needsElevation(payload)) {
      appendLog("当前 WebUI 不是管理员权限，真实创建符号链接前需要提权。");
      savePendingElevatedRun(payload);
      showElevationPrompt();
      return;
    }
  } catch (error) {
    appendLog(`权限状态检查失败: ${error.message}`);
    return;
  }

  setBusy(true);
  reportLinks.innerHTML = "";
  appendLog(`提交 ${payload.action}，dry-run=${payload.dry_run}`);

  try {
    const response = await fetch("/v1/run", {
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
        savePendingElevatedRun(payload);
        showElevationPrompt();
        return;
      }
      throw new Error(data.detail || response.statusText);
    }

    document.querySelector("#runId").textContent = data.run_id;
    document.querySelector("#actionName").textContent = data.action;
    document.querySelector("#runMode").textContent = data.dry_run ? "dry-run" : "run";
    reportLinks.innerHTML = `
      <a href="${withToken(data.reports.html_url)}" target="_blank" rel="noreferrer">打开 HTML 报告</a>
      <a href="${withToken(data.reports.json_url)}" target="_blank" rel="noreferrer">打开 JSON 报告</a>
      <span>${data.reports.html}</span>
      <span>${data.reports.json}</span>
    `;
    appendLog(`执行完成 run_id=${data.run_id}`);
    clearPendingElevatedRun();
  } catch (error) {
    appendLog(`执行失败: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

async function runWorkflow(event) {
  event.preventDefault();
  await executePayload(buildPayload());
}

async function resumePendingElevatedRun() {
  const payload = readPendingElevatedRun();
  if (!payload) return;
  const status = await fetch("/v1/admin/status", { headers: tokenHeaders() })
    .then(parseJson)
    .catch(() => ({}));
  if (!status.is_admin) {
    appendLog("检测到待恢复任务，但当前 WebUI 仍不是管理员权限。");
    return;
  }
  appendLog("检测到管理员重启前的待执行任务，正在继续执行。");
  await executePayload(payload);
}

document.querySelector("#addPairButton").addEventListener("click", () => addPair({
  name: "tvshows",
  source: "D:\\115open\\tmp\\origin\\tvshows",
  target: "C:\\working-emby\\tvshows",
}));

document.querySelector("#runForm").addEventListener("input", saveFormConfig);
document.querySelector("#runForm").addEventListener("change", saveFormConfig);

document.querySelector("#clearButton").addEventListener("click", () => {
  outputLog.textContent = "";
  reportLinks.innerHTML = "";
  document.querySelector("#runId").textContent = "-";
  document.querySelector("#actionName").textContent = "-";
  document.querySelector("#runMode").textContent = "-";
});

document.querySelector("#runForm").addEventListener("submit", runWorkflow);
restartElevatedButton.addEventListener("click", restartElevated);
cancelElevationButton.addEventListener("click", hideElevationPrompt);

restoreFormConfig();
checkHealth();
resumePendingElevatedRun();

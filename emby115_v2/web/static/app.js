const DEFAULT_PAIR = {
  name: "movies",
  source: "D:\\115open\\tmp\\origin\\movies",
  target: "C:\\working-emby\\movies",
};

const state = {
  busy: false,
};

const pathPairs = document.querySelector("#pathPairs");
const outputLog = document.querySelector("#outputLog");
const runButton = document.querySelector("#runButton");
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
  runButton.disabled = busy;
  runButton.textContent = busy ? "执行中" : "执行";
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
    <input class="pair-source" value="${pair.source || ""}" placeholder="D:\\115open\\tmp\\origin\\movies">
    <input class="pair-target" value="${pair.target || ""}" placeholder="C:\\working-emby\\movies">
    <button type="button" class="remove-button">移除</button>
  `;
  row.querySelector(".remove-button").addEventListener("click", () => {
    if (pathPairs.children.length > 1) {
      row.remove();
    }
  });
  pathPairs.appendChild(row);
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

async function runWorkflow(event) {
  event.preventDefault();
  if (state.busy) return;

  const payload = buildPayload();
  if (!payload.path_pairs.length) {
    appendLog("请至少填写一个有效的源目录和目标目录。");
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
    const data = await response.json();
    if (!response.ok) {
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
  } catch (error) {
    appendLog(`执行失败: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

document.querySelector("#addPairButton").addEventListener("click", () => addPair({
  name: "tvshows",
  source: "D:\\115open\\tmp\\origin\\tvshows",
  target: "C:\\working-emby\\tvshows",
}));

document.querySelector("#clearButton").addEventListener("click", () => {
  outputLog.textContent = "";
  reportLinks.innerHTML = "";
  document.querySelector("#runId").textContent = "-";
  document.querySelector("#actionName").textContent = "-";
  document.querySelector("#runMode").textContent = "-";
});

document.querySelector("#runForm").addEventListener("submit", runWorkflow);

addPair(DEFAULT_PAIR);
checkHealth();

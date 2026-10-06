// 通用 utils - 所有頁面共用

const API_BASE = "";

/**
 * 統一 API 呼叫 wrapper
 * - JSON header 自動加
 * - 錯誤統一 throw Error(detail)
 * @param {string} path - API path (e.g. '/matchings/1')
 * @param {object} options - fetch options (method / body / headers)
 * @returns {Promise<object>} response JSON
 */
async function apiCall(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const errMsg = data.detail || `HTTP ${res.status}`;
    throw new Error(
      typeof errMsg === "string" ? errMsg : JSON.stringify(errMsg)
    );
  }

  return data;
}

/**
 * Toast 訊息 (右下角浮出 3 秒)
 * @param {string} msg
 * @param {'success'|'error'|'info'} type
 */
function showToast(msg, type = "info") {
  const colors = {
    success: "bg-green-500",
    error: "bg-red-500",
    info: "bg-blue-500",
  };

  const toast = document.createElement("div");
  toast.className = `fixed bottom-6 right-6 px-4 py-3 rounded-lg text-white shadow-lg z-50 transition-opacity ${colors[type]}`;
  toast.textContent = msg;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/**
 * Loading state (spinner + 語意化文字)
 * @param {HTMLElement} el
 * @param {string} msg - 語意化提示, e.g. "AI 正在比對您的核心技能..."
 */
function showLoading(el, msg = "載入中...") {
  el.innerHTML = `
    <div class="flex items-center justify-center py-12 gap-3 text-gray-500">
      <svg class="animate-spin h-6 w-6" viewBox="0 0 24 24" fill="none">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      <span>${msg}</span>
    </div>
  `;
}

/**
 * Error state (紅色卡片 + 選擇性 retry 按鈕)
 * @param {HTMLElement} el
 * @param {string} msg
 * @param {function|null} retryFn - 若給, render 重試按鈕
 */
function showError(el, msg, retryFn = null) {
  el.innerHTML = `
    <div class="bg-red-50 border border-red-200 rounded-lg p-6">
      <div class="flex items-start gap-3">
        <span class="text-2xl">⚠️</span>
        <div class="flex-1">
          <p class="text-red-700 font-medium">${msg}</p>
          ${
            retryFn
              ? '<button id="retry-btn" class="mt-3 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm">點我重試</button>'
              : ""
          }
        </div>
      </div>
    </div>
  `;
  if (retryFn) {
    document.getElementById("retry-btn").addEventListener("click", retryFn);
  }
}

/**
 * 複製到剪貼簿 + Toast 反饋
 * @param {string} text
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showToast("已複製到剪貼簿！", "success");
  } catch (e) {
    showToast("複製失敗, 請手動選取", "error");
    console.error("Clipboard error:", e);
  }
}

/**
 * 從 URL query params 取值
 * @param {string} key
 * @returns {string|null}
 */
function getQueryParam(key) {
  return new URLSearchParams(window.location.search).get(key);
}


/**
 * HTML escape - 防 XSS
 * 任何從 backend fetch 的 dynamic string render 到 innerHTML 前一律 wrap
 * @param {string|null|undefined} str
 * @returns {string}
 */

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// 只記住本次頁面已建立的紀錄，避免成功後再次點擊；跨頁防重需由後端處理。
const createdTrackingKeys = new Set();

function renderTrackingEntry(matchingId, letterId = null, version = null) {
  const created = createdTrackingKeys.has(`${matchingId}:${letterId}`);
  return `<div class="shrink-0 sm:text-right" aria-label="加入求職追蹤">
    <div class="flex flex-wrap items-center gap-3 sm:justify-end">
      <span class="text-xs text-gray-500">${letterId === null ? "未選用求職信" : `使用 v${escapeHtml(version)}`}</span>
      <button id="add-tracking" type="button" ${created ? "disabled" : ""} class="inline-flex items-center justify-center rounded-lg border border-indigo-200 bg-white px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-default">${created ? "✓ 已加入追蹤" : "＋ 加入追蹤"}</button>
    </div>
    <p id="tracking-feedback" role="status" class="text-xs text-gray-600 mt-2 max-w-sm empty:hidden"></p>
  </div>`;
}

function bindTrackingEntry(matchingId, letterId = null, options = {}) {
  const button = document.getElementById("add-tracking");
  const feedback = document.getElementById("tracking-feedback");
  const key = `${matchingId}:${letterId}`;
  let pending = false;
  button.addEventListener("click", async () => {
    if (pending || createdTrackingKeys.has(key)) return;
    const reason = options.blockReason?.();
    if (reason) { feedback.textContent = reason; return; }
    pending = true;
    button.disabled = true;
    button.textContent = "建立中…";
    feedback.textContent = "";
    options.setBusy?.(true);
    try {
      // 履歷與職缺由後端依 matching 查出，不另外由前端傳入。
      const result = await apiCall("/applications", {
        method: "POST",
        body: JSON.stringify({matching_id: Number(matchingId), cover_letter_id: letterId}),
      });
      createdTrackingKeys.add(key);
      feedback.textContent = `已建立追蹤紀錄 #${result.data.id}，狀態為準備中。`;
    } catch (error) {
      feedback.textContent = `無法確認是否建立成功：${error.message}。請先查看求職追蹤，再決定是否重試。`;
    } finally {
      pending = false;
      options.setBusy?.(false);
      const created = createdTrackingKeys.has(key);
      button.disabled = created;
      button.textContent = created ? "✓ 已加入追蹤" : "＋ 加入追蹤";
    }
  });
}

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

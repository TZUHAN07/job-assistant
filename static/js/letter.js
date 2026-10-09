let allVersions = [];
let currentIdx = 0;
let matchingId = null;
let matchingInfo = null;
let draft = null;
let originalDraft = "";
let isSaving = false;
const sectionNames = {opening: "開場", why_me: "為何選我", why_company: "為何貴公司", call_to_action: "結尾與邀約"};

function isDirty() { return draft !== null && JSON.stringify(draft) !== originalDraft; }
function canLeaveDraft() { return !isSaving && (!isDirty() || window.confirm("尚有未儲存的修改，要放棄嗎？")); }
function draftContent() {
  if (!isDirty()) return allVersions[currentIdx].content;
  return draft.sections ? Object.values(draft.sections).join("\n\n") : draft.content; }
window.addEventListener("beforeunload", event => {
  if (isDirty() || isSaving) { event.preventDefault(); event.returnValue = ""; }
});
document.addEventListener("click", event => {
  if (event.target.closest("a[href]") && !canLeaveDraft()) event.preventDefault();
});

(async function main() {
  matchingId = getQueryParam("matching_id");
  if (!matchingId) {
    showError(document.getElementById("content"), "URL 缺少 matching_id 參數");
    return;
  }

  await loadVersions();
})();

async function loadVersions() {
  const contentEl = document.getElementById("content");
  showLoading(contentEl, "正在載入求職信...");

  try {
    const [lettersRes, matchingRes] = await Promise.all([
      apiCall(`/cover-letters?matching_id=${matchingId}`),
      apiCall(`/matchings/${matchingId}`),
    ]);

    allVersions = lettersRes.data;
    matchingInfo = matchingRes.data;

    
    const requestedId = getQueryParam("cover_letter_id");
    currentIdx = requestedId === null
      ? 0
      : allVersions.findIndex(letter => String(letter.id) === requestedId);

    renderHeader();
    if (currentIdx === -1) {
      showError(contentEl, "找不到這筆紀錄選用的求職信，請返回求職追蹤確認。", loadVersions);
      return;
    }
    if (allVersions.length === 0) {
      renderEmptyState();
    } else {
      renderFullPage();
    }
  } catch (e) {
    showError(contentEl, `載入失敗: ${e.message}`, loadVersions);
  }
}

function renderEmptyState() {
  const contentEl = document.getElementById("content");
  contentEl.innerHTML = `
    <div class="bg-white rounded-lg shadow p-12 text-center">
      <p class="text-gray-600 text-lg mb-6">尚未生成求職信</p>
      <button id="generate-first" class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-lg">
        生成第一版求職信
      </button>
    </div>
  `;
  document
    .getElementById("generate-first")
    .addEventListener("click", handleRegenerate);
}

function renderFullPage() {
  const contentEl = document.getElementById("content");
  const current = allVersions[currentIdx];

  const sections = current.sections;
  const hasSections = Object.keys(sectionNames).every(key => typeof sections?.[key] === "string");
  draft = hasSections
    ? {sections: Object.fromEntries(Object.keys(sectionNames).map(key => [key, sections[key]]))}
    : {content: current.content};
  originalDraft = JSON.stringify(draft);
  contentEl.innerHTML = `
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
      <h2 class="text-lg font-semibold text-gray-800">目前版本 <span class="ml-1 text-indigo-700">v${escapeHtml(current.version)}</span></h2>
      ${renderTrackingEntry(matchingId, current.id, current.version)}
    </div>
    ${renderVersionTabs()}
    ${renderControlPanel(current)}
    ${renderSplitView(current)}
  `;

  attachEventListeners();
  let lockedControls = [];
  bindTrackingEntry(matchingId, current.id, {
    blockReason: () => isSaving ? "正在處理，請稍候。" : isDirty() ? "請先將修改儲存為新版本，再使用該版本加入追蹤。" : "",
    setBusy: busy => {
      isSaving = busy;
      if (busy) {
        lockedControls = [...contentEl.querySelectorAll("button, textarea, select")]
          .filter(el => el.id !== "add-tracking")
          .map(el => [el, el.disabled]);
        lockedControls.forEach(([el]) => { el.disabled = true; });
      } else {
        lockedControls.forEach(([el, disabled]) => { el.disabled = disabled; });
      }
    },
  });
  contentEl.querySelectorAll("textarea[data-field]").forEach(input => {
    input.addEventListener("input", () => {
      if (draft.sections) draft.sections[input.dataset.field] = input.value;
      else draft.content = input.value;
      document.getElementById("letter-preview").textContent = draftContent();
      document.getElementById("save-edit").disabled = !isDirty();
      document.getElementById("edit-feedback").textContent = isDirty() ? "尚未儲存" : "";
    });
  });
  document.getElementById("save-edit").addEventListener("click", saveEditedVersion);
  document.getElementById("reset-edit").addEventListener("click", () => {
    if (canLeaveDraft()) renderFullPage();
  });
}

function attachEventListeners() {
  document.querySelectorAll(".version-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      if (!canLeaveDraft()) return;
      currentIdx = parseInt(tab.dataset.idx);
      renderFullPage();
    });
  });

  document
    .getElementById("regenerate-btn")
    ?.addEventListener("click", handleRegenerate);

  document.getElementById("copy-btn")?.addEventListener("click", () => {
    copyToClipboard(draftContent());
  });
}

async function handleRegenerate() {
  if (!canLeaveDraft()) return;
  const toneEl = document.getElementById("tone-select");
  const langEl = document.getElementById("language-select");
  const tone = toneEl?.value || "formal";
  const language = langEl?.value || "zh-TW";

  const contentEl = document.getElementById("content");
  showLoading(contentEl, "AI 正在為您撰寫求職信... (約 5-10 秒)");

  try {
    const res = await apiCall("/cover-letters/generate", {
      method: "POST",
      body: JSON.stringify({
        matching_id: parseInt(matchingId),
        tone,
        language,
      }),
    });
    
    allVersions.unshift(res.data);
    currentIdx = 0;
    renderFullPage();
    showToast(`已生成 v${res.data.version}!`, "success");
  } catch (e) {
    showError(contentEl, `生成失敗: ${e.message}`, () => renderFullPage());
  }
}

function renderHeader() {
  const headerEl = document.getElementById("header");
  if (!headerEl) return;

  const jobInfo = matchingInfo
    ? `${matchingInfo.job_company || ""} · ${matchingInfo.job_title || ""}`
    : "";

   headerEl.innerHTML = `
    <div class="py-4 border-b border-gray-200">
      <div class="flex items-center justify-between gap-4">
        <h1 class="text-2xl font-bold text-gray-800">求職信工作室</h1>
        <a href="applications.html" class="shrink-0 text-sm text-gray-500 hover:text-indigo-700 hover:underline rounded focus:ring-2 focus:ring-indigo-500">求職追蹤 →</a>
      </div>
      <p class="text-sm text-gray-500 mt-2 break-words">${escapeHtml(jobInfo)}</p>
      <nav aria-label="求職信導覽" class="flex flex-wrap items-center gap-5 mt-5 text-sm">
        <a href="matching.html?id=${encodeURIComponent(matchingId)}" class="text-indigo-700 hover:underline">← 匹配結果</a>
        <a href="index.html" class="text-gray-500 hover:text-gray-800 hover:underline">選擇其他職缺</a>
      </nav>
    </div>`;
}

function renderVersionTabs() {
  if (!allVersions || allVersions.length === 0) return "";

  return `
    <div class="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
    <span class="text-xs font-semibold text-gray-400 mr-2 shrink-0">歷史版本：</span>
      ${allVersions
        .map(
          (letter, i) => `
        <button 
          type="button"
          class="version-tab px-4 py-2 rounded-lg text-sm font-medium transition shrink-0 ${
            i === currentIdx
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }" 
          data-idx="${i}">
          v${letter.version}${i === 0 ? " (最新)" : ""}
        </button>
      `,
        )
        .join("")}
    </div>
  `;
}

function renderControlPanel(letter) {
  const tones = [
    { value: "professional", label: "專業 (Professional)" },
    { value: "casual", label: "輕鬆 (Casual)" },
    { value: "formal", label: "正式 (Formal)" },
    { value: "enthusiastic", label: "熱情 (Enthusiastic)" },
  ];

  const languages = [
    { value: "zh-TW", label: "繁體中文" },
    { value: "en-US", label: "英文" },
  ];

  return `
    <div class="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap items-center gap-4">
      <!-- Tone -->
      <div class="flex items-center gap-2">
        <label class="text-sm font-medium text-gray-600">語氣</label>
        <select id="tone-select" class="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
          ${tones
            .map(
              (t) => `
            <option value="${t.value}" ${letter.tone === t.value ? "selected" : ""}>${t.label}</option>
          `,
            )
            .join("")}
        </select>
      </div>

      <!-- Language -->
      <div class="flex items-center gap-2">
        <label class="text-sm font-medium text-gray-600">語言</label>
        <select id="language-select" class="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
          ${languages
            .map(
              (l) => `
            <option value="${l.value}" ${letter.language === l.value ? "selected" : ""}>${l.label}</option>
          `,
            )
            .join("")}
        </select>
      </div>

      <!-- Regenerate -->
      <button id="regenerate-btn" class="ml-auto inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-5 py-2 rounded-lg transition shadow-sm hover:shadow">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        重新生成新版本
      </button>
    </div>
  `;
}

function renderSplitView(letter) {
  const fields = draft.sections || {content: draft.content};
  return `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div class="space-y-4">
        <h2 class="font-bold">${draft.sections ? "編輯四個段落" : "編輯全文"}</h2>
        ${draft.sections ? '<p class="text-sm text-gray-500">修改後，預覽會依四段重新組合；請將需要的稱呼與署名保留在開場及結尾。</p>' : ""}
        ${draft.sections ? "" : '<p class="text-sm text-gray-500">此版本只有完整內容，沒有分段資料，可直接編輯全文。</p>'}
        ${Object.entries(fields).map(([key, value]) => `
          <div class="bg-white rounded-lg shadow p-4">
            <label for="edit-${key}" class="block font-semibold mb-2">${sectionNames[key] || "完整內容"}</label>
            <textarea id="edit-${key}" data-field="${key}" rows="${key === "content" ? 18 : 6}" class="w-full border rounded-lg p-3 text-sm focus:ring-2 focus:ring-indigo-500">${escapeHtml(value)}</textarea>
          </div>`).join("")}
        <div class="flex gap-3">
          <button id="save-edit" disabled class="bg-indigo-600 text-white rounded-lg px-4 py-2 disabled:opacity-50">儲存為新版本</button>
          <button id="reset-edit" class="border rounded-lg px-4 py-2">還原修改</button>
        </div>
        <p class="text-xs text-gray-500">儲存會新增版本，不會變更追蹤紀錄選用的求職信。</p>
        <p id="edit-feedback" role="status" class="text-sm text-gray-600"></p>
      </div>
      <div class="bg-white rounded-lg shadow p-6 h-fit md:sticky md:top-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="font-bold">完整預覽</h2>
          <button id="copy-btn" class="bg-indigo-600 text-white rounded-lg px-4 py-2">複製全文</button>
        </div>
        <div id="letter-preview" class="whitespace-pre-wrap break-words text-sm max-h-[600px] overflow-y-auto">${escapeHtml(draftContent())}</div>
      </div>
    </div>`;
}

async function saveEditedVersion() {
  if (isSaving || !isDirty()) return;
  const fields = draft.sections || {content: draft.content};
  if (Object.values(fields).some(value => !value.trim() || value.trim().length > 30000)) {
    document.getElementById("edit-feedback").textContent = "每個欄位需填寫內容，且不可超過 30,000 字。";
    return;
  }
  isSaving = true;
  const controls = [...document.querySelectorAll("#content button, #content textarea, #content select")];
  const disabledStates = controls.map(el => el.disabled);
  controls.forEach(el => { el.disabled = true; });
  document.getElementById("edit-feedback").textContent = "正在儲存…";
  try {
    const result = await apiCall(`/cover-letters/${allVersions[currentIdx].id}/versions`, {
      method: "POST", body: JSON.stringify(draft),
    });
    allVersions.unshift(result.data);
    currentIdx = 0;
    renderFullPage();
    showToast(`已儲存為 v${result.data.version}，追蹤紀錄選用版本維持不變`, "success");
  } catch (error) {
    document.getElementById("edit-feedback").textContent = `儲存失敗：${error.message}，修改內容仍保留。`;
  } finally {
    isSaving = false;
    controls.forEach((el, index) => { el.disabled = disabledStates[index]; });
  }
}

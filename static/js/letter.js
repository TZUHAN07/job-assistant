let allVersions = [];
let currentIdx = 0;
let matchingId = null;
let matchingInfo = null;

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
    currentIdx = 0;

    renderHeader();
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

  contentEl.innerHTML = `
    ${renderVersionTabs()}
    ${renderControlPanel(current)}
    ${renderSplitView(current)}
  `;

  attachEventListeners();
}

function attachEventListeners() {
  document.querySelectorAll(".version-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      currentIdx = parseInt(tab.dataset.idx);
      renderFullPage();
    });
  });

  document
    .getElementById("regenerate-btn")
    ?.addEventListener("click", handleRegenerate);

  document.getElementById("copy-btn")?.addEventListener("click", () => {
    copyToClipboard(allVersions[currentIdx].content);
  });
}

async function handleRegenerate() {
  const toneEl = document.getElementById("tone-select");
  const langEl = document.getElementById("language-select");
  const tone = toneEl?.value || "professional";
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
    // 新 letter unshift 到 array 頂端, currentIdx 指向新版
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
   <div class="flex items-center justify-between py-4 border-b border-gray-200">
      <div class="flex items-center gap-4">
        <a href="matching.html?id=${matchingId}" 
           class="inline-flex items-center text-sm font-medium text-gray-500 hover:text-indigo-600 transition">
          ← 返回匹配分析
        </a>
        <h1 class="text-xl font-bold text-gray-800">求職信工作室</h1>
      </div>
      ${jobInfo ? `<div class="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">${jobInfo}</div>` : ""}
    </div>

   `;
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
  const hasSections = letter.sections.opening !== null;

  const sections = [
    {
      title: "Opening · 開場",
      content: letter.sections.opening,
      borderClass: "border-indigo-400",
    },
    {
      title: "Why Me · 為何選我",
      content: letter.sections.why_me,
      borderClass: "border-emerald-400",
    },
    {
      title: "Why Company · 為何貴公司",
      content: letter.sections.why_company,
      borderClass: "border-amber-400",
    },
    {
      title: "Call to Action · 行動呼籲",
      content: letter.sections.call_to_action,
      borderClass: "border-rose-400",
    },
  ];

  return `
    <h3 class="text-lg font-bold text-gray-800 mb-4">Sections 拆解</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- 左: Sections 卡片 -->
      <div class="space-y-4">
        ${
          hasSections
            ? sections
                .map(
                  (s) => `
                    <div class="bg-white rounded-lg shadow p-4 border-l-4 ${s.borderClass}">
                      <h4 class="text-sm font-semibold text-gray-700 mb-2">${s.title}</h4>
                      <p class="letter-content text-sm text-gray-600">${s.content}</p>
                    </div>
                  `,
                )
                .join("")
            : `
              <div class="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center text-gray-500 text-sm">
                此版本無 sections 拆解 (舊版), 請重新生成新版
              </div>
            `
        }
      </div>

      <!-- 右: 完整預覽 + Copy -->
      <div class="bg-white rounded-lg shadow p-6 h-fit sticky top-6">
        <div class="flex items-center justify-between mb-4">
      
          <h3 class="text-lg font-bold text-gray-800">完整預覽</h3>
          <button id="copy-btn" class="inline-flex items-center gap-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2 rounded-lg transition">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/>
            </svg>
            複製全文
          </button>
        </div>
        <div class="letter-content text-sm text-gray-700 max-h-[600px] overflow-y-auto">${letter.content}</div>
      </div>
    </div>
  `;
}

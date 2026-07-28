(async function main() {
  const headerEl = document.getElementById("header");
  const contentEl = document.getElementById("content");

  const matchingId = getQueryParam("id");
  if (!matchingId) {
    showError(contentEl, "URL 缺少 matching_id 參數");
    return;
  }

  showLoading(contentEl, "正在載入匹配結果...");

  try {
    const res = await apiCall(`/matchings/${matchingId}`);
    const data = res.data;

    renderHeader(headerEl, data);
    renderContent(contentEl, data);
  } catch (e) {
    showError(contentEl, `載入失敗: ${e.message}`, () => location.reload());
  }
})();

function renderHeader(el, data) {
  el.innerHTML = `
    <div class="border-b pb-4">
      <p class="text-sm text-gray-500 mb-1">匹配度分析</p>
      <h1 class="text-2xl font-bold text-gray-800">${data.job_title}</h1>
      <p class="text-gray-600 mt-1">${data.job_company}</p>
      <span class="inline-block mt-2 bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-sm">
        對照履歷: ${data.resume_name || "預設履歷"}
      </span>
    </div>
  `;
}

function renderContent(el, data) {
  el.innerHTML = `
    ${renderScore(data.score)}
    ${renderReasons(data.match_reasons)}
    ${renderSkills(data.matched_skills, data.missing_skills)}
    ${renderQuickWins(data.quick_wins)}
    ${renderGoals(data.long_term_goals)}
    ${renderCTA(data.id)}
  `;
}

function renderScore(score) {
  let scoreColor = "#f43f5e";
  let statusText = "需補強關鍵技能";
  let statusBg = "bg-rose-50 text-rose-700 border-rose-200";
  let summaryDesc =
    "核心技能落差較大，建議先完成下方 Long Term Goals 深度累積經驗後再行投遞。";

  if (score >= 80) {
    scoreColor = "#10b981";
    statusText = "高度契合";
    statusBg = "bg-emerald-50 text-emerald-700 border-emerald-200";
    summaryDesc =
      "您的核心技能非常符合該職缺需求，建議直接生成 Cover Letter 開始投遞！";
  } else if (score >= 60) {
    scoreColor = "#f59e0b";
    statusText = "尚有進步空間";
    statusBg = "bg-amber-50 text-amber-700 border-amber-200";
    summaryDesc =
      "您具備基礎能力但仍有少數缺口，建議參考下方 Quick Wins 進行短期履歷優化。";
  }

  return `
    <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 sm:p-8 mb-6">
      <div class="flex flex-col sm:flex-row items-center gap-6 sm:gap-8">
        <div class="flex flex-col items-center shrink-0">
          <div class="score-ring flex items-center justify-center" style="--score: ${score}; --color: ${scoreColor};">
            <div class="flex flex-col items-center leading-none">
              <div class="flex items-baseline justify-center gap-0.5">
                <span class="text-5xl font-extrabold tracking-tight" style="color: ${scoreColor}">${score}</span>
                <span class="text-sm font-medium" style="color: ${scoreColor}">%</span>
              </div>
            </div>
          </div>
        </div>
        <div class="flex-1 text-center sm:text-left space-y-2">
          <div class="flex items-center justify-center sm:justify-start gap-2">
            <span class="text-xs font-semibold uppercase tracking-wider text-gray-400">AI 綜合匹配評估</span>
            <span class="px-2.5 py-0.5 text-xs font-semibold rounded-full border ${statusBg}">
              ${statusText}
            </span>
          </div>
          <h2 class="text-xl font-bold text-gray-800">
            整體匹配度為 ${score}%
          </h2>
          <p class="text-sm text-gray-600 leading-relaxed">
            ${summaryDesc}
          </p>
        </div>
      </div>
    </div>
  `;
}

function renderReasons(reasons) {
  return `
    <div class="bg-white rounded-lg shadow p-6 mb-6">
      <h2 class="text-lg font-semibold mb-3 text-gray-800">核心契合點</h2>
      <ul class="space-y-3">
        ${reasons
          .map(
            (r) => `
              <li class="flex items-start gap-3">
                <svg class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                </svg>
                <span class="text-gray-700 text-sm leading-relaxed">${r}</span>
              </li>
            `,
          )
          .join("")}
      </ul>
    </div>
  `;
}

function renderSkills(matched = [], missing = []) {
  return `
    <div class="bg-white rounded-lg shadow p-6 mb-6">
      <h2 class="text-lg font-semibold mb-3 text-gray-800">技能對照</h2>
      <div class="mb-4">
        <p class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">匹配技能</p>
        <div class="flex flex-wrap gap-2">
          ${
            matched.length > 0
              ? matched
                  .map(
                    (s) => `
                      <span class="px-3 py-1 text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/60 rounded-full">
                        ${s}
                      </span>
                    `,
                  )
                  .join("")
              : `<span class="text-xs text-gray-400">尚無符合技能</span>`
          }
        </div>
      </div>
      <div>
        <p class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">需提升技能</p>
        <div class="flex flex-wrap gap-2">
          ${
            missing.length > 0
              ? missing
                  .map(
                    (s) => `
                      <span class="px-3 py-1 text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200/60 rounded-full">
                        ${s}
                      </span>
                    `,
                  )
                  .join("")
              : `<span class="text-xs text-emerald-600 font-medium">無缺少的關鍵技能</span>`
          }
        </div>
      </div>
    </div>
  `;
}

function renderQuickWins(items) {
  return `
    <div class="bg-white rounded-lg shadow p-6 mb-6">
      <div class="flex items-center gap-2 mb-1">
        <svg class="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <h2 class="text-lg font-bold text-gray-800">Quick Wins - 短期補強</h2>
      </div>
      <p class="text-sm text-gray-500 mb-4 pl-7">1-2 週內可完成的行動</p>
      <div class="space-y-3">
        ${
          items.length > 0
            ? items
                .map(
                  (item) => `
                    <div class="border-l-4 border-amber-400 bg-amber-50/60 p-4 rounded">
                      <p class="text-gray-700 text-sm leading-relaxed">${item}</p>
                    </div>
                  `,
                )
                .join("")
            : `<p class="text-sm text-gray-400">尚無 Quick Wins 建議</p>`
        }
      </div>
    </div>
  `;
}

function renderGoals(items) {
  return `
    <div class="bg-white rounded-lg shadow p-6 mb-6">
      <div class="flex items-center gap-2 mb-1">
        <svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h2 class="text-lg font-bold text-gray-800">Long Term Goals - 長期發展</h2>
      </div>
      <p class="text-xs text-gray-500 mb-4 pl-7">3-6 個月深度累積與技能提升方向</p>
      <div class="space-y-3">
        ${
          items.length > 0
            ? items
                .map(
                  (item) => `
                    <div class="border-l-4 border-indigo-400 bg-indigo-50/50 p-4 rounded">
                      <p class="text-gray-700 text-sm leading-relaxed">${item}</p>
                    </div>
                  `,
                )
                .join("")
            : `<p class="text-sm text-gray-400">尚無 Long Term Goals 建議</p>`
        }
      </div>
    </div>
  `;
}

function renderCTA(matchingId) {
  return `
    <div class="mt-8 pt-6 border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-4">
      <a
        href="index.html"
        class="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 transition shadow-sm"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        重新選擇職缺 / 履歷
      </a>
      <a
        href="letter.html?matching_id=${matchingId}"
        class="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-md hover:shadow-lg transition"
      >
        <span>前往生成 Cover Letter</span>
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </a>
    </div>
  `;
}

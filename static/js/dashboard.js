let allResumes = [];
let allJobs = [];
let currentJobTab = "url";

(async function main() {
  await loadAll();
})();

async function loadAll() {
  try {
    const [resumesRes, jobsRes] = await Promise.all([
      apiCall("/resumes"),
      apiCall("/jobs"),
    ]);

    allResumes = resumesRes.data || [];
    allJobs = jobsRes.data || [];

    renderResumeSection();
    renderJobSection();
    renderMatchSection();
  } catch (e) {
    showToast(`載入失敗: ${e.message} `, "error");
  }
}

function renderResumeSection() {
  const el = document.getElementById("section-resume");
  el.innerHTML = `
    <h2 class="text-lg font-bold text-gray-800 mb-4">履歷管理</h2>

    <div id="resume-drop" class="drop-zone border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-indigo-400 transition mb-4">
      <p class="text-gray-500 text-sm">拖曳 PDF 至此或 <span class="text-indigo-600 font-semibold">click 選檔</span></p>
      <input type="file" id="resume-file" accept="application/pdf" class="hidden" />
    </div>

    <div class="space-y-2 max-h-60 overflow-y-auto pr-1">
      ${
        allResumes.length > 0
          ? allResumes
              .map(
                (r) => `
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div class="flex-1 min-w-0 mr-3">
                  <p class="text-sm font-medium text-gray-800 truncate">${escapeHtml(r.resume_name || "未命名履歷")}</p>
                  <p class="text-xs text-gray-500 truncate">${escapeHtml(r.filename)} · ${new Date(r.uploaded_at).toLocaleString("zh-TW")}</p>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                  ${
                    r.processed_at
                      ? `<span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-1 rounded">✓ 已解析</span>`
                      : `<span class="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">解析失敗</span>`
                  }
                  <button 
                    data-resume-id="${r.id}" 
                    class="delete-resume-btn text-gray-400 hover:text-red-600 hover:bg-red-50 p-1.5 rounded-lg transition shrink-0 cursor-pointer"
                    title="刪除履歷"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            `,
              )
              .join("")
          : `<p class="text-sm text-gray-400 text-center py-4">尚未上傳任何履歷</p>`
      }
    </div>
  `;
  setupResumeUpload();
  setupResumeDeleteHandlers();
}

function setupResumeUpload() {
  const dropZone = document.getElementById("resume-drop");
  const fileInput = document.getElementById("resume-file");

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files[0]) handleResumeUpload(e.target.files[0]);
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () =>
    dropZone.classList.remove("dragover"),
  );
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files[0]) handleResumeUpload(e.dataTransfer.files[0]);
  });
}

function setupResumeDeleteHandlers() {
  document.querySelectorAll(".delete-resume-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const button = e.currentTarget;
      const resumeId = button.dataset.resumeId;

      if (
        !confirm(
          "確定要刪除這份履歷嗎？相關的匹配分析與求職信也會一併刪除, 且無法恢復。",
        )
      )
        return;

      try {
        await apiCall(`/resumes/${resumeId}`, { method: "DELETE" });
        showToast("履歷已刪除", "success");
        await loadAll();
      } catch (e) {
        showToast(`刪除失敗: ${e.message}`, "error");
        await loadAll();
      }
    });
  });
}

function setupJobDeleteHandlers() {
  document.querySelectorAll(".delete-job-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const button = e.currentTarget;
      const jobId = button.dataset.jobId;

      if (
        !confirm(
          "確定要刪除這份職缺嗎？相關的匹配分析與求職信也會一併刪除, 且無法恢復。",
        )
      )
        return;

      try {
        await apiCall(`/jobs/${jobId}`, { method: "DELETE" });
        showToast("職缺已刪除", "success");
        await loadAll();
      } catch (e) {
        showToast(`刪除失敗: ${e.message}`, "error");
        await loadAll();
      }
    });
  });
}
async function handleResumeUpload(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showToast("僅支援 PDF 檔案", "error");
    return;
  }

  showToast("上傳中... AI 正在解析履歷 (約 10 秒)", "info");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/resumes/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    showToast(`履歷已上傳: ${data.data.filename}`, "success");
    await loadAll();
  } catch (e) {
    showToast(`上傳失敗: ${e.message}`, "error");
  }
}

function renderJobSection() {
  const el = document.getElementById("section-job");
  el.innerHTML = `
    <h2 class="text-lg font-bold text-gray-800 mb-4">職缺管理</h2>
    <div class="flex gap-2 mb-4 border-b border-gray-200">
      <button class="job-tab px-4 py-2 text-sm font-medium border-b-2 transition ${
        currentJobTab === "url"
          ? "border-indigo-600 text-indigo-600"
          : "border-transparent text-gray-500 hover:text-gray-700"
      }" data-tab="url">
        URL 抓取
      </button>
      <button class="job-tab px-4 py-2 text-sm font-medium border-b-2 transition ${
        currentJobTab === "text"
          ? "border-indigo-600 text-indigo-600"
          : "border-transparent text-gray-500 hover:text-gray-700"
      }" data-tab="text">
        貼上內文
      </button>
    </div>
  
   ${
     currentJobTab === "url"
       ? `
        <div class="mb-6">
          <input type="url" id="job-url-input" placeholder="貼上 104 / CakeResume / LinkedIn JD 網址..."
                 class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 mb-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <button id="job-url-submit" class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
            抓取 JD
          </button>
          <p class="text-xs text-gray-400 mt-2">Firecrawl scrape → AI 解析 (約 15 秒)</p>
        </div>
      `
       : `
        <div class="mb-6">
          <textarea id="job-text-input" rows="6" placeholder="直接貼上完整 JD 內容 (至少 50 字)..."
                    class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 mb-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"></textarea>
          <button id="job-text-submit" class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
            解析 JD
          </button>
          <p class="text-xs text-gray-400 mt-2">若 URL 抓不到 (anti-bot), 用 text 貼上 fallback</p>
        </div>
      `
   }

    <div class="space-y-2 max-h-60 overflow-y-auto pr-1">
      ${
        allJobs.length > 0
          ? allJobs
              .map(
                (j) => `
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div class="flex-1 min-w-0 mr-3">
                  <p class="text-sm font-medium text-gray-800 truncate">${escapeHtml(j.job_title || "未命名職缺")} @ ${escapeHtml(j.job_company || "未知公司")}</p>
                  <p class="text-xs text-gray-500 truncate">${escapeHtml(j.source_type)} · ${j.created_at ? new Date(j.created_at).toLocaleString("zh-TW") : "未知時間"}</p>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                  ${
                    j.processed_at
                      ? `<span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-1 rounded">✓ 已解析</span>`
                      : `<span class="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">解析失敗</span>`
                  }
                  <button
                    data-job-id="${j.id}"
                    class="delete-job-btn text-gray-400 hover:text-red-600 hover:bg-red-50 p-1.5 rounded-lg transition shrink-0 cursor-pointer"
                    title="刪除職缺"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            `,
              )
              .join("")
          : `<p class="text-sm text-gray-400 text-center py-4">尚未輸入任何職缺</p>`
      }
    </div>
  `;
  setupJobHandlers();
  setupJobDeleteHandlers();
}

function setupJobHandlers() {
  document.querySelectorAll(".job-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      currentJobTab = tab.dataset.tab;
      renderJobSection();
    });
  });

  document
    .getElementById("job-url-submit")
    ?.addEventListener("click", handleAddJobFromUrl);
  document
    .getElementById("job-text-submit")
    ?.addEventListener("click", handleAddJobFromText);
}

async function handleAddJobFromUrl() {
  const url = document.getElementById("job-url-input").value.trim();
  if (!url) {
    showToast("請輸入 JD 網址", "error");
    return;
  }

  showToast("Firecrawl 抓取中... AI 解析 (約 15 秒)", "info");

  try {
    const res = await apiCall("/jobs/parse-url", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
    showToast(
      `✓ JD 已解析: ${res.data.parsed_data?.title || "未命名"}`,
      "success",
    );
    await loadAll();
  } catch (e) {
    showToast(`失敗: ${e.message}`, "error");
  }
}

async function handleAddJobFromText() {
  const text = document.getElementById("job-text-input").value.trim();
  if (text.length < 50) {
    showToast("JD 內文至少 50 字", "error");
    return;
  }

  showToast("AI 解析中... (約 10 秒)", "info");

  try {
    const res = await apiCall("/jobs/parse-text", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    showToast(
      `✓ JD 已解析: ${res.data.parsed_data?.title || "未命名"}`,
      "success",
    );
    await loadAll();
  } catch (e) {
    showToast(`失敗: ${e.message}`, "error");
  }
}

function renderMatchSection() {
  const el = document.getElementById("section-match");
  if (!el) return;

  const validResumes = allResumes.filter((r) => r.processed_at);
  const validJobs = allJobs.filter((j) => j.processed_at);

  el.innerHTML = `
    <h2 class="text-lg font-bold text-gray-800 mb-4">開始 AI 匹配</h2>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
      <div>
        <label for="match-resume" class="block text-xs font-semibold text-gray-600 mb-1">選擇履歷</label>
        <select id="match-resume" class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option value="">請選擇已解析的履歷...</option>
          ${validResumes
            .map(
              (r) =>
                `<option value="${r.id}">${escapeHtml(r.resume_name || r.filename)}</option>`,
            )
            .join("")}
        </select>
      </div>

      <div>
        <label for="match-job" class="block text-xs font-semibold text-gray-600 mb-1">選擇職缺</label>
        <select id="match-job" class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option value="">請選擇已解析的職缺...</option>
          ${validJobs
            .map(
              (j) =>
                `<option value="${j.id}">${escapeHtml(j.job_title || "未命名職缺")} @ ${escapeHtml(j.job_company || "未知公司")}</option>`,
            )
            .join("")}
        </select>
      </div>
    </div>

    <button id="trigger-match" class="w-full md:w-auto bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-6 py-2.5 rounded-lg transition">
      開始匹配
    </button>
  `;

  document
    .getElementById("trigger-match")
    ?.addEventListener("click", handleStartMatch);
}

async function handleStartMatch() {
  const resumeId = document.getElementById("match-resume")?.value;
  const jobId = document.getElementById("match-job")?.value;
  const btn = document.getElementById("trigger-match");

  if (!resumeId || !jobId) {
    showToast("請選擇履歷和職缺", "error");
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.classList.add("opacity-50", "cursor-not-allowed");
    btn.textContent = "AI 正在深度分析中 (約 20 秒)...";
  }
  showToast("AI 開始進行履歷與職缺深度匹配...", "info");

  try {
    const res = await apiCall("/matchings/score", {
      method: "POST",
      body: JSON.stringify({
        resume_id: resumeId,
        job_id: jobId,
      }),
    });

    const matchId = res.data?.id;
    if (matchId) {
      showToast("匹配完成，正在跳轉結果頁...", "success");
      window.location.href = `matching.html?id=${matchId}`;
    } else {
      throw new Error("伺服器未回傳匹配結果 ID");
    }
  } catch (e) {
    showToast(`匹配失敗: ${e.message}`, "error");

    if (btn) {
      btn.disabled = false;
      btn.classList.remove("opacity-50", "cursor-not-allowed");
      btn.textContent = "開始匹配";
    }
  }
}

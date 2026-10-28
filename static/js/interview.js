(() => {
  const matchingId = Number(getQueryParam("matching_id"));
  const generateButton = document.getElementById("generate");
  const reloadButton = document.getElementById("reload");
  const statusEl = document.getElementById("status");
  const errorEl = document.getElementById("error");
  const questionsEl = document.getElementById("questions");
  let current = null;
  let busy = false;
  let loaded = false;

  function setBusy(value) {
    busy = value;
    generateButton.disabled = value;
    reloadButton.disabled = value;
    questionsEl.setAttribute("aria-busy", String(value));
  }
  function showFailure(message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }
  function clearError() { errorEl.hidden = true; errorEl.textContent = ""; }
  function evidence(items) {
    if (!items?.length) return '<p class="text-sm text-gray-500">未引用直接專案證據。</p>';
    return items.map(item => `<blockquote class="border-l-2 border-indigo-200 pl-3 mt-3 text-sm whitespace-pre-wrap break-words">${item.project ? `<p class="font-medium mb-1">${escapeHtml(item.project)}</p>` : ""}${escapeHtml(item.text)}</blockquote>`).join("");
  }
  function render() {
    generateButton.hidden = false;
    generateButton.textContent = current ? "重新生成" : "生成面試題";
    generateButton.className = current
      ? "px-4 py-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      : "px-5 py-2.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed";
    if (!current) {
      questionsEl.innerHTML = "";
      statusEl.textContent = "尚未生成題目。按下「生成面試題」開始準備。";
      return;
    }
    statusEl.textContent = `生成於 ${new Date(current.created_at).toLocaleString("zh-TW")}。題目依當時資料產生；重新生成不保證題目不同。`;
    questionsEl.innerHTML = `<p class="text-sm text-gray-500">AI 題目供練習參考，不代表公司實際考題。引用內容與經驗描述請自行確認。</p>` + current.report.questions.map((q, i) => `
      <article class="bg-white border rounded-xl p-6">
        <div class="flex gap-3 items-center mb-3"><span class="text-indigo-600 font-semibold">第 ${i + 1} 題</span><span class="text-xs rounded-full bg-indigo-50 text-indigo-700 px-3 py-1">${q.kind === "project_experience" ? "專案經驗" : "假設情境"}</span></div>
        <h2 class="font-semibold leading-relaxed whitespace-pre-wrap break-words">${escapeHtml(q.question)}</h2>
        <details class="mt-4"><summary class="cursor-pointer text-sm text-indigo-700">出題理由與參考依據</summary>
          <p class="text-sm text-gray-600 leading-relaxed mt-3 whitespace-pre-wrap">${escapeHtml(q.rationale)}</p>
          <h3 class="font-medium text-sm mt-4">職缺需求</h3>${evidence(q.job_evidence)}
          <h3 class="font-medium text-sm mt-4">履歷原文</h3>${evidence(q.resume_evidence)}
        </details>
      </article>`).join("");
  }
  async function load() {
    if (busy) return;
    setBusy(true); clearError(); loaded = false; generateButton.hidden = true;
    statusEl.textContent = "正在讀取已保存題組…";
    try {
      const [matching, latest] = await Promise.all([
        apiCall(`/matchings/${matchingId}`),
        apiCall(`/interview-sets/latest?matching_id=${matchingId}`),
      ]);
      document.getElementById("job-info").textContent = [matching.data.job_company, matching.data.job_title].filter(Boolean).join(" · ");
      current = latest.data ? (await apiCall(`/interview-sets/${latest.data.id}`)).data : null;
      loaded = true; render();
    } catch (error) {
      statusEl.textContent = "尚未確認最近題組，請重新載入。";
      showFailure(error.message);
    } finally { setBusy(false); }
  }
  async function generate() {
    if (busy || !loaded) return;
    if (current && !window.confirm("重新生成一組面試題？完成後會顯示新題組，題目可能與先前重複。")) return;
    setBusy(true); clearError();
    statusEl.textContent = "正在準備題目，可能需要幾分鐘，請勿重複點擊或關閉頁面。";
    try {
      const result = await apiCall("/interview-sets/generate", {
        method: "POST", body: JSON.stringify({ matching_id: matchingId }),
      });
      current = result.data; render();
    } catch (error) {
      // 回應中斷時伺服器可能已存檔，先讓使用者查詢，避免直接重送付費生成。
      loaded = false; generateButton.hidden = true;
      statusEl.textContent = current ? "保留原本題組，請先重新載入確認最新結果。" : "請先重新載入，確認是否已有保存的題組。";
      showFailure(error.message);
    } finally { setBusy(false); }
  }
  if (!Number.isSafeInteger(matchingId) || matchingId <= 0) {
    statusEl.textContent = "無法開啟面試準備。";
    showFailure("網址缺少有效的 matching_id，請從匹配結果頁進入。");
    reloadButton.hidden = true;
    return;
  }
  document.getElementById("back-link").href = `matching.html?id=${matchingId}`;
  generateButton.addEventListener("click", generate);
  reloadButton.addEventListener("click", load);
  load();
})();

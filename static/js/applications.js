const PAGE_SIZE = 20;
let currentOffset = 0;
let isLoading = false;
const content = document.getElementById("applications-content");
const summary = document.getElementById("summary");
const pagination = document.getElementById("pagination");
const previousButton = document.getElementById("previous");
const nextButton = document.getElementById("next");
const reloadButton = document.getElementById("reload");

const statusLabels = new Map([
  ["preparing", ["準備中", "bg-gray-100 text-gray-700"]],
  ["applied", ["已投遞", "bg-indigo-50 text-indigo-700"]],
  ["interview", ["面試中", "bg-amber-50 text-amber-800"]],
  ["closed", ["已結束", "bg-emerald-50 text-emerald-700"]],
]);

function formatAppliedAt(value) {
  if (!value) return "尚未填寫";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "時間格式異常";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", timeZone: "Asia/Taipei",
  }).format(date);
}

function renderApplication(row) {
  const [label, color] = statusLabels.get(row.status) || ["未知狀態", "bg-gray-100 text-gray-700"];
  const score = row.score == null ? "尚未評分" : `${row.score} / 100`;
  const letter = row.cover_letter_id == null
    ? "未選用"
    : `v${row.cover_letter_version ?? "?"}`;
  return `<tr class="border-t border-gray-100 align-top">
    <td class="p-4 max-w-xs break-words"><p class="font-semibold">${escapeHtml(row.job_title || "未提供職稱")}</p><p class="text-sm text-gray-500 mt-1">${escapeHtml(row.company || "未提供公司")}</p><p class="text-xs text-gray-400 mt-2">紀錄 #${escapeHtml(row.id)}</p></td>
    <td class="p-4 font-semibold whitespace-nowrap">${escapeHtml(score)}</td>
    <td class="p-4 whitespace-nowrap"><span class="inline-block rounded-full px-3 py-1 text-xs font-medium ${color}">${escapeHtml(label)}</span></td>
    <td class="p-4 max-w-xs break-words"><p>${escapeHtml(letter)}</p>${row.cover_letter_id == null ? "" : `<p class="text-xs text-gray-500 mt-1">${escapeHtml(row.cover_letter_title || "未命名求職信")}</p>`}</td>
    <td class="p-4 text-sm whitespace-nowrap">${escapeHtml(formatAppliedAt(row.applied_at))}</td>
    <td class="p-4 text-sm max-w-xs break-words">${escapeHtml(row.resume_filename || "未提供履歷名稱")}</td>
  </tr>`;
}

async function loadApplications(offset = currentOffset) {
  if (isLoading) return;
  isLoading = true;
  content.setAttribute("aria-busy", "true");
  reloadButton.disabled = true;
  previousButton.disabled = true;
  nextButton.disabled = true;
  pagination.hidden = true;
  summary.textContent = "正在讀取求職紀錄…";
  showLoading(content, "正在載入求職追蹤…");
  try {
    let result = await apiCall(`/applications?limit=${PAGE_SIZE}&offset=${offset}`);
    if (offset > 0 && offset >= result.total) {
      offset = Math.max(0, Math.floor((result.total - 1) / PAGE_SIZE) * PAGE_SIZE);
      result = await apiCall(`/applications?limit=${PAGE_SIZE}&offset=${offset}`);
    }
    currentOffset = offset;
    summary.textContent = `共 ${result.total} 筆紀錄 · 依建立時間由新到舊排列`;
    if (result.total === 0) {
      content.innerHTML = `<div class="p-10 text-center"><h2 class="text-lg font-semibold">尚無求職追蹤紀錄</h2><p class="text-gray-500 mt-2">建立紀錄後，就能在這裡查看匹配度與投遞進度。</p><a href="index.html" class="inline-block mt-5 text-indigo-600 hover:underline">返回首頁查看履歷與職缺</a></div>`;
      return;
    }
    content.innerHTML = `<div class="overflow-x-auto" role="region" aria-label="求職紀錄表格，可左右捲動" tabindex="0"><table class="w-full min-w-[850px] text-left"><caption class="sr-only">求職追蹤紀錄，投遞時間以台北時區顯示</caption><thead class="bg-gray-50 text-sm text-gray-500"><tr>${["職缺／公司", "匹配度", "投遞狀態", "求職信版本", "投遞時間（台北）", "使用履歷"].map(text => `<th scope="col" class="p-4 font-medium">${text}</th>`).join("")}</tr></thead><tbody>${result.data.map(renderApplication).join("")}</tbody></table></div>`;
    pagination.hidden = false;
    document.getElementById("page-info").textContent = `第 ${Math.floor(offset / PAGE_SIZE) + 1} / ${Math.ceil(result.total / PAGE_SIZE)} 頁 · 顯示 ${offset + 1}–${offset + result.data.length} 筆`;
    previousButton.disabled = offset === 0;
    nextButton.disabled = offset + PAGE_SIZE >= result.total;
  } catch (error) {
    summary.textContent = "載入失敗";
    showError(content, escapeHtml(`無法載入求職紀錄：${error.message}`), () => loadApplications(offset));
  } finally {
    content.setAttribute("aria-busy", "false");
    reloadButton.disabled = false;
    isLoading = false;
  }
}

previousButton.addEventListener("click", () => loadApplications(Math.max(0, currentOffset - PAGE_SIZE)));
nextButton.addEventListener("click", () => loadApplications(currentOffset + PAGE_SIZE));
reloadButton.addEventListener("click", () => loadApplications());
loadApplications();

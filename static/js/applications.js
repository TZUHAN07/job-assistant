const PAGE_SIZE = 20;
let currentOffset = 0;
let isLoading = false;
let applications = [];
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
  if (Number.isNaN(date.getTime())) return "日期格式異常";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric", month: "2-digit", day: "2-digit",
    timeZone: "Asia/Taipei",
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
    <td class="p-4 whitespace-nowrap"><select data-status-id="${escapeHtml(row.id)}" aria-label="紀錄 ${escapeHtml(row.id)} 投遞狀態，選擇後自動儲存" class="border rounded-lg px-3 py-2 text-sm cursor-pointer focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 ${color}">${statusLabels.has(row.status) ? "" : '<option value="" selected disabled>未知狀態</option>'}${Array.from(statusLabels, ([value, [text]]) => `<option value="${value}" ${value === row.status ? "selected" : ""}>${text}</option>`).join("")}</select></td>
    <td class="p-4 max-w-xs break-words">${row.cover_letter_id == null ? `<p>${escapeHtml(letter)}</p>` : `<a href="letter.html?matching_id=${encodeURIComponent(row.matching_id)}&amp;cover_letter_id=${encodeURIComponent(row.cover_letter_id)}" class="text-indigo-700 underline underline-offset-4 hover:text-indigo-900">查看求職信 ${escapeHtml(letter)}</a>`}${row.cover_letter_id == null ? "" : `<p class="text-xs text-gray-500 mt-1">${escapeHtml(row.cover_letter_title || "未命名求職信")}</p>`}</td>
    <td class="p-4 text-sm whitespace-nowrap"><button type="button" data-edit-id="${escapeHtml(row.id)}" data-edit-field="applied_at" class="text-indigo-700 border border-indigo-100 rounded-lg px-3 py-2 hover:bg-indigo-50 focus:ring-2 focus:ring-indigo-500" aria-label="編輯紀錄 ${escapeHtml(row.id)} 的投遞日期">${row.applied_at ? escapeHtml(formatAppliedAt(row.applied_at)) + " ✎" : "+ 填寫日期"}</button></td>
    <td class="p-4 text-sm max-w-xs break-words">${escapeHtml(row.resume_filename || "未提供履歷名稱")}</td>
    <td class="p-4 min-w-[180px] max-w-xs"><p class="text-sm whitespace-pre-wrap break-words">${escapeHtml(row.notes || "尚無備註")}</p><button type="button" data-edit-id="${escapeHtml(row.id)}" data-edit-field="notes" title="編輯備註" class="mt-2 text-indigo-700 border border-indigo-100 rounded-lg px-3 py-2 text-sm hover:bg-indigo-50 focus:ring-2 focus:ring-indigo-500" aria-label="編輯紀錄 ${escapeHtml(row.id)} 的備註"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L9 17l-4 1 1-4Z"/></svg></button></td>
    <td class="p-4"><button type="button" data-delete-id="${escapeHtml(row.id)}" title="刪除追蹤紀錄" aria-label="刪除追蹤紀錄 ${escapeHtml(row.id)}" class="text-gray-400 hover:text-red-600 hover:bg-red-50 border rounded-lg p-3 focus:ring-2 focus:ring-red-500"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg></button></td>
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
    applications = result.data;
    summary.textContent = `共 ${result.total} 筆紀錄 · 依建立時間由新到舊排列`;
    if (result.total === 0) {
      content.innerHTML = `<div class="p-10 text-center"><h2 class="text-lg font-semibold">尚無求職追蹤紀錄</h2><p class="text-gray-500 mt-2">建立紀錄後，就能在這裡查看匹配度與投遞進度。</p><a href="index.html" class="inline-block mt-5 text-indigo-600 hover:underline">返回首頁查看履歷與職缺</a></div>`;
      return;
    }
    content.innerHTML = `<div class="overflow-x-auto" role="region" aria-label="求職紀錄表格，可左右捲動" tabindex="0"><table class="w-full min-w-[850px] text-left"><caption class="sr-only">求職追蹤紀錄，投遞日期以台北時區顯示</caption><thead class="bg-gray-50 text-sm text-gray-500"><tr>${["職缺／公司", "匹配度", "投遞狀態", "求職信版本", "投遞日期", "使用履歷", "備註", "操作"].map(text => `<th scope="col" class="p-4 font-medium">${text}</th>`).join("")}</tr></thead><tbody>${result.data.map(renderApplication).join("")}</tbody></table></div>`;
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


const editDialog = document.getElementById("edit-dialog");
const editForm = document.getElementById("edit-form");
const editDate = document.getElementById("edit-date");
const editNotes = document.getElementById("edit-notes");
const editError = document.getElementById("edit-error");
const editSave = document.getElementById("edit-save");
const editCancel = document.getElementById("edit-cancel");
let editing = null;
let originalInputs = null;
let isSaving = false;
let editTrigger = null;
let editingField = null;

function toTaipeiInput(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

content.addEventListener("click", event => {
  const button = event.target.closest("button[data-edit-id]");
  if (!button || isLoading || isSaving) return;
  const row = applications.find(item => String(item.id) === button.dataset.editId);
  if (!row) return;
  editing = row;
  editTrigger = button;
  editingField = button.dataset.editField;
  document.getElementById("date-field").hidden = editingField !== "applied_at";
  document.getElementById("notes-field").hidden = editingField !== "notes";
  document.getElementById("edit-title").textContent = editingField === "applied_at" ? "編輯投遞日期" : "編輯備註";
  editDate.value = toTaipeiInput(row.applied_at);
  editNotes.value = row.notes ?? "";
  originalInputs = {applied_at: editDate.value, notes: editNotes.value};
  document.getElementById("edit-context").textContent = `紀錄 #${row.id} · ${row.company || "未提供公司"} · ${row.job_title || "未提供職稱"}`;
  editError.textContent = "";
  editDialog.showModal();
  (editingField === "applied_at" ? editDate : editNotes).focus();
});

editCancel.addEventListener("click", () => {
  if (!isSaving) editDialog.close();
});
editDialog.addEventListener("cancel", event => {
  if (isSaving) event.preventDefault();
});
editDialog.addEventListener("close", () => {
  editing = null;
  if (editTrigger?.isConnected) editTrigger.focus();
});

editForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (!editing || isSaving || !editForm.reportValidity()) return;
  const changes = {};
  if (editingField === "notes" && editNotes.value !== originalInputs.notes) changes.notes = editNotes.value === "" ? null : editNotes.value;

  if (editingField === "applied_at" && editDate.value !== originalInputs.applied_at) {
    const date = editDate.value ? new Date(`${editDate.value}T00:00:00+08:00`) : null;
    if (date && Number.isNaN(date.getTime())) {
      editError.textContent = "請輸入有效的投遞日期";
      return;
    }
    changes.applied_at = date ? date.toISOString() : null;
  }
  if (Object.keys(changes).length === 0) {
    editError.textContent = "尚未修改任何欄位";
    return;
  }
  isSaving = true;
  editError.textContent = "";
  editForm.setAttribute("aria-busy", "true");
  document.getElementById("edit-fields").disabled = true;
  editSave.disabled = true;
  editCancel.disabled = true;
  editSave.textContent = "儲存中…";
  try {
    await apiCall(`/applications/${editing.id}`, {method: "PATCH", body: JSON.stringify(changes)});
    editDialog.close();
    showToast("求職追蹤已更新", "success");
    await loadApplications();
    reloadButton.focus();
  } catch (error) {
    editError.textContent = `儲存失敗：${error.message}`;
  } finally {
    isSaving = false;
    editForm.setAttribute("aria-busy", "false");
    document.getElementById("edit-fields").disabled = false;
    editSave.disabled = false;
    editCancel.disabled = false;
    editSave.textContent = "儲存";
  }
});


content.addEventListener("change", async event => {
  const select = event.target.closest("select[data-status-id]");
  if (!select) return;
  const row = applications.find(item => String(item.id) === select.dataset.statusId);
  if (!row) return;
  if (isSaving || isLoading) {
    select.value = row.status;
    return;
  }
  const nextStatus = select.value;
  if (nextStatus === row.status || !statusLabels.has(nextStatus)) return;
  isSaving = true;
  select.disabled = true;
  const buttons = [reloadButton, previousButton, nextButton];
  const disabledStates = buttons.map(button => button.disabled);
  buttons.forEach(button => { button.disabled = true; });
  summary.textContent = "正在儲存狀態…";
  try {
    const result = await apiCall(`/applications/${row.id}`, {
      method: "PATCH", body: JSON.stringify({status: nextStatus}),
    });
    const oldColor = statusLabels.get(row.status)?.[1];
    if (oldColor) select.classList.remove(...oldColor.split(" "));
    row.status = result.data.status;
    select.value = row.status;
    select.classList.add(...statusLabels.get(row.status)[1].split(" "));
    summary.textContent = "投遞狀態已儲存";
    showToast("投遞狀態已更新", "success");
  } catch (error) {
    select.value = row.status;
    summary.textContent = "狀態儲存失敗，已恢復原本選項";
    showToast(`儲存失敗：${error.message}`, "error");
  } finally {
    isSaving = false;
    select.disabled = false;
    buttons.forEach((button, index) => { button.disabled = disabledStates[index]; });
  }
});

const deleteDialog = document.getElementById("delete-dialog");
const deleteForm = document.getElementById("delete-form");
const deleteCancel = document.getElementById("delete-cancel");
const deleteConfirm = document.getElementById("delete-confirm");
const deleteError = document.getElementById("delete-error");
let deleting = null;
let deleteTrigger = null;

content.addEventListener("click", event => {
  const button = event.target.closest("button[data-delete-id]");
  if (!button || isLoading || isSaving) return;
  const row = applications.find(item => String(item.id) === button.dataset.deleteId);
  if (!row) return;
  deleting = row;
  deleteTrigger = button;
  document.getElementById("delete-context").textContent =
    `紀錄 #${row.id} · ${row.company || "未提供公司"} · ${row.job_title || "未提供職稱"}`;
  deleteError.textContent = "";
  deleteDialog.showModal();
  deleteCancel.focus();
});

deleteCancel.addEventListener("click", () => {
  if (!isSaving) deleteDialog.close();
});
deleteDialog.addEventListener("cancel", event => {
  if (isSaving) event.preventDefault();
});
deleteDialog.addEventListener("close", () => {
  deleting = null;
  if (deleteTrigger?.isConnected) deleteTrigger.focus();
});

deleteForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (!deleting || isSaving) return;
  isSaving = true;
  deleteError.textContent = "";
  deleteForm.setAttribute("aria-busy", "true");
  deleteCancel.disabled = true;
  deleteConfirm.disabled = true;
  deleteConfirm.textContent = "刪除中…";
  try {
    const response = await fetch(`${API_BASE}/applications/${deleting.id}`, {method: "DELETE"});
    if (!response.ok && response.status !== 404) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === "string" ? error.detail : `HTTP ${response.status}`);
    }
    deleteDialog.close();
    showToast(response.status === 404 ? "這筆紀錄已不存在，已重新整理列表" : "求職追蹤已刪除", response.status === 404 ? "info" : "success");
    await loadApplications();
    reloadButton.focus();
  } catch (error) {
    deleteError.textContent = `刪除失敗：${error.message}`;
  } finally {
    isSaving = false;
    deleteForm.setAttribute("aria-busy", "false");
    deleteCancel.disabled = false;
    deleteConfirm.disabled = false;
    deleteConfirm.textContent = "刪除紀錄";
  }
});

loadApplications();

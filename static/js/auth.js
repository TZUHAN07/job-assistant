(() => {
  const pageScript = document.currentScript.dataset.page;
  const bar = document.createElement("div");
  bar.className = "max-w-5xl mx-auto px-6 pt-4 flex flex-wrap items-center justify-end gap-3 text-sm text-gray-600";
  bar.innerHTML = '<span id="auth-status" role="status">確認登入狀態中…</span><button id="auth-action" type="button" hidden class="text-indigo-700 underline">重試</button>';
  document.body.prepend(bar);
  const status = bar.querySelector("#auth-status");
  const button = bar.querySelector("#auth-action");
  let ready = false;

  async function logout() {
    button.disabled = true;
    try {
      await apiCall("/auth/logout", { method: "POST" });
      window.location.replace("/app/login.html");
    } catch (error) {
      status.textContent = `登出未完成：${error.message}`;
      button.disabled = false;
    }
  }

  async function initialize() {
    button.hidden = true;
    status.textContent = "確認登入狀態中…";
    try {
      const result = await apiCall("/auth/me", { cache: "no-store" });
      status.textContent = result.data.email;
      button.textContent = "登出";
      button.onclick = logout;
      button.hidden = false;
      // 確認登入後才載入頁面邏輯，避免未登入時同時發出多個資料請求。
      if (!ready) {
        ready = true;
        const script = document.createElement("script");
        script.src = pageScript;
        script.onerror = () => {
          status.textContent = "頁面載入失敗，請重新整理。";
        };
        document.body.appendChild(script);
      }
    } catch (error) {
      status.textContent = `無法確認登入狀態：${error.message}`;
      button.textContent = "重試";
      button.onclick = initialize;
      button.hidden = false;
    }
  }

  // 返回上一頁若使用瀏覽器快照，要重新驗證，不能直接沿用舊帳號畫面。
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) window.location.reload();
  });
  initialize();
})();

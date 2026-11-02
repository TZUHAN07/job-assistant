(() => {
  const form = document.getElementById("login-form");
  const button = document.getElementById("login-submit");
  const errorEl = document.getElementById("login-error");
  const password = document.getElementById("password");
  let pending = false;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (pending || !form.reportValidity()) return;
    pending = true;
    button.disabled = true;
    button.textContent = "登入中…";
    form.setAttribute("aria-busy", "true");
    errorEl.hidden = true;
    try {
      // 登入的 401 是帳密錯誤，必須留在表單提示，不能套用資料 API 的跳轉。
      const response = await fetch("/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: document.getElementById("email").value.trim(),
          password: password.value,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = response.status === 429 ? "嘗試次數過多，請稍後再登入。"
          : typeof data.detail === "string" ? data.detail
          : response.status === 422 ? "請確認 Email 與密碼格式。"
          : "登入失敗，請稍後再試。";
        throw new Error(message);
      }
      // JWT 由伺服器透過 HttpOnly Cookie 設定，JavaScript 不保存 token。
      window.location.replace("/app/index.html");
    } catch (error) {
      errorEl.textContent = error instanceof TypeError
        ? "無法連線至伺服器，請確認連線後再試。" : error.message;
      errorEl.hidden = false;
      password.focus();
    } finally {
      password.value = "";
      pending = false;
      button.disabled = false;
      button.textContent = "登入";
      form.setAttribute("aria-busy", "false");
    }
  });
})();

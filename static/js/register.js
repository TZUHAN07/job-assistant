(() => {
  const form = document.getElementById("register-form");
  const button = document.getElementById("register-submit");
  const errorEl = document.getElementById("register-error");
  const password = document.getElementById("password");
  let pending = false;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (pending || !form.reportValidity()) return;
    pending = true;
    button.disabled = true;
    button.textContent = "註冊中…";
    form.setAttribute("aria-busy", "true");
    errorEl.hidden = true;
    try {
     
      const response = await fetch("/auth/register", {
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
        const message = response.status === 429 ? "嘗試次數過多，請稍後再註冊。"
          : typeof data.detail === "string" ? data.detail
          : response.status === 422 ? "請確認 Email 與密碼格式。"
          : "註冊失敗，請稍後再試。";
        throw new Error(message);
      }
      
      window.location.replace("/app/login.html");
    } catch (error) {
      errorEl.textContent = error instanceof TypeError
        ? "無法連線至伺服器，請確認連線後再試。" : error.message;
      errorEl.hidden = false;
      password.focus();
    } finally {
      password.value = "";
      pending = false;
      button.disabled = false;
      button.textContent = "註冊";
      form.setAttribute("aria-busy", "false");
    }
  });
})();

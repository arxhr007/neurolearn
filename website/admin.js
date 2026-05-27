(() => {
const NC = window.NeuroConsole;
if (!NC) return;
const { login: apiLogin, setAuth, setStatus, setButtonBusy, getNextPath } = NC;

function initAdminLogin() {
  const form = document.getElementById("login-form");
  const button = document.getElementById("login-button");
  if (!form || !button) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = document.getElementById("admin-username").value.trim();
    const password = document.getElementById("admin-password").value.trim();
    setButtonBusy(button, true, "Signing in...");
    try {
      const data = await apiLogin("admin", username, password);
      setAuth("admin", data);
      setStatus("Signed in. Redirecting...", "success");
      window.location.href = getNextPath("admin-dashboard.html");
    } catch (err) {
      setStatus(String(err), "error", 8000);
    } finally {
      setButtonBusy(button, false);
    }
  });
}

window.addEventListener("DOMContentLoaded", initAdminLogin);
})();

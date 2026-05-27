(() => {
const NC = window.NeuroConsole;
if (!NC) return;
const { login: apiLogin, setAuth, setStatus, setButtonBusy, getNextPath } = NC;

function initTeacherLogin() {
  const form = document.getElementById("login-form");
  const button = document.getElementById("login-button");
  if (!form || !button) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = document.getElementById("teacher-username").value.trim();
    const password = document.getElementById("teacher-password").value.trim();
    setButtonBusy(button, true, "Signing in...");
    try {
      const data = await apiLogin("teacher", username, password);
      setAuth("teacher", data);
      setStatus("Signed in. Redirecting...", "success");
      window.location.href = getNextPath("teacher-dashboard.html");
    } catch (err) {
      setStatus(String(err), "error", 8000);
    } finally {
      setButtonBusy(button, false);
    }
  });
}

window.addEventListener("DOMContentLoaded", initTeacherLogin);
})();

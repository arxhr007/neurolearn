(() => {
const NC = window.NeuroConsole;
if (!NC) return;
const {
  apiRequest,
  requireAuth,
  clearAuth,
  setStatus,
  setButtonBusy,
} = NC;

let session = null;

function formatDate(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function renderTeachers(teachers) {
  const body = document.getElementById("teacher-table-body");
  if (!body) return;
  body.innerHTML = "";

  if (!teachers || teachers.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = `<td class="empty" colspan="5">No teachers found.</td>`;
    body.appendChild(row);
    return;
  }

  teachers.forEach((teacher) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${teacher.teacher_id}</td>
      <td>${teacher.username}</td>
      <td>${teacher.full_name || "--"}</td>
      <td>${teacher.is_active ? "Yes" : "No"}</td>
      <td>${formatDate(teacher.created_at)}</td>
    `;
    body.appendChild(row);
  });
}

async function refreshTeachers() {
  const data = await apiRequest("GET", "/api/admin/teachers", session.token);
  renderTeachers(data.teachers || []);
  setStatus("Teacher list updated.", "success");
}

function initAdminDashboard() {
  session = requireAuth("admin", "admin.html");
  if (!session) return;

  const signOut = document.getElementById("sign-out");
  const createForm = document.getElementById("create-teacher-form");
  const createButton = document.getElementById("teacher-create");
  const refreshButton = document.getElementById("teacher-refresh");

  if (signOut) {
    signOut.addEventListener("click", () => {
      clearAuth("admin");
      window.location.href = "admin.html";
    });
  }

  if (createForm) {
    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const username = document.getElementById("teacher-username").value.trim();
      const password = document.getElementById("teacher-password").value.trim();
      const fullName = document.getElementById("teacher-full-name").value.trim();
      setButtonBusy(createButton, true, "Creating...");
      try {
        await apiRequest("POST", "/api/admin/teachers", session.token, {
          username,
          password,
          full_name: fullName,
        });
        setStatus("Teacher created.", "success");
        await refreshTeachers();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(createButton, false);
      }
    });
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
      setButtonBusy(refreshButton, true, "Refreshing...");
      try {
        await refreshTeachers();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(refreshButton, false);
      }
    });
  }

  refreshTeachers().catch((err) => setStatus(String(err), "error", 8000));
}

window.addEventListener("DOMContentLoaded", initAdminDashboard);
})();

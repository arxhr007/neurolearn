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

function splitCsv(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderStudents(students) {
  const body = document.getElementById("student-table-body");
  if (!body) return;
  body.innerHTML = "";

  if (!students || students.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = `<td class="empty" colspan="5">No students found.</td>`;
    body.appendChild(row);
    return;
  }

  students.forEach((student) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${student.student_id}</td>
      <td>${student.username}</td>
      <td>${student.reading_age}</td>
      <td>${student.learning_style}</td>
      <td>${student.is_active ? "Yes" : "No"}</td>
    `;
    body.appendChild(row);
  });
}

async function refreshStudents() {
  const data = await apiRequest("GET", "/api/teacher/students", session.token);
  renderStudents(data.students || []);
  setStatus("Student list updated.", "success");
}

async function createStudent() {
  const studentId = document.getElementById("student-id").value.trim();
  const username = document.getElementById("student-username").value.trim();
  const password = document.getElementById("student-password").value.trim();
  const fullName = document.getElementById("student-name").value.trim();
  const readingAge = Number(document.getElementById("student-reading-age").value || 12);
  const learningStyle = document.getElementById("student-learning-style").value.trim();
  const interests = splitCsv(document.getElementById("student-interests").value);
  const neuro = splitCsv(document.getElementById("student-neuro").value);

  await apiRequest("POST", "/api/teacher/students", session.token, {
    student_id: studentId,
    username,
    password,
    full_name: fullName,
    age: 10,
    reading_age: readingAge,
    learning_style: learningStyle,
    interests,
    neuro_profile: neuro,
  });
  document.getElementById("goal-student-id").value = studentId;
  setStatus("Student created.", "success");
  await refreshStudents();
}

async function updateStudent() {
  const studentId = document.getElementById("student-id").value.trim();
  const fullName = document.getElementById("student-name").value.trim();
  const readingAge = Number(document.getElementById("student-reading-age").value || 12);
  const learningStyle = document.getElementById("student-learning-style").value.trim();
  const interests = splitCsv(document.getElementById("student-interests").value);
  const neuro = splitCsv(document.getElementById("student-neuro").value);

  await apiRequest(
    "PUT",
    `/api/teacher/students/${encodeURIComponent(studentId)}`,
    session.token,
    {
      full_name: fullName,
      reading_age: readingAge,
      learning_style: learningStyle,
      interests,
      neuro_profile: neuro,
    }
  );
  setStatus("Student updated.", "success");
  await refreshStudents();
}

async function assignGoal() {
  const studentId = document.getElementById("goal-student-id").value.trim();
  const goalText = document.getElementById("goal-text").value.trim();
  await apiRequest(
    "POST",
    `/api/teacher/students/${encodeURIComponent(studentId)}/goals`,
    session.token,
    { goal_text: goalText }
  );
  setStatus("Goal assigned.", "success");
}

function initTeacherDashboard() {
  session = requireAuth("teacher", "teacher.html");
  if (!session) return;

  const signOut = document.getElementById("sign-out");
  const studentForm = document.getElementById("student-form");
  const updateButton = document.getElementById("student-update");
  const goalForm = document.getElementById("goal-form");
  const refreshButton = document.getElementById("student-refresh");
  const studentIdField = document.getElementById("student-id");
  const goalStudentField = document.getElementById("goal-student-id");

  if (signOut) {
    signOut.addEventListener("click", () => {
      clearAuth("teacher");
      window.location.href = "teacher.html";
    });
  }

  if (studentForm) {
    studentForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const createButton = document.getElementById("student-create");
      setButtonBusy(createButton, true, "Creating...");
      try {
        await createStudent();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(createButton, false);
      }
    });
  }

  if (updateButton) {
    updateButton.addEventListener("click", async () => {
      setButtonBusy(updateButton, true, "Updating...");
      try {
        await updateStudent();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(updateButton, false);
      }
    });
  }

  if (goalForm) {
    goalForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const goalButton = document.getElementById("goal-set");
      setButtonBusy(goalButton, true, "Saving...");
      try {
        await assignGoal();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(goalButton, false);
      }
    });
  }

  if (studentIdField && goalStudentField) {
    studentIdField.addEventListener("input", (event) => {
      goalStudentField.value = event.target.value.trim();
    });
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
      setButtonBusy(refreshButton, true, "Refreshing...");
      try {
        await refreshStudents();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(refreshButton, false);
      }
    });
  }

  refreshStudents().catch((err) => setStatus(String(err), "error", 8000));
}

window.addEventListener("DOMContentLoaded", initTeacherDashboard);
})();

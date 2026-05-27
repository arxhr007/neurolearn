(() => {
const NC = window.NeuroConsole;
if (!NC) return;
const {
  apiRequest,
  requireAuth,
  clearAuth,
  setStatus,
  setButtonBusy,
  newConversationId,
} = NC;

let session = null;

const chatState = {
  conversationId: "",
  turnId: "",
  checkHint: "",
};

function renderMessage(role, text, sources) {
  const log = document.getElementById("chat-window");
  if (!log) return;
  const bubble = document.createElement("div");
  bubble.className = `chat-message ${role}`;
  bubble.textContent = text;
  if (sources && sources.length) {
    const sourceLine = document.createElement("div");
    sourceLine.className = "chat-source";
    sourceLine.textContent = sources.map((source) => `${source.source} p.${source.page}`).join(" | ");
    bubble.appendChild(sourceLine);
  }
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

function resetConversation() {
  chatState.conversationId = newConversationId();
  chatState.turnId = "";
  chatState.checkHint = "";
  document.getElementById("conversation-id").value = chatState.conversationId;
  document.getElementById("check-question").textContent = "No check question yet.";
  const log = document.getElementById("chat-window");
  if (log) {
    log.textContent = "";
  }
}

async function askTutor() {
  const studentId = document.getElementById("student-session-id").value.trim();
  const question = document.getElementById("question-text").value.trim();
  if (!studentId || !question) {
    setStatus("Student ID and question are required.", "warning");
    return;
  }

  if (!chatState.conversationId) {
    chatState.conversationId = newConversationId();
    document.getElementById("conversation-id").value = chatState.conversationId;
  }

  renderMessage("student", question);

  const data = await apiRequest("POST", "/api/tutor/question", session.token, {
    student_id: studentId,
    conversation_id: chatState.conversationId,
    question,
    context: {},
  });

  chatState.turnId = data.turn_id || "";
  chatState.checkHint = data.check_answer_hint || "";
  document.getElementById("check-question").textContent = data.check_question || "No check question yet.";

  renderMessage("tutor", data.answer || "No answer returned.", data.sources || []);
  setStatus("Tutor response received.", "success");
}

async function answerCheck() {
  const studentId = document.getElementById("student-session-id").value.trim();
  const answer = document.getElementById("answer-text").value.trim();
  if (!studentId || !answer) {
    setStatus("Student ID and answer are required.", "warning");
    return;
  }
  if (!chatState.turnId || !chatState.conversationId) {
    setStatus("Ask a question first to get a turn ID.", "warning");
    return;
  }

  renderMessage("student", answer);

  const data = await apiRequest("POST", "/api/tutor/answer", session.token, {
    student_id: studentId,
    conversation_id: chatState.conversationId,
    turn_id: chatState.turnId,
    student_answer: answer,
    check_answer_hint: chatState.checkHint || undefined,
  });

  const feedback = data.feedback || data.remediation || "Answer submitted.";
  renderMessage("tutor", feedback);
  setStatus("Answer evaluated.", "success");
}

function initStudentDashboard() {
  session = requireAuth("student", "student.html");
  if (!session) return;

  const signOut = document.getElementById("sign-out");
  const sessionForm = document.getElementById("session-form");
  const questionForm = document.getElementById("question-form");
  const answerForm = document.getElementById("answer-form");
  const newConversationBtn = document.getElementById("new-conversation");
  const conversationField = document.getElementById("conversation-id");
  const studentIdField = document.getElementById("student-session-id");
  const questionButton = document.getElementById("question-send");
  const answerButton = document.getElementById("answer-send");

  if (session?.user?.student_id) {
    studentIdField.value = session.user.student_id;
  }

  if (signOut) {
    signOut.addEventListener("click", () => {
      clearAuth("student");
      window.location.href = "student.html";
    });
  }

  if (sessionForm) {
    sessionForm.addEventListener("submit", (event) => {
      event.preventDefault();
    });
  }

  if (conversationField) {
    conversationField.addEventListener("input", (event) => {
      chatState.conversationId = event.target.value.trim();
    });
  }

  if (newConversationBtn) {
    newConversationBtn.addEventListener("click", () => {
      resetConversation();
      setStatus("New conversation started.", "info");
    });
  }

  if (questionForm) {
    questionForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      setButtonBusy(questionButton, true, "Sending...");
      try {
        await askTutor();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(questionButton, false);
      }
    });
  }

  if (answerForm) {
    answerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      setButtonBusy(answerButton, true, "Submitting...");
      try {
        await answerCheck();
      } catch (err) {
        setStatus(String(err), "error", 8000);
      } finally {
        setButtonBusy(answerButton, false);
      }
    });
  }

  if (!chatState.conversationId) {
    resetConversation();
  }
}

window.addEventListener("DOMContentLoaded", initStudentDashboard);
})();

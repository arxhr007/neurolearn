const chatLayout = document.querySelector(".chat-layout");

if (chatLayout) {
  const studentId = chatLayout.dataset.studentId;
  const messagesEl = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const checkForm = document.getElementById("check-form");
  const checkInput = document.getElementById("check-input");
  const checkQuestion = document.getElementById("check-question");

  let conversationId = "";
  let lastTurnId = "";
  let lastCheckHint = "";

  if (!studentId) {
    addMessage("tutor", "Missing student ID for this session.");
  }

  function stripMarkdown(text) {
    return text.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1");
  }

  function addMessage(role, text) {
    if (!messagesEl) return;
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;
    bubble.textContent = role === "tutor" ? stripMarkdown(text) : text;
    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function makeConversationId() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  async function getToken() {
    const resp = await fetch("/auth/session-token");
    if (!resp.ok) {
      throw new Error("Unable to fetch session token");
    }
    const data = await resp.json();
    return data.access_token;
  }

  async function sendQuestion(text) {
    const token = await getToken();
    if (!conversationId) {
      conversationId = makeConversationId();
    }
    const payload = {
      student_id: studentId,
      conversation_id: conversationId,
      question: text,
      context: {},
    };
    const resp = await fetch("/api/tutor/question", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || "Tutor request failed");
    }
    lastTurnId = data.turn_id;
    if (data.check_question) {
      lastCheckHint = data.check_answer_hint || "";
      checkQuestion.textContent = data.check_question;
    }
    addMessage("tutor", data.answer || "No answer returned.");
  }

  async function sendAnswer(text) {
    const token = await getToken();
    const payload = {
      student_id: studentId,
      conversation_id: conversationId,
      turn_id: lastTurnId,
      student_answer: text,
      check_answer_hint: lastCheckHint || undefined,
    };
    const resp = await fetch("/api/tutor/answer", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || "Answer evaluation failed");
    }
    addMessage("tutor", data.feedback || "Thanks!" );
  }

  if (chatForm) {
    chatForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = chatInput.value.trim();
      if (!text || !studentId) return;
      addMessage("student", text);
      chatInput.value = "";
      try {
        await sendQuestion(text);
      } catch (err) {
        addMessage("tutor", String(err));
      }
    });
  }

  if (checkForm) {
    checkForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = checkInput.value.trim();
      if (!text) return;
      addMessage("student", text);
      checkInput.value = "";
      try {
        await sendAnswer(text);
      } catch (err) {
        addMessage("tutor", String(err));
      }
    });
  }
}

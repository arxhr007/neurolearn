const storageKeys = {
  baseUrl: "neurolearn.baseUrl",
  token: (role) => `neurolearn.token.${role}`,
  user: (role) => `neurolearn.user.${role}`,
};

function normalizeBaseUrl(value) {
  if (!value) return "http://localhost:8000";
  return value.trim().replace(/\/+$/, "");
}

function getBaseUrl() {
  const stored = localStorage.getItem(storageKeys.baseUrl);
  return normalizeBaseUrl(stored || "http://localhost:8000");
}

function setBaseUrl(value) {
  const normalized = normalizeBaseUrl(value);
  localStorage.setItem(storageKeys.baseUrl, normalized);
  return normalized;
}

function getToken(role) {
  return localStorage.getItem(storageKeys.token(role)) || "";
}

function setToken(role, token) {
  const safe = token || "";
  localStorage.setItem(storageKeys.token(role), safe);
  updateAuthView(role);
}

function clearToken(role) {
  localStorage.removeItem(storageKeys.token(role));
  updateAuthView(role);
}

function getUser(role) {
  const raw = localStorage.getItem(storageKeys.user(role));
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function setUser(role, user) {
  if (user) {
    localStorage.setItem(storageKeys.user(role), JSON.stringify(user));
  } else {
    localStorage.removeItem(storageKeys.user(role));
  }
  updateAuthView(role);
}

function setAuth(role, data) {
  setToken(role, data.access_token || "");
  setUser(role, data.user || null);
}

function clearAuth(role) {
  clearToken(role);
  setUser(role, null);
}

function updateAuthView(role) {
  const indicator = document.getElementById("auth-indicator");
  if (!indicator) return;
  const token = getToken(role);
  const user = getUser(role);
  indicator.textContent = token
    ? `Signed in as ${user?.email || user?.name || role}`
    : "Not signed in";
}

function requireAuth(role, loginPath) {
  const token = getToken(role);
  if (!token) {
    const current = window.location.pathname.split("/").pop() || "";
    const next = current ? `?next=${encodeURIComponent(current)}` : "";
    window.location.href = `${loginPath}${next}`;
    return null;
  }
  updateAuthView(role);
  return { token, user: getUser(role) };
}

function getNextPath(defaultPath) {
  const params = new URLSearchParams(window.location.search);
  const next = params.get("next");
  if (next && next.endsWith(".html")) {
    return next;
  }
  return defaultPath || "index.html";
}

function setStatus(message, tone = "info", timeoutMs = 5000) {
  const banner = document.getElementById("status-banner");
  if (!banner) return;
  banner.textContent = message;
  banner.dataset.tone = tone;
  banner.classList.remove("is-hidden");
  if (timeoutMs > 0) {
    window.setTimeout(() => {
      if (banner.textContent === message) {
        banner.classList.add("is-hidden");
      }
    }, timeoutMs);
  }
}

function setButtonBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = label || "Working...";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
  }
}

async function apiRequest(method, path, token, body) {
  const url = `${getBaseUrl()}${path}`;
  const headers = {
    Accept: "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const resp = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await resp.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!resp.ok) {
    const detail = data.detail ? data.detail : resp.statusText;
    throw new Error(`${resp.status} ${detail}`);
  }
  return data;
}

async function login(role, username, password) {
  return apiRequest("POST", "/api/auth/login", "", {
    email: username,
    password,
    role,
  });
}

function newConversationId() {
  if (window.crypto && window.crypto.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function checkHealth() {
  const statusEl = document.getElementById("health-status");
  try {
    const data = await apiRequest("GET", "/api/health");
    if (statusEl) {
      statusEl.textContent = `Status: ${data.status || "unknown"}`;
    }
  } catch {
    if (statusEl) {
      statusEl.textContent = "Status: error";
    }
  }
}

function initBaseUrlControls() {
  const input = document.getElementById("base-url");
  const healthBtn = document.getElementById("health-btn");

  if (input) {
    input.value = getBaseUrl();
    input.addEventListener("change", () => {
      const value = setBaseUrl(input.value);
      input.value = value;
      setStatus("Base URL updated.", "success");
    });
  }

  if (healthBtn) {
    healthBtn.addEventListener("click", () => {
      checkHealth().then(() => setStatus("Health check complete.", "info"));
    });
  }

  if (document.getElementById("health-status")) {
    checkHealth();
  }
}

window.NeuroConsole = {
  getBaseUrl,
  setBaseUrl,
  getToken,
  setToken,
  clearToken,
  getUser,
  setUser,
  setAuth,
  clearAuth,
  updateAuthView,
  requireAuth,
  getNextPath,
  setStatus,
  setButtonBusy,
  apiRequest,
  login,
  newConversationId,
  initBaseUrlControls,
  checkHealth,
};

window.addEventListener("DOMContentLoaded", () => {
  initBaseUrlControls();
});

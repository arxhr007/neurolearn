(() => {
const NC = window.NeuroConsole;
if (!NC) return;
const { apiRequest, requireAuth, clearAuth, setStatus, setButtonBusy } = NC;

let session = null;
let curriculaData = null;
let selectedCurriculum = null;
let selectedModule = null;
let selectedActivity = null;

function showStep(id) {
  document.querySelectorAll(".story-step").forEach(el => el.classList.remove("is-active"));
  const step = document.getElementById(id);
  if (step) step.classList.add("is-active");
}

function renderCurricula(data) {
  const list = document.getElementById("curricula-list");
  if (!data.length) {
    list.innerHTML = '<p class="status">No curricula available.</p>';
    return;
  }
  list.innerHTML = data.map(c => `
    <div class="sel-card" data-name="${c.name}">
      <strong>${c.title}</strong>
      <div style="font-size: 0.85rem; color: var(--muted);">${c.module_count} module(s)</div>
    </div>
  `).join("");
  list.querySelectorAll(".sel-card").forEach(el => {
    el.addEventListener("click", () => onSelectCurriculum(el.dataset.name));
  });
}

async function loadCurricula() {
  setStatus("Loading curricula...", "info");
  const data = await apiRequest("GET", "/api/story/curricula", session.token);
  curriculaData = data.curricula || [];
  renderCurricula(curriculaData);
  setStatus(`Loaded ${curriculaData.length} curriculum/curricula.`, "success");
}

async function onSelectCurriculum(name) {
  selectedCurriculum = name;
  selectedModule = null;
  selectedActivity = null;
  showStep("step-placeholders");
  document.querySelector("#curricula-list .is-selected")?.classList.remove("is-selected");
  document.querySelector(`#curricula-list [data-name="${name}"]`)?.classList.add("is-selected");
  document.getElementById("modules-list").innerHTML = '<p class="status">Loading modules...</p>';
  document.getElementById("activities-list").innerHTML = '<p class="status">Select a module first.</p>';

  const data = await apiRequest("GET", `/api/story/curricula/${name}`, session.token);
  curriculaData = data;
  const modules = data.modules || [];
  const list = document.getElementById("modules-list");
  if (!modules.length) {
    list.innerHTML = '<p class="status">No modules in this curriculum.</p>';
    return;
  }
  list.innerHTML = modules.map(m => `
    <div class="sel-card" data-number="${m.module_number}">
      <strong>Module ${m.module_number}: ${m.module_title}</strong>
      <div style="font-size: 0.85rem; color: var(--muted);">${m.activities.length} activity/activities</div>
    </div>
  `).join("");
  list.querySelectorAll(".sel-card").forEach(el => {
    el.addEventListener("click", () => onSelectModule(parseInt(el.dataset.number)));
  });
}

function onSelectModule(moduleNumber) {
  selectedModule = moduleNumber;
  selectedActivity = null;
  document.querySelector("#modules-list .is-selected")?.classList.remove("is-selected");
  document.querySelector(`#modules-list [data-number="${moduleNumber}"]`)?.classList.add("is-selected");

  const module = curriculaData.modules.find(m => m.module_number === moduleNumber);
  const activities = module ? module.activities : [];
  const list = document.getElementById("activities-list");
  if (!activities.length) {
    list.innerHTML = '<p class="status">No activities in this module.</p>';
    return;
  }
  list.innerHTML = activities.map(a => `
    <div class="sel-card" data-id="${a.activity_id}">
      <strong>${a.activity_name}</strong>
      <div style="font-size: 0.85rem; color: var(--muted);">${a.story_theme || ''}</div>
    </div>
  `).join("");
  list.querySelectorAll(".sel-card").forEach(el => {
    el.addEventListener("click", () => onSelectActivity(el.dataset.id));
  });
}

function onSelectActivity(activityId) {
  selectedActivity = activityId;
  document.querySelector("#activities-list .is-selected")?.classList.remove("is-selected");
  document.querySelector(`#activities-list [data-id="${activityId}"]`)?.classList.add("is-selected");

  const module = curriculaData.modules.find(m => m.module_number === selectedModule);
  const activity = module ? module.activities.find(a => a.activity_id === activityId) : null;
  if (!activity) return;

  const placeholders = activity.placeholder_variables || [];
  const container = document.getElementById("placeholder-fields");
  if (!placeholders.length) {
    container.innerHTML = '<p class="status">No placeholders to fill.</p>';
  } else {
    container.innerHTML = placeholders.map(v => {
      const label = v.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
      return `
        <div class="field">
          <label for="ph-${v}">${label}</label>
          <input id="ph-${v}" type="text" placeholder="Enter ${label.toLowerCase()}" />
        </div>
      `;
    }).join("");
  }
  showStep("step-placeholders");
}

async function generateStory(event) {
  event.preventDefault();
  const module = curriculaData.modules.find(m => m.module_number === selectedModule);
  const activity = module ? module.activities.find(a => a.activity_id === selectedActivity) : null;
  if (!activity) return;

  const placeholders = activity.placeholder_variables || [];
  const values = {};
  placeholders.forEach(v => {
    const input = document.getElementById(`ph-${v}`);
    values[v] = input ? input.value.trim() || `[${v}]` : `[${v}]`;
  });

  const btn = document.getElementById("generate-btn");
  setButtonBusy(btn, true, "Generating...");
  setStatus("Generating story...", "info");

  try {
    const result = await apiRequest("POST", "/api/story/generate", session.token, {
      curriculum: selectedCurriculum,
      module_number: selectedModule,
      activity_id: selectedActivity,
      placeholder_values: values,
    });

    const meta = document.getElementById("story-meta");
    meta.textContent = `${result.curriculum_title} › ${result.module_title} › ${result.activity.name}`;

    const output = document.getElementById("story-output");
    output.textContent = result.story || "No story was generated.";
    showStep("step-result");
    setStatus("Story generated successfully.", "success");
  } catch (err) {
    setStatus(String(err), "error", 8000);
  } finally {
    setButtonBusy(btn, false);
  }
}

function resetAll() {
  selectedCurriculum = null;
  selectedModule = null;
  selectedActivity = null;
  curriculaData = null;
  document.querySelectorAll(".is-selected").forEach(el => el.classList.remove("is-selected"));
  document.getElementById("modules-list").innerHTML = '<p class="status">Select a curriculum first.</p>';
  document.getElementById("activities-list").innerHTML = '<p class="status">Select a module first.</p>';
  document.getElementById("placeholder-fields").innerHTML = "";
  document.getElementById("story-output").textContent = "Story will appear here after generation.";
  document.getElementById("story-meta").textContent = "";
  showStep("step-placeholders");
  loadCurricula();
}

function initStoryPage() {
  session = requireAuth("student", "student.html");
  if (!session) return;

  const signOut = document.getElementById("sign-out");
  if (signOut) {
    signOut.addEventListener("click", () => {
      clearAuth("student");
      window.location.href = "student.html";
    });
  }

  const form = document.getElementById("placeholder-form");
  if (form) {
    form.addEventListener("submit", generateStory);
  }

  const resetBtn = document.getElementById("reset-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", resetAll);
  }

  loadCurricula();
}

window.addEventListener("DOMContentLoaded", initStoryPage);
})();

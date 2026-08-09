function renderLineChart(canvasId, label, labels, data) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  new Chart(el, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label,
          data,
          borderColor: "#2563eb",
          backgroundColor: "rgba(37, 99, 235, 0.2)",
          tension: 0.35,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function renderBarChart(canvasId, label, labels, data) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  new Chart(el, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label,
          data,
          backgroundColor: "rgba(37, 99, 235, 0.6)",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

window.NeuroCharts = {
  renderAdminCharts() {
    renderLineChart("admin-engagement-chart", "Engagement", ["Mon", "Tue", "Wed", "Thu", "Fri"], [4, 6, 3, 8, 5]);
  },
  renderAdminAnalytics() {
    renderLineChart("admin-mastery-chart", "Mastery", ["W1", "W2", "W3", "W4"], [12, 18, 22, 30]);
    renderBarChart("admin-usage-chart", "AI Usage", ["Mon", "Tue", "Wed", "Thu"], [18, 25, 22, 30]);
  },
  renderTeacherCharts() {
    renderLineChart("teacher-progress-chart", "Progress", ["Week 1", "Week 2", "Week 3"], [2, 5, 7]);
  },
  renderTeacherAnalytics() {
    renderLineChart("teacher-mastery-chart", "Mastery", ["Mon", "Tue", "Wed"], [6, 8, 7]);
    renderBarChart("teacher-engagement-chart", "Engagement", ["Mon", "Tue", "Wed"], [12, 9, 14]);
  },
  renderStudentDashboard() {
    renderLineChart("student-progress-chart", "Progress", ["Week 1", "Week 2", "Week 3"], [1, 4, 6]);
  },
  renderStudentProgress() {
    renderLineChart("student-mastery-chart", "Mastery", ["Mon", "Tue", "Wed"], [2, 3, 4]);
    renderBarChart("student-weakness-chart", "Weak Concepts", ["Health", "Math", "Science"], [3, 1, 2]);
  },
  renderStudentMastery() {
    renderLineChart("teacher-student-mastery", "Mastery", ["Attempt 1", "Attempt 2", "Attempt 3"], [0.4, 0.6, 0.8]);
  },
};

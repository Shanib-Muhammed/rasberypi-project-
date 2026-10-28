// Local mode: this page is served by the Raspberry Pi itself (server.py).
// No Supabase, no CDN, no internet needed.
const $ = (selector) => document.querySelector(selector);
const reportsElement = $("#reports");
const messageElement = $("#message");
const totalElement = $("#total-count");
const latestElement = $("#latest-date");
const refreshButton = $("#refresh-button");
const modal = $("#photo-modal");
const modalImage = $("#modal-image");
const modalCaption = $("#modal-caption");
const modalClose = $("#modal-close");
const loginForm = $("#login-form");
const passwordInput = $("#admin-password");
const authStatus = $("#auth-status");
const logoutButton = $("#logout-button");

const STORAGE_KEY = "varodeAdmin";
const REFRESH_MS = 5000;
let adminPassword = "";
try { adminPassword = sessionStorage.getItem(STORAGE_KEY) || ""; } catch {}
let lastKey = null;

function saveAdmin(value) {
  adminPassword = value;
  try { value ? sessionStorage.setItem(STORAGE_KEY, value) : sessionStorage.removeItem(STORAGE_KEY); } catch {}
  updateAuthUI();
}

function updateAuthUI() {
  const signedIn = Boolean(adminPassword);
  loginForm.hidden = signedIn;
  logoutButton.hidden = !signedIn;
  authStatus.textContent = signedIn
    ? "Signed in as administrator. Report deletion is enabled."
    : "Viewing reports is public. Enter the administrator password only to manage reports.";
  document.querySelectorAll(".delete-button").forEach((button) => { button.hidden = !signedIn; });
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authStatus.textContent = "Checking password…";
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: passwordInput.value })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) throw new Error(result.error || `Request failed (${response.status})`);
    saveAdmin(passwordInput.value);
    passwordInput.value = "";
  } catch (error) {
    authStatus.textContent = `Login failed: ${error.message}`;
  }
});

logoutButton.addEventListener("click", () => saveAdmin(""));

function formatDate(value) {
  if (!value) return "Time not supplied";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function openPhoto(url, report) {
  modalImage.src = url;
  modalImage.alt = `Photo for report #${report.id}`;
  modalCaption.textContent = `Report #${report.id} · ${formatDate(report.timestamp)}`;
  modal.showModal();
}

modalClose.addEventListener("click", () => modal.close());
modal.addEventListener("click", (event) => { if (event.target === modal) modal.close(); });

function makeReportCard(report) {
  const card = document.createElement("article");
  card.className = "report-card";
  const photoUrl = `/photos/${encodeURIComponent(report.photo)}`;

  const imageButton = document.createElement("button");
  imageButton.className = "image-button";
  imageButton.type = "button";
  imageButton.setAttribute("aria-label", `Open photo for report ${report.id}`);
  const image = document.createElement("img");
  image.className = "report-image";
  image.src = photoUrl;
  image.alt = `Photo for report #${report.id}`;
  image.loading = "lazy";
  image.onerror = () => { image.removeAttribute("src"); image.alt = "Photo unavailable"; };
  imageButton.append(image);
  imageButton.addEventListener("click", () => openPhoto(photoUrl, report));

  const body = document.createElement("div");
  body.className = "report-body";
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = report.detection || "CRACK DETECTED";
  const title = document.createElement("h3");
  title.textContent = `Report #${report.id}`;
  const time = document.createElement("p");
  time.className = "report-time";
  time.textContent = formatDate(report.timestamp);
  const coords = document.createElement("div");
  coords.className = "coords";
  coords.textContent = `Latitude: ${report.latitude} · Longitude: ${report.longitude}`;
  const map = document.createElement("a");
  map.className = "map-link";
  map.href = `https://www.google.com/maps?q=${encodeURIComponent(report.latitude)},${encodeURIComponent(report.longitude)}`;
  map.target = "_blank";
  map.rel = "noopener noreferrer";
  map.textContent = "Open location in Google Maps ↗ (needs internet)";

  const actions = document.createElement("div");
  actions.className = "report-actions";
  const deleteButton = document.createElement("button");
  deleteButton.className = "delete-button";
  deleteButton.type = "button";
  deleteButton.textContent = "Delete report";
  deleteButton.hidden = !adminPassword;
  deleteButton.addEventListener("click", async () => {
    if (!window.confirm(`Delete report #${report.id} and its photo? This cannot be undone.`)) return;
    deleteButton.disabled = true;
    deleteButton.textContent = "Deleting…";
    try {
      const response = await fetch("/api/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Password": adminPassword },
        body: JSON.stringify({ id: report.id })
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) saveAdmin("");
      if (!response.ok || !result.success) throw new Error(result.error || `Request failed (${response.status})`);
      await loadReports(true);
      messageElement.textContent = `Report #${report.id} and its photo were deleted.`;
    } catch (error) {
      messageElement.textContent = `Delete failed: ${error.message}`;
      deleteButton.disabled = false;
      deleteButton.textContent = "Delete report";
    }
  });

  actions.append(deleteButton);
  body.append(tag, title, time, coords, map, actions);
  card.append(imageButton, body);
  return card;
}

async function loadReports(force = false) {
  let payload;
  try {
    const response = await fetch("/api/reports", { cache: "no-store" });
    if (!response.ok) throw new Error(`Status ${response.status}`);
    payload = await response.json();
  } catch {
    messageElement.textContent = "Cannot reach the Raspberry Pi. Check that it is on the same Wi-Fi/hotspot and server.py is running.";
    return;
  }

  const reports = payload.reports || [];
  totalElement.textContent = String(payload.total ?? reports.length);
  latestElement.textContent = reports.length ? formatDate(reports[0].timestamp) : "No reports yet";
  messageElement.textContent = reports.length
    ? `Showing ${reports.length} recent report(s). Click a photo to open it full size.`
    : "Connected to the Raspberry Pi. No reports yet.";

  // Only redraw when something changed, so the page does not flicker.
  const key = reports.map((report) => report.id).join(",");
  if (!force && key === lastKey) return;
  lastKey = key;

  reportsElement.replaceChildren();
  if (!reports.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No reports yet. When the robot sees a red marking, it will appear here.";
    reportsElement.append(empty);
    return;
  }
  for (const report of reports) reportsElement.append(makeReportCard(report));
}

refreshButton.addEventListener("click", () => loadReports(true));
updateAuthUI();
loadReports(true);
window.setInterval(() => loadReports(), REFRESH_MS);

/**
 * SnapKey Remote Access Dashboard JS
 * 
 * In local dev, this points to http://127.0.0.1:8000.
 * After deploying your backend to Render, replace the fallback URL below
 * with your production Render backend URL.
 */
const API_BASE = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost"
  ? "http://127.0.0.1:8000"
  : "https://snapkey-backend.onrender.com"; // <-- Replace with your Render URL (e.g., https://snapkey-backend.onrender.com)

// Cache elements
const userNameInput = document.getElementById("user_name");
const userIdInput = document.getElementById("user_id");
const agentTokenInput = document.getElementById("agent_token");
const passwordInput = document.getElementById("password");

const saveBtn = document.getElementById("save-btn");
const connectBtn = document.getElementById("connect-btn");
const searchBox = document.getElementById("search-box");

const statusCard = document.getElementById("status-card");
const statusText = document.getElementById("status-text");

const usersListContainer = document.getElementById("users-list");
const agentsListContainer = document.getElementById("agents-list");

// Keep local memory of users for search filtering
let savedUsers = [];

/**
 * Updates the Connection Status card with a message and a severity class.
 * @param {string} message - Message to show
 * @param {'success'|'error'|'pending'|''} type - Style theme
 */
function setStatus(message, type) {
  statusText.textContent = message;
  statusCard.className = "status-box";
  if (type) {
    statusCard.classList.add(type);
  }
}

/**
 * Fetches saved users from backend and updates the list sidebar
 */
async function loadSavedUsers() {
  try {
    const res = await fetch(`${API_BASE}/api/users`);
    if (!res.ok) throw new Error("Backend response error");
    savedUsers = await res.json();
    renderUsersList(savedUsers);
  } catch (err) {
    console.error("Failed to load saved users:", err);
    usersListContainer.innerHTML = '<div class="user-item placeholder">Failed to load saved devices</div>';
  }
}

/**
 * Fetches currently connected agents from backend and updates the sidebar
 */
async function loadActiveAgents() {
  try {
    const res = await fetch(`${API_BASE}/api/agents`);
    if (!res.ok) throw new Error("Backend response error");
    const data = await res.json();
    const agents = data.connected_agents || [];
    renderAgentsList(agents);
  } catch (err) {
    console.error("Failed to load connected agents:", err);
    agentsListContainer.innerHTML = '<div class="agent-item placeholder">Failed to check agents</div>';
  }
}

/**
 * Renders the list of saved users to the sidebar
 * @param {Array} users 
 */
function renderUsersList(users) {
  if (!users || users.length === 0) {
    usersListContainer.innerHTML = '<div class="user-item placeholder">No saved devices found</div>';
    return;
  }

  usersListContainer.innerHTML = "";
  users.forEach(user => {
    const div = document.createElement("div");
    div.className = "user-item";
    div.innerHTML = `
      <span class="name">${escapeHTML(user.user_name)}</span>
      <span class="id-val">ID: ${escapeHTML(user.user_id)}</span>
    `;
    div.addEventListener("click", () => {
      populateForm(user.user_name, user.user_id);
      setStatus(`Loaded details for "${user.user_name}".`, "success");
    });
    usersListContainer.appendChild(div);
  });
}

/**
 * Renders the list of active agents to the sidebar
 * @param {Array<string>} agents 
 */
function renderAgentsList(agents) {
  if (!agents || agents.length === 0) {
    agentsListContainer.innerHTML = '<div class="agent-item placeholder">None online</div>';
    return;
  }

  agentsListContainer.innerHTML = "";
  agents.forEach(token => {
    const div = document.createElement("div");
    div.className = "agent-item";
    div.innerHTML = `
      <span class="status-dot"></span>
      <span class="token">${escapeHTML(token)}</span>
    `;
    agentsListContainer.appendChild(div);
  });
}

/**
 * Utility to escape html to prevent XSS
 */
function escapeHTML(str) {
  return String(str)
    .replace(/&/g, "\u0026amp;")
    .replace(/</g, "\u0026lt;")
    .replace(/>/g, "\u0026gt;")
    .replace(/"/g, "\u0026quot;")
    .replace(/'/g, "\u0026#039;");
}

/**
 * Fills the form with saved user parameters
 */
function populateForm(name, id) {
  userNameInput.value = name;
  userIdInput.value = id;
  passwordInput.value = ""; // Clear password for security, let them supply new if updating or leave blank
}

// ---------------------------------------------------------------------------
// Event Listeners
// ---------------------------------------------------------------------------

// Filter saved users list based on search bar
searchBox.addEventListener("input", (e) => {
  const query = e.target.value.toLowerCase().trim();
  const filtered = savedUsers.filter(user => 
    user.user_name.toLowerCase().includes(query) || 
    user.user_id.includes(query)
  );
  renderUsersList(filtered);
});

// Save Device Action
saveBtn.addEventListener("click", async () => {
  const userName = userNameInput.value.trim();
  const userId = userIdInput.value.trim().replace(/\s/g, "");
  const password = passwordInput.value;
  const agentToken = agentTokenInput.value.trim();

  if (!userName || !userId) {
    setStatus("Please enter both User Name and User ID to save.", "error");
    return;
  }

  if (!/^\d+$/.test(userId)) {
    setStatus("User ID (AnyDesk ID) must contain only numbers.", "error");
    return;
  }

  // Persist the agent token locally for convenience
  if (agentToken) {
    localStorage.setItem("snapkey_last_agent_token", agentToken);
  }

  saveBtn.disabled = true;
  setStatus("Saving device details...", "pending");

  try {
    const res = await fetch(`${API_BASE}/api/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_name: userName,
        user_id: userId,
        password: password || null
      })
    });

    const data = await res.json();

    if (!res.ok) {
      // Handle server-side errors (e.g., integrity constraint error)
      setStatus(data.detail || "Failed to save device information.", "error");
    } else {
      setStatus(`Successfully saved "${data.user_name}" (ID: ${data.user_id}) to database!`, "success");
      passwordInput.value = ""; // Clear password input
      loadSavedUsers(); // Refresh sidebar list
    }
  } catch (err) {
    setStatus(
      "Could not reach backend. Please ensure the central SnapKey server is running.",
      "error"
    );
  } finally {
    saveBtn.disabled = false;
  }
});

// Connect Action (Agent-based connect-request)
connectBtn.addEventListener("click", async () => {
  const userId = userIdInput.value.trim().replace(/\s/g, "");
  const agentToken = agentTokenInput.value.trim();

  if (!userId || !agentToken) {
    setStatus("Connect requires both AnyDesk User ID and Agent Token.", "error");
    return;
  }

  if (!/^\d+$/.test(userId)) {
    setStatus("User ID (AnyDesk ID) must contain only numbers.", "error");
    return;
  }

  // Persist agent token locally
  localStorage.setItem("snapkey_last_agent_token", agentToken);

  connectBtn.disabled = true;
  setStatus(`Sending dispatch request to agent "${agentToken}"...`, "pending");

  try {
    const res = await fetch(`${API_BASE}/api/connect-request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_token: agentToken,
        user_id: userId
      })
    });

    const data = await res.json();

    if (!res.ok) {
      setStatus(data.detail || "Failed to dispatch connection request.", "error");
    } else {
      setStatus(data.message || "Connection instructions sent successfully!", "success");
    }
  } catch (err) {
    setStatus(
      "Could not reach backend. Please ensure the central SnapKey server is running.",
      "error"
    );
  } finally {
    connectBtn.disabled = false;
  }
});

// Load persistent agent token and fetch data on launch
window.addEventListener("DOMContentLoaded", () => {
  const cachedToken = localStorage.getItem("snapkey_last_agent_token");
  if (cachedToken) {
    agentTokenInput.value = cachedToken;
  } else {
    agentTokenInput.value = "dev-agent-token";
  }

  // Initial loads
  loadSavedUsers();
  loadActiveAgents();

  // Periodic polling to keep dashboard live (every 7 seconds)
  setInterval(() => {
    loadSavedUsers();
    loadActiveAgents();
  }, 7000);
});

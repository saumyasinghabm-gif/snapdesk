/**
 * SnapKey Remote Access Dashboard JS
 * 
 * In local dev, this points to http://127.0.0.1:8000.
 * In production, this points at the Render backend defined in render.yaml.
 */
 const API_BASE = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost"
   ? "http://127.0.0.1:8000"
   : "https://snapdesk-backend.onrender.com";

// Fix double slash issue by ensuring proper URL construction
function buildApiUrl(path) {
  // Remove any trailing slashes from base and leading slashes from path
  const cleanBase = API_BASE.replace(/\/$/, '');
  const cleanPath = path.replace(/^\//, '');
  const result = `${cleanBase}/${cleanPath}`;

  // Additional safety check for Vercel/Render deployment issues
  // If we still have double slashes (e.g., from deployment base path), clean them up
  return result.replace(/([^:]\/)\/+/g, '$1');
}

// Cache elements
const userNameInput = document.getElementById("user_name");
const userIdInput = document.getElementById("user_id");
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
let activeAgents = [];
let selectedAgentId = "";

function selectSupportAgent(agentId, announce = true) {
  selectedAgentId = agentId;
  localStorage.setItem("snapkey_last_agent_id", agentId);
  renderAgentsList(activeAgents);
  if (announce) {
    setStatus(`Selected support agent "${agentId}".`, "success");
  }
}

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
    const res = await fetch(buildApiUrl("/api/users"));
    if (!res.ok) throw new Error("Backend response error");
    savedUsers = await res.json();
    renderUsersList(savedUsers);
  } catch (err) {
    console.error("Failed to load saved users:", err);
    // Only show error if we haven't successfully loaded users before
    // This prevents flickering between error states and successful loads
    if (!savedUsers || savedUsers.length === 0) {
      usersListContainer.innerHTML = '<div class="user-item placeholder">Failed to load saved devices</div>';
    }
    // If we had users before, keep showing them rather than showing error
    // This provides better user experience during temporary network issues
  }
}

/**
 * Fetches currently connected agents from backend and updates the sidebar
 */
async function loadActiveAgents() {
  try {
    const res = await fetch(buildApiUrl("/api/agents"));
    if (!res.ok) throw new Error("Backend response error");
    const data = await res.json();
    activeAgents = data.connected_agents || [];

    const cachedAgentId = localStorage.getItem("snapkey_last_agent_id");
    if (!selectedAgentId && cachedAgentId && activeAgents.includes(cachedAgentId)) {
      selectedAgentId = cachedAgentId;
    }

    if (!selectedAgentId && activeAgents.length === 1) {
      selectSupportAgent(activeAgents[0], false);
    } else {
      renderAgentsList(activeAgents);
    }
  } catch (err) {
    console.error("Failed to load connected agents:", err);
    // Only show error if we haven't successfully loaded agents before
    // This prevents flickering between error states and successful loads
    if (!agentsListContainer.querySelector('.agent-item:not(.placeholder)')) {
      agentsListContainer.innerHTML = '<div class="agent-item placeholder">Failed to check agents</div>';
    }
    // If we had agents before, keep showing them rather than showing error
    // This provides better user experience during temporary network issues
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
  agents.forEach(agentId => {
    const div = document.createElement("div");
    div.className = agentId === selectedAgentId ? "agent-item selected" : "agent-item";
    div.innerHTML = `
      <span class="status-dot"></span>
      <span class="token">${escapeHTML(agentId)}</span>
    `;
    div.addEventListener("click", () => {
      selectSupportAgent(agentId);
    });
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

  if (!userName || !userId) {
    setStatus("Please enter both User Name and User ID to save.", "error");
    return;
  }

  if (!/^\d+$/.test(userId)) {
    setStatus("User ID (AnyDesk ID) must contain only numbers.", "error");
    return;
  }

  saveBtn.disabled = true;
  setStatus("Saving device details...", "pending");

  try {
    const res = await fetch(buildApiUrl("/api/users"), {
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
  const agentId = selectedAgentId;

  if (!userId || !agentId) {
    setStatus("Select an online support agent once, then choose a saved device or enter an AnyDesk ID.", "error");
    return;
  }

  if (!/^\d+$/.test(userId)) {
    setStatus("User ID (AnyDesk ID) must contain only numbers.", "error");
    return;
  }

  connectBtn.disabled = true;
  setStatus(`Sending dispatch request to support agent "${agentId}"...`, "pending");

  try {
    const res = await fetch(buildApiUrl("/api/connect-request"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
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

// Load persistent agent selection and fetch data on launch
window.addEventListener("DOMContentLoaded", () => {
  const urlAgentId = new URLSearchParams(window.location.search).get("agent_id");
  if (urlAgentId) {
    selectedAgentId = urlAgentId.trim();
    localStorage.setItem("snapkey_last_agent_id", selectedAgentId);
  } else {
    selectedAgentId = localStorage.getItem("snapkey_last_agent_id") || "";
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

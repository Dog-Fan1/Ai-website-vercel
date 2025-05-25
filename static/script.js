const API_BASE = '';
let currentChatId = null;
let currentUsername = null;
let hasChatted = false;
let isAdmin = false;

function renderHistory(history) {
  const chatDiv = document.getElementById('chatHistory');
  chatDiv.innerHTML = '';
  if (!history || history.length === 0) {
    chatDiv.innerHTML = '<em>Start the conversation!</em>';
    return;
  }
  history.forEach(msg => {
    if (msg.role === "user") {
      chatDiv.innerHTML += `<div class="user-msg">You: ${marked.parse(msg.content)}</div>`;
    } else if (msg.role === "assistant") {
      chatDiv.innerHTML += `<div class="assistant-msg">AmberMind: ${marked.parse(msg.content)}</div>`;
    }
  });
  chatDiv.scrollTop = chatDiv.scrollHeight;
}

function renderChats(chats) {
  const chatList = document.getElementById('chatList');
  chatList.innerHTML = '';
  chats.forEach(chat => {
    const li = document.createElement('li');
    li.textContent = chat.title || "New Chat";
    li.className = chat.chat_id === currentChatId ? "selected" : "";
    li.onclick = () => selectChat(chat.chat_id);
    chatList.appendChild(li);
  });
}

function selectChat(chat_id) {
  currentChatId = chat_id;
  hasChatted = false;
  fetch(`${API_BASE}/history/${chat_id}`, {
    method: 'GET',
    credentials: 'include'
  })
  .then(r => r.json())
  .then(data => {
    renderHistory(data.history);
    updateChatList();
    document.getElementById('promptInput').disabled = false;
    document.getElementById('chatBtn').disabled = false;
    showGreeting();
  });
}

function updateChatList() {
  fetch(`${API_BASE}/chats`, {
    method: 'GET',
    credentials: 'include'
  })
  .then(r => r.json())
  .then(data => {
    if (data.chats) renderChats(data.chats);
  });
}

function showGreeting() {
  const header = document.getElementById('greetingHeader');
  if (currentUsername && !hasChatted) {
    header.textContent = `Hi ${currentUsername}!`;
    header.style.display = "block";
  }
}

function hideGreeting() {
  document.getElementById('greetingHeader').style.display = "none";
}

document.getElementById('signupBtn').onclick = function() {
  fetch(`${API_BASE}/signup`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      username: document.getElementById('signup-username').value,
      password: document.getElementById('signup-password').value
    }),
    credentials: 'include'
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById('signup-result').textContent = data.message || data.error;
    if (data.chat_id) {
      currentChatId = data.chat_id;
      currentUsername = document.getElementById('signup-username').value;
      updateChatList();
      selectChat(currentChatId);
      document.getElementById('logoutBtn').disabled = false;
      document.getElementById('newChatBtn').disabled = false;
      showGreeting();
    }
  });
};

document.getElementById('loginBtn').onclick = function() {
  fetch(`${API_BASE}/login`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      username: document.getElementById('login-username').value,
      password: document.getElementById('login-password').value
    }),
    credentials: 'include'
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById('login-result').textContent = data.message || data.error;
    if (data.chats && data.chats.length > 0) {
      currentChatId = data.chats[0].chat_id;
      currentUsername = document.getElementById('login-username').value;
      isAdmin = data.is_admin;
      renderChats(data.chats);
      selectChat(currentChatId);
      document.getElementById('logoutBtn').disabled = false;
      document.getElementById('newChatBtn').disabled = false;
      showGreeting();
      if (isAdmin) {
        showAdminTab();
      }
    }
  });
};

document.getElementById('chatBtn').onclick = function() {
  sendPrompt();
};

// Shift+Enter to send, Enter for newline
const promptInput = document.getElementById('promptInput');
promptInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') {
    if (e.shiftKey) {
      // Shift+Enter: send
      e.preventDefault();
      if (!promptInput.disabled && !document.getElementById('chatBtn').disabled) {
        sendPrompt();
      }
    } else {
      // Enter: newline
      // Let the default behavior happen (insert newline)
    }
  }
});

function sendPrompt() {
  const prompt = promptInput.value.trim();
  if (!currentChatId || !prompt) return;
  fetch(`${API_BASE}/chat/${currentChatId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({prompt}),
    credentials: 'include'
  })
  .then(r => r.json())
  .then(data => {
    hasChatted = true;
    hideGreeting();
    renderHistory(data.history);
    updateChatList();
    promptInput.value = '';
  });
}

document.getElementById('logoutBtn').onclick = function() {
  fetch(`${API_BASE}/logout`, {
    method: 'POST',
    credentials: 'include'
  }).then(r => r.json())
  .then(data => {
    document.getElementById('promptInput').disabled = true;
    document.getElementById('chatBtn').disabled = true;
    document.getElementById('logoutBtn').disabled = true;
    document.getElementById('newChatBtn').disabled = true;
    renderHistory([]);
    renderChats([]);
    currentChatId = null;
    currentUsername = null;
    hasChatted = false;
    isAdmin = false;
    document.getElementById('greetingHeader').textContent = "Welcome to AmberMind!";
    document.getElementById('greetingHeader').style.display = "block";
    document.getElementById('adminTab').style.display = "none";
  });
};

document.getElementById('newChatBtn').onclick = function() {
  fetch(`${API_BASE}/new_chat`, {
    method: 'POST',
    credentials: 'include'
  })
  .then(r => r.json())
  .then(data => {
    if (data.chat_id) {
      currentChatId = data.chat_id;
      hasChatted = false;
      updateChatList();
      selectChat(currentChatId);
      showGreeting();
    }
  });
};

function showAdminTab() {
  const adminTab = document.getElementById('adminTab');
  adminTab.style.display = "block";
  fetch(`${API_BASE}/admin`, {
    method: 'GET',
    credentials: 'include'
  })
  .then(r => r.json())
  .then(data => {
    if (data.users) {
      let html = "<b>Users:</b><ul>";
      data.users.forEach(u => {
        html += `<li>${u} (${data.chat_stats[u]} chats)</li>`;
      });
      html += "</ul>";
      document.getElementById('adminContent').innerHTML = html;
    } else {
      document.getElementById('adminContent').textContent = data.error || "No data";
    }
  });
}

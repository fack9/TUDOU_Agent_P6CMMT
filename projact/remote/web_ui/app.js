(function () {
  "use strict";

  var TOKEN_KEY = "tudou_remote_token";
  var $ = function (id) { return document.getElementById(id); };

  var pairScreen = $("pair-screen");
  var chatScreen = $("chat-screen");
  var pairCode = $("pair-code");
  var pairBtn = $("pair-btn");
  var pairError = $("pair-error");
  var messages = $("messages");
  var msgInput = $("msg-input");
  var sendBtn = $("send-btn");
  var statusDot = $("status-dot");
  var typing = $("typing-indicator");
  var unpairBtn = $("unpair-btn");

  var token = localStorage.getItem(TOKEN_KEY);

  // --- init ---

  if (token) {
    showChat();
    checkStatus();
  }

  // --- events ---

  pairBtn.addEventListener("click", doPair);
  pairCode.addEventListener("keydown", function (e) {
    if (e.key === "Enter") doPair();
  });

  sendBtn.addEventListener("click", doSend);
  msgInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") doSend();
  });

  unpairBtn.addEventListener("click", function () {
    api("POST", "/api/unpair").then(function () {
      localStorage.removeItem(TOKEN_KEY);
      token = null;
      showPair();
    });
  });

  // --- pairing ---

  function doPair() {
    var code = pairCode.value.trim();
    if (code.length !== 6) {
      pairError.textContent = "请输入6位配对码";
      return;
    }
    pairBtn.disabled = true;
    pairError.textContent = "";
    api("POST", "/api/pair", { code: code }).then(function (r) {
      return r.json();
    }).then(function (data) {
      if (data.ok) {
        token = data.token;
        localStorage.setItem(TOKEN_KEY, token);
        showChat();
      } else {
        pairError.textContent = data.error || "配对失败";
      }
    }).catch(function () {
      pairError.textContent = "连接失败，请检查网络";
    }).finally(function () {
      pairBtn.disabled = false;
    });
  }

  // --- chat ---

  function doSend() {
    var text = msgInput.value.trim();
    if (!text) return;
    if (!token) return;

    addMessage("me", text);
    msgInput.value = "";
    msgInput.focus();
    showTyping(true);
    sendBtn.disabled = true;

    api("POST", "/api/chat", { message: text }).then(function (r) {
      return r.json();
    }).then(function (data) {
      showTyping(false);
      sendBtn.disabled = false;
      if (data.ok) {
        addMessage("agent", data.message, data.tool_calls, data.duration_ms);
      } else {
        addMessage("agent", "Error: " + (data.error || "unknown"));
      }
    }).catch(function () {
      showTyping(false);
      sendBtn.disabled = false;
      addMessage("agent", "请求失败，Agent 可能离线");
    });
  }

  // --- UI helpers ---

  function addMessage(role, text, toolCalls, duration) {
    var row = document.createElement("div");
    row.className = "msg-row " + (role === "me" ? "me" : "agent");

    var bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.textContent = text;

    row.appendChild(bubble);

    if (toolCalls && toolCalls.length > 0) {
      var toolsDiv = document.createElement("div");
      toolsDiv.className = "msg-tools";
      var names = toolCalls.map(function (t) { return t.tool; }).join(", ");
      toolsDiv.textContent = "[tools: " + names + "]";
      row.appendChild(toolsDiv);
    }

    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  }

  function showTyping(show) {
    typing.classList.toggle("hidden", !show);
    if (show) messages.scrollTop = messages.scrollHeight;
  }

  function showChat() {
    pairScreen.classList.add("hidden");
    chatScreen.classList.remove("hidden");
    msgInput.focus();
  }

  function showPair() {
    chatScreen.classList.add("hidden");
    pairScreen.classList.remove("hidden");
    pairCode.value = "";
    pairError.textContent = "";
    pairBtn.disabled = false;
    pairCode.focus();
  }

  function checkStatus() {
    api("GET", "/api/status").then(function (r) { return r.json(); }).then(function (data) {
      if (data.ok) {
        if (data.bound) {
          statusDot.className = "dot green";
        } else {
          statusDot.className = "dot yellow";
          showPair();
        }
      } else {
        statusDot.className = "dot red";
      }
    }).catch(function () {
      statusDot.className = "dot red";
    });
    setTimeout(checkStatus, 30000);
  }

  // --- api helper ---

  function api(method, path, body) {
    var opts = {
      method: method,
      headers: { "Content-Type": "application/json" },
    };
    if (token) {
      opts.headers["Authorization"] = "Bearer " + token;
    }
    if (body) {
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts);
  }
})();

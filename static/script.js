document.addEventListener("DOMContentLoaded", () => {
  initLandingPage();
  initChatPage();
});

function initLandingPage() {
  const animatedEls = document.querySelectorAll(".fcard, .stat, .about-text, .about-preview");
  if (animatedEls.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = "1";
            entry.target.style.transform = "translateY(0)";
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
    );

    animatedEls.forEach((el) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(24px)";
      el.style.transition = "opacity 0.55s ease, transform 0.55s cubic-bezier(0.16,1,0.3,1)";
      observer.observe(el);
    });
  }

  const homePrompt = document.getElementById("homePrompt");
  const homePromptSend = document.getElementById("homePromptSend");
  if (!homePrompt || !homePromptSend) return;

  const openChatWithPrompt = () => {
    const prompt = homePrompt.value.trim();
    const chatUrl = homePrompt.dataset.chatUrl || "/chat";
    if (!prompt) {
      window.location.href = chatUrl;
      return;
    }
    window.location.href = `${chatUrl}?message=${encodeURIComponent(prompt)}`;
  };

  homePromptSend.addEventListener("click", openChatWithPrompt);
  homePrompt.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      openChatWithPrompt();
    }
  });
}

function initChatPage() {
  const messagesContainer = document.getElementById("messagesContainer");
  const messageInput = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");
  const typingIndicator = document.getElementById("typingIndicator");
  const errorBanner = document.getElementById("errorBanner");
  const errorText = document.getElementById("errorText");
  const dismissError = document.getElementById("dismissError");
  const initialTime = document.getElementById("initialTime");

  if (!messagesContainer || !messageInput || !sendBtn || !typingIndicator) return;

  if (initialTime) {
    initialTime.textContent = formatTime(new Date());
  }

  messageInput.addEventListener("input", () => {
    resizeMessageInput(messageInput);
    sendBtn.disabled = messageInput.value.trim() === "";
  });

  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener("click", sendMessage);
  if (dismissError && errorBanner) {
    dismissError.addEventListener("click", () => errorBanner.classList.remove("active"));
  }

  const initialMessage = new URLSearchParams(window.location.search).get("message");
  if (initialMessage) {
    messageInput.value = initialMessage;
    resizeMessageInput(messageInput);
    sendBtn.disabled = false;
    window.history.replaceState({}, "", window.location.pathname);
    setTimeout(sendMessage, 250);
  }

  async function sendMessage() {
    const userMessage = messageInput.value.trim();
    if (!userMessage) return;

    addMessage(userMessage, "user");
    messageInput.value = "";
    resizeMessageInput(messageInput);
    sendBtn.disabled = true;
    hideError();
    typingIndicator.classList.add("active");
    scrollToBottom(messagesContainer);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.error || `Server error: ${response.status}`);
      }

      addMessage(data.response || "I am here with you. Could you share a little more?", "bot");
    } catch (error) {
      console.error("Failed to get AI response:", error);
      showError("Seren is having trouble responding right now. Please try again in a moment.");
    } finally {
      typingIndicator.classList.remove("active");
      scrollToBottom(messagesContainer);
      messageInput.focus();
    }
  }

  function addMessage(text, sender) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${sender}`;
    const time = formatTime(new Date());
    const safeText = escapeHtml(text).replace(/\n/g, "<br>");

    if (sender === "bot") {
      messageDiv.innerHTML = `
        ${botAvatarMarkup()}
        <div class="message-content">
          <div class="message-bubble">${safeText}</div>
          <div class="message-time">${time}</div>
        </div>`;
    } else {
      messageDiv.innerHTML = `
        <div class="message-content">
          <div class="message-bubble">${safeText}</div>
          <div class="message-time">${time}</div>
        </div>`;
    }

    messagesContainer.appendChild(messageDiv);
    scrollToBottom(messagesContainer);
  }

  function hideError() {
    if (errorBanner) {
      errorBanner.classList.remove("active");
    }
  }

  function showError(message) {
    if (errorText) {
      errorText.textContent = message;
    }
    if (errorBanner) {
      errorBanner.classList.add("active");
    }
  }
}

function resizeMessageInput(input) {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

function botAvatarMarkup() {
  return `
    <div class="bot-avatar">
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 3L13.5 7.5L18 9L13.5 10.5L12 15L10.5 10.5L6 9L10.5 7.5L12 3Z"
          fill="rgba(255,255,255,0.35)" stroke="white" stroke-width="1.4" stroke-linejoin="round"/>
      </svg>
    </div>`;
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function scrollToBottom(container) {
  setTimeout(() => {
    container.scrollTop = container.scrollHeight;
  }, 80);
}

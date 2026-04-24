const API = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:5000/api"
    : window.API_BASE_URL || (window.location.origin + "/api");
const SESSION_TIMEOUT_MS = 30 * 60 * 1000; // 30 min inactivity logout

document.addEventListener("DOMContentLoaded", async () => {
    // --- Auth Guard ---
    let authToken = localStorage.getItem("authToken");
    let refreshToken = localStorage.getItem("refreshToken");
    let currentUser = null;

    try {
        currentUser = JSON.parse(localStorage.getItem("currentUser") || "null");
    } catch {
        localStorage.clear();
    }

    if (!authToken || !currentUser) {
        window.location.href = "login.html";
        return;
    }

    // --- DOM ---
    const $ = (s) => document.querySelector(s);
    const userName = $("#userName");
    const userEmail = $("#userEmail");
    const chatList = $("#chatList");
    const chatForm = $("#chatForm");
    const messageInput = $("#messageInput");
    const sendBtn = $("#sendBtn");
    const messagesContainer = $("#messagesContainer");
    const sidebar = $("#sidebar");
    const imageInput = $("#imageInput");
    const imagePreviewBar = $("#imagePreviewBar");
    const imagePreviewThumb = $("#imagePreviewThumb");
    const imagePreviewName = $("#imagePreviewName");
    const profileModal = $("#profileModal");
    const deleteModal = $("#deleteModal");

    let currentChatId = null;
    let pendingImage = null;
    let chatToDelete = null;
    let inactivityTimer = null;

    // --- Init ---
    userName.textContent = currentUser.name;
    userEmail.textContent = currentUser.email;
    resetInactivityTimer();

    // --- Inactivity Timeout ---
    function resetInactivityTimer() {
        clearTimeout(inactivityTimer);
        inactivityTimer = setTimeout(() => {
            showToast("Session expired due to inactivity", "error");
            logout();
        }, SESSION_TIMEOUT_MS);
    }
    ["click", "keydown", "mousemove", "scroll"].forEach((evt) =>
        document.addEventListener(evt, resetInactivityTimer, { passive: true })
    );

    // --- API Fetch with Auth + Retry ---
    async function apiFetch(url, opts = {}) {
        if (!opts.headers) opts.headers = {};
        // Don't set Content-Type for FormData (browser sets it with boundary)
        if (!(opts.body instanceof FormData)) {
            opts.headers["Content-Type"] = opts.headers["Content-Type"] || "application/json";
        }
        opts.headers["Authorization"] = `Bearer ${authToken}`;

        let resp;
        try {
            resp = await fetch(url, opts);
        } catch (e) {
            showToast("Network error. Check your connection.", "error");
            return null;
        }

        // Token expired — try refresh
        if (resp.status === 401 && refreshToken) {
            const errData = await resp.json().catch(() => ({}));
            if (errData.code === "TOKEN_EXPIRED" || errData.code === "TOKEN_REVOKED" || errData.code === "INVALID_TOKEN") {
                const refreshResp = await fetch(`${API}/auth/refresh`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${refreshToken}` },
                }).catch(() => null);

                if (refreshResp && refreshResp.ok) {
                    const data = await refreshResp.json();
                    authToken = data.access_token;
                    localStorage.setItem("authToken", authToken);
                    opts.headers["Authorization"] = `Bearer ${authToken}`;
                    try {
                        resp = await fetch(url, opts);
                    } catch {
                        return null;
                    }
                } else {
                    showToast("Session expired. Please log in again.", "error");
                    logout();
                    return null;
                }
            }
        }

        // Rate limited
        if (resp.status === 429) {
            showToast("Too many requests. Please wait a moment.", "error");
            return null;
        }

        return resp;
    }

    // --- Toast ---
    function showToast(msg, type = "success") {
        const c = $("#toastContainer");
        const t = document.createElement("div");
        t.className = `toast ${type}`;
        t.textContent = msg;
        c.appendChild(t);
        setTimeout(() => t.remove(), 3500);
    }

    // --- Logout (revokes token on server) ---
    async function logout() {
        try {
            await fetch(`${API}/auth/logout`, {
                method: "POST",
                headers: { Authorization: `Bearer ${authToken}` },
            }).catch(() => {});
        } finally {
            localStorage.clear();
            window.location.href = "login.html";
        }
    }

    // --- XSS-Safe Markdown Renderer ---
    function escapeHtml(str) {
        const d = document.createElement("div");
        d.textContent = str;
        return d.innerHTML;
    }

    function renderMarkdown(text) {
        // Escape HTML first to prevent XSS, then apply markdown
        let safe = escapeHtml(text);
        safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        safe = safe.replace(/\*(.*?)\*/g, "<em>$1</em>");
        safe = safe.replace(/\n/g, "<br>");
        return safe;
    }

    // --- Messages ---
    function addMessage(text, sender, opts = {}) {
        const div = document.createElement("div");
        div.className = `message ${sender}-message ${opts.loading ? "loading" : ""}`;

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.innerHTML = `<i class="fas ${sender === "user" ? "fa-user" : "fa-robot"}"></i>`;

        const content = document.createElement("div");
        content.className = "message-content";

        if (opts.imageUrl) {
            const img = document.createElement("img");
            img.src = opts.imageUrl;
            img.className = "message-image";
            img.alt = "Uploaded image";
            img.loading = "lazy";
            img.onclick = () => window.open(img.src, "_blank");
            content.appendChild(img);
        }

        const p = document.createElement("div");
        p.className = "message-text";
        p.innerHTML = renderMarkdown(text);
        content.appendChild(p);

        div.appendChild(avatar);
        div.appendChild(content);
        messagesContainer.appendChild(div);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return div;
    }

    function setLoading(on) {
        const plane = sendBtn.querySelector(".fa-paper-plane");
        const spin = sendBtn.querySelector(".fa-spinner");
        plane.style.display = on ? "none" : "inline-block";
        spin.style.display = on ? "inline-block" : "none";
        sendBtn.disabled = on;
        messageInput.disabled = on;
    }

    function openModal(modal) { modal.classList.remove("hidden"); }
    function closeModal(modal) { modal.classList.add("hidden"); }

    // --- Chat CRUD ---
    async function loadChats() {
        const resp = await apiFetch(`${API}/chats`);
        if (!resp || !resp.ok) return;
        const { chats } = await resp.json();
        chatList.innerHTML = "";
        chats.forEach((chat) => {
            const item = document.createElement("div");
            item.className = `chat-item ${chat.id === currentChatId ? "active" : ""}`;
            item.innerHTML = `
                <i class="fas fa-message" style="font-size:.8rem;opacity:.5"></i>
                <span class="chat-item-title">${escapeHtml(chat.title)}</span>
                <button class="chat-delete-btn" title="Delete"><i class="fas fa-trash"></i></button>
            `;
            item.querySelector(".chat-item-title").onclick = () => loadChat(chat.id);
            item.querySelector(".chat-delete-btn").onclick = (e) => {
                e.stopPropagation();
                chatToDelete = chat.id;
                openModal(deleteModal);
            };
            chatList.appendChild(item);
        });
    }

    async function createNewChat() {
        const resp = await apiFetch(`${API}/chats`, {
            method: "POST",
            body: JSON.stringify({ title: "New Consultation" }),
        });
        if (!resp || !resp.ok) {
            if (resp) {
                const err = await resp.json().catch(() => ({}));
                showToast(err.error || "Failed to create chat", "error");
            }
            return;
        }
        const { chat } = await resp.json();
        currentChatId = chat.id;
        messagesContainer.innerHTML = "";
        addMessage("Hello! I'm CureAI, your medical assistant. Describe your symptoms or upload an image for analysis.", "ai");
        await loadChats();
    }

    async function loadChat(chatId) {
        const resp = await apiFetch(`${API}/chats/${chatId}`);
        if (!resp || !resp.ok) return;
        const data = await resp.json();
        currentChatId = chatId;
        messagesContainer.innerHTML = "";
        if (data.messages.length === 0) {
            addMessage("This chat is empty. Describe your symptoms to get started.", "ai");
        } else {
            data.messages.forEach((m) => {
                addMessage(m.content, m.sender, { imageUrl: m.image_url || null });
            });
        }
        await loadChats();
        if (window.innerWidth < 768) sidebar.classList.remove("open");
    }

    async function deleteChat(chatId) {
        const resp = await apiFetch(`${API}/chats/${chatId}`, { method: "DELETE" });
        if (!resp || !resp.ok) return;
        if (currentChatId === chatId) {
            currentChatId = null;
            messagesContainer.innerHTML = "";
            addMessage("Chat deleted. Start a new conversation or select an existing one.", "ai");
        }
        showToast("Chat deleted");
        await loadChats();
    }

    async function saveMessage(content, sender) {
        if (!currentChatId) return;
        await apiFetch(`${API}/chats/${currentChatId}/messages`, {
            method: "POST",
            body: JSON.stringify({ content: content.substring(0, 5000), sender }),
        });
    }

    // --- Image Handling ---
    const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp", "image/bmp"];

    imageInput.addEventListener("change", () => {
        const file = imageInput.files[0];
        if (!file) return;
        if (!ALLOWED_TYPES.includes(file.type)) {
            showToast("Invalid image type. Use PNG, JPG, WEBP, or BMP.", "error");
            imageInput.value = "";
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showToast("Image must be under 10MB", "error");
            imageInput.value = "";
            return;
        }
        pendingImage = file;
        imagePreviewThumb.src = URL.createObjectURL(file);
        imagePreviewName.textContent = file.name;
        imagePreviewBar.classList.remove("hidden");
        updateSendState();
    });

    $("#removeImageBtn").addEventListener("click", () => {
        pendingImage = null;
        imageInput.value = "";
        imagePreviewBar.classList.add("hidden");
        updateSendState();
    });

    function updateSendState() {
        sendBtn.disabled = !messageInput.value.trim() && !pendingImage;
    }
    messageInput.addEventListener("input", updateSendState);

    // --- Send Message ---
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = messageInput.value.trim().substring(0, 3000);
        if (!text && !pendingImage) return;

        if (!currentChatId) await createNewChat();
        if (!currentChatId) return;

        const userText = text || "Uploaded an image for analysis";
        let imagePreviewUrl = null;
        if (pendingImage) imagePreviewUrl = URL.createObjectURL(pendingImage);

        addMessage(userText, "user", { imageUrl: imagePreviewUrl });
        messageInput.value = "";
        imagePreviewBar.classList.add("hidden");
        updateSendState();
        setLoading(true);

        const loadingMsg = addMessage("Analyzing...", "ai", { loading: true });

        try {
            if (pendingImage) {
                const formData = new FormData();
                formData.append("image", pendingImage);
                formData.append("caption", userText);
                await apiFetch(`${API}/chats/${currentChatId}/upload`, { method: "POST", body: formData });

                const imgForm = new FormData();
                imgForm.append("image", pendingImage);
                pendingImage = null;
                imageInput.value = "";

                const resp = await apiFetch(`${API}/predict-image`, { method: "POST", body: imgForm });
                safeRemove(loadingMsg);

                if (resp && resp.ok) {
                    const data = await resp.json();
                    addMessage(data.analysis, "ai");
                    await saveMessage(data.analysis, "ai");
                } else {
                    const err = resp ? await resp.json().catch(() => ({})) : {};
                    addMessage(err.error || "Failed to analyze image. Please try again.", "ai");
                }
            } else {
                await saveMessage(text, "user");
                const resp = await apiFetch(`${API}/predict`, {
                    method: "POST",
                    body: JSON.stringify({ symptoms: text }),
                });
                safeRemove(loadingMsg);

                if (resp && resp.ok) {
                    const data = await resp.json();
                    addMessage(data.diagnosis, "ai");
                    await saveMessage(data.diagnosis, "ai");
                } else {
                    const err = resp ? await resp.json().catch(() => ({})) : {};
                    addMessage(err.error || "Something went wrong. Please try again.", "ai");
                }
            }
        } catch (error) {
            console.error("Send error:", error);
            safeRemove(loadingMsg);
            addMessage("Network error. Please check your connection and try again.", "ai");
        } finally {
            setLoading(false);
        }
    });

    function safeRemove(el) {
        if (el && messagesContainer.contains(el)) messagesContainer.removeChild(el);
    }

    // --- Profile ---
    $("#profileAvatarBtn").addEventListener("click", () => {
        $("#profileName").value = currentUser.name;
        $("#profileCurrentPw").value = "";
        $("#profileNewPw").value = "";
        openModal(profileModal);
    });

    $("#profileForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = $("#profileName").value.trim().substring(0, 100);
        const body = { name };
        const curPw = $("#profileCurrentPw").value;
        const newPw = $("#profileNewPw").value;

        if (name.length < 2) return showToast("Name must be at least 2 characters", "error");

        if (newPw) {
            if (newPw.length < 8) return showToast("Password must be at least 8 characters", "error");
            if (!curPw) return showToast("Enter your current password to change it", "error");
            body.current_password = curPw;
            body.new_password = newPw;
        }

        const resp = await apiFetch(`${API}/auth/profile`, {
            method: "PUT",
            body: JSON.stringify(body),
        });
        if (resp && resp.ok) {
            const data = await resp.json();
            currentUser = data.user;
            localStorage.setItem("currentUser", JSON.stringify(currentUser));
            userName.textContent = currentUser.name;
            closeModal(profileModal);
            showToast("Profile updated");
        } else {
            const err = resp ? await resp.json().catch(() => ({})) : {};
            showToast(err.error || "Update failed", "error");
        }
    });

    // --- Delete Confirmation ---
    $("#confirmDeleteBtn").addEventListener("click", async () => {
        if (chatToDelete) await deleteChat(chatToDelete);
        chatToDelete = null;
        closeModal(deleteModal);
    });

    // --- Modal Close ---
    document.querySelectorAll(".close-modal").forEach((btn) => {
        btn.addEventListener("click", () => {
            closeModal(profileModal);
            closeModal(deleteModal);
        });
    });
    [profileModal, deleteModal].forEach((m) => {
        m.addEventListener("click", (e) => {
            if (e.target === m) closeModal(m);
        });
    });

    // --- Sidebar ---
    $("#mobileSidebarToggle")?.addEventListener("click", () => sidebar.classList.toggle("open"));
    $("#logoutBtn").addEventListener("click", logout);
    $("#newChatBtn").addEventListener("click", createNewChat);

    // --- Init ---
    await loadChats();
    addMessage("Hello! I'm CureAI, your medical assistant. Describe your symptoms or upload an image for analysis. Select an existing chat or create a new one.", "ai");
});

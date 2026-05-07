const API = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:5000/api"
    : window.API_BASE_URL || (window.location.origin + "/api");

function sanitizeInput(str) {
    if (!str) return "";
    return str
        .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "")
        .replace(/<script[^>]*>.*?<\/script>/gi, "")
        .replace(/javascript:/gi, "")
        .replace(/on\w+\s*=/gi, "")
        .trim();
}

document.addEventListener("DOMContentLoaded", () => {
    if (localStorage.getItem("authToken")) {
        window.location.href = "chat.html";
        return;
    }

    const loginForm = document.getElementById("loginFormPage");
    const signupForm = document.getElementById("signupFormPage");

    // --- Login ---
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = sanitizeInput(document.getElementById("email").value).toLowerCase().substring(0, 255);
            const password = document.getElementById("password").value;
            const btn = loginForm.querySelector("button[type=submit]");

            if (!email || !password) return showToast("Please fill in all fields", "error");

            btn.disabled = true;
            btn.querySelector(".btn-loading")?.classList.remove("hidden");

            try {
                const resp = await fetch(`${API}/auth/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password }),
                });
                const data = await resp.json();

                if (resp.ok) {
                    localStorage.setItem("authToken", data.access_token);
                    localStorage.setItem("refreshToken", data.refresh_token);
                    localStorage.setItem("currentUser", JSON.stringify(data.user));
                    window.location.href = "chat.html";
                } else if (resp.status === 429) {
                    showToast(data.error || "Too many attempts. Please wait.", "error");
                } else {
                    showToast(data.error || "Login failed", "error");
                }
            } catch {
                showToast("Network error. Is the backend running?", "error");
            } finally {
                btn.disabled = false;
                btn.querySelector(".btn-loading")?.classList.add("hidden");
            }
        });
    }

    // --- Signup ---
    if (signupForm) {
        const pwInput = document.getElementById("password");
        const strengthBar = document.getElementById("passwordStrength");
        const strengthLabel = document.getElementById("strengthLabel");

        if (pwInput && strengthBar) {
            pwInput.addEventListener("input", () => {
                const pw = pwInput.value;
                let score = 0;
                if (pw.length >= 8) score++;
                if (/[A-Z]/.test(pw)) score++;
                if (/[a-z]/.test(pw)) score++;
                if (/\d/.test(pw)) score++;
                if (/[^A-Za-z0-9]/.test(pw)) score++;

                const pct = (score / 5) * 100;
                strengthBar.style.width = pct + "%";
                strengthBar.style.background =
                    score <= 2 ? "var(--error)" : score <= 3 ? "var(--warning)" : "var(--success)";

                if (strengthLabel) {
                    const labels = ["Very Weak", "Weak", "Fair", "Good", "Strong"];
                    strengthLabel.textContent = labels[Math.min(score, 4)];
                    strengthLabel.style.color = strengthBar.style.background;
                }
            });
        }

        signupForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = sanitizeInput(document.getElementById("name").value).substring(0, 100);
            const email = sanitizeInput(document.getElementById("email").value).toLowerCase().substring(0, 255);
            const password = document.getElementById("password").value;
            const confirm = document.getElementById("confirmPassword").value;
            const btn = signupForm.querySelector("button[type=submit]");

            if (!name || !email || !password || !confirm)
                return showToast("Please fill in all fields", "error");
            if (name.length < 2)
                return showToast("Name must be at least 2 characters", "error");
            if (password !== confirm)
                return showToast("Passwords do not match", "error");
            if (password.length < 8)
                return showToast("Password must be at least 8 characters", "error");
            if (!/[A-Z]/.test(password))
                return showToast("Password needs at least one uppercase letter", "error");
            if (!/[a-z]/.test(password))
                return showToast("Password needs at least one lowercase letter", "error");
            if (!/\d/.test(password))
                return showToast("Password needs at least one digit", "error");

            btn.disabled = true;
            btn.querySelector(".btn-loading")?.classList.remove("hidden");

            try {
                const resp = await fetch(`${API}/auth/register`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, email, password }),
                });
                const data = await resp.json();

                if (resp.ok) {
                    localStorage.setItem("authToken", data.access_token);
                    localStorage.setItem("refreshToken", data.refresh_token);
                    localStorage.setItem("currentUser", JSON.stringify(data.user));
                    window.location.href = "chat.html";
                } else {
                    showToast(data.error || "Registration failed", "error");
                }
            } catch {
                showToast("Network error. Is the backend running?", "error");
            } finally {
                btn.disabled = false;
                btn.querySelector(".btn-loading")?.classList.add("hidden");
            }
        });
    }
});

function showToast(msg, type = "success") {
    const c = document.getElementById("toastContainer");
    if (!c) return;
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => t.remove(), 3500);
}

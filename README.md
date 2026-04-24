# CureAI - AI-Powered Medical Assistant

A full-stack medical chatbot with real authentication, PostgreSQL database, AI symptom analysis powered by Pinecone vector search, medicine recommendations from Bangladesh's medex.com.bd database, and medical image processing.

> **⚠️ Deployment Note:** This project requires a server with **2GB+ RAM** due to PyTorch and sentence-transformers dependencies (~450MB). Free-tier hosting platforms (Render 512MB, Google Cloud 614MB) do not have enough memory. A paid VPS (DigitalOcean, Hostinger, Oracle Cloud, etc.) is recommended for deployment. The project runs perfectly on localhost for development.

## Features

- **Real Authentication** — JWT access + refresh tokens, password strength validation, account lockout after 5 failed attempts, token revocation on logout
- **PostgreSQL on Neon.tech** — Production-grade cloud database with SSL
- **AI Symptom Analysis** — Pinecone vector search over 940-page medical PDF (9,500+ vectors) + rule-based symptom analysis engine
- **Medicine Recommendations** — 44+ common Bangladesh medicines with indications, dosage, side effects from medex.com.bd
- **Medical Image Analysis** — Upload images for AI-powered preliminary analysis via HuggingFace Inference API
- **Chat Management** — Create, switch, delete chats with full message history stored in PostgreSQL
- **Profile Management** — Edit name, change password with current password verification
- **Security Hardened** — Rate limiting, security headers, CORS whitelist, PBKDF2 password hashing (600K iterations), token blocklist, input validation, UUID verification, image magic byte validation
- **Responsive Design** — Mobile-first with sidebar toggle, works on all screen sizes

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Flask, SQLAlchemy, Flask-JWT-Extended, Flask-Limiter, Flask-CORS |
| **Database** | PostgreSQL (Neon.tech) with SSL |
| **AI/ML** | PyTorch, sentence-transformers (all-MiniLM-L6-v2), Pinecone vector database |
| **Image Analysis** | HuggingFace Inference API |
| **Frontend** | Vanilla HTML/CSS/JS, Font Awesome |
| **Auth** | JWT access tokens (1hr) + refresh tokens (30 days) |

## Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- [Neon.tech](https://neon.tech) free PostgreSQL database
- [Pinecone](https://pinecone.io) free vector database account

### 1. Clone & Configure

```bash
git clone https://github.com/YOUR_USERNAME/CureAI.git
cd CureAI/backend
copy .env.example .env
```

Edit `.env` with your keys:
```env
DATABASE_URL=postgresql://user:pass@host.neon.tech/dbname?sslmode=require
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
PINECONE_API_KEY=your-pinecone-key
HUGGINGFACE_API_KEY=your-hf-key
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** First install downloads PyTorch (~300MB). This is a one-time download.

### 3. Upload Medicine Data (Optional)

```bash
python upload_medicines.py
```

### 4. Run

```bash
python app.py
```

Open http://localhost:5000 — the backend serves the frontend too.

Or run frontend separately:
```bash
cd frontend/static
python -m http.server 8000
```

Then open http://localhost:8000

**Windows shortcut:** Run `start.bat` from the project root.

## API Endpoints

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | No | Register new user |
| POST | `/api/auth/login` | No | Login (returns access + refresh tokens) |
| POST | `/api/auth/refresh` | Refresh Token | Get new access token |
| GET | `/api/auth/profile` | Access Token | Get user profile |
| PUT | `/api/auth/profile` | Access Token | Update name / change password |
| POST | `/api/auth/logout` | Any Token | Revoke token (real logout) |

### Chat
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/chats` | Yes | List user's chats |
| POST | `/api/chats` | Yes | Create new chat |
| GET | `/api/chats/:id` | Yes | Get chat messages |
| POST | `/api/chats/:id/messages` | Yes | Add message to chat |
| DELETE | `/api/chats/:id` | Yes | Delete chat + uploaded images |
| PUT | `/api/chats/:id/title` | Yes | Rename chat |
| POST | `/api/chats/:id/upload` | Yes | Upload image to chat |

### AI
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/predict` | Yes | AI symptom analysis + medicine suggestions |
| POST | `/api/predict-image` | Yes | AI image analysis |
| GET | `/api/health` | No | Health check + AI status |

## Security Features

| Feature | Implementation |
|---|---|
| Password Hashing | PBKDF2-SHA256 with 600,000 iterations |
| JWT Tokens | Access (1hr) + Refresh (30 days), revocable |
| Token Blocklist | Revoked tokens stored in DB, checked on every request |
| Account Lockout | 5 failed logins → 15 minute lockout |
| Rate Limiting | 60/min default, 10/min auth, 20/min predictions |
| Security Headers | CSP, HSTS, X-Frame-Options DENY, X-Content-Type-Options |
| Input Validation | Length limits, UUID validation, email regex, password strength |
| File Upload | Type whitelist, size limit (10MB), magic byte verification |
| XSS Prevention | HTML escaping before markdown rendering on frontend |
| CORS | Configurable whitelist via `ALLOWED_ORIGINS` |
| SQL Injection | Prevented via SQLAlchemy ORM (parameterized queries) |
| Session Timeout | 30 min inactivity auto-logout on frontend |

## AI Architecture

```
User Query
    │
    ├──→ Pinecone Vector Search (medical PDF, 9500+ vectors)
    │       └── sentence-transformers/all-MiniLM-L6-v2 (384d embeddings)
    │
    ├──→ Pinecone Filtered Search (medicine database, medex.com.bd)
    │
    ├──→ Rule-Based Symptom Analysis Engine
    │       └── Covers: fever, headache, respiratory, digestive, pain, skin, fatigue
    │
    └──→ Response Builder
            ├── Medical references from PDF
            ├── Symptom assessment
            └── Medicine recommendations (Bangladesh brands)
```

**Optional:** Add `OPENAI_API_KEY` to `.env` for GPT-3.5-turbo powered responses using the retrieved context (RAG).

## Project Structure

```
CureAI/
├── backend/
│   ├── config/settings.py          # All configuration & env vars
│   ├── src/
│   │   ├── helper.py               # Text utilities
│   │   └── prompt.py               # AI prompt templates
│   ├── research/data/
│   │   └── Medical.pdf             # 940-page medical reference (embedded in Pinecone)
│   ├── uploads/                    # User uploaded images
│   ├── models.py                   # SQLAlchemy models (User, Chat, Message, TokenBlocklist)
│   ├── auth.py                     # Auth routes + account lockout + token revocation
│   ├── chat_routes.py              # Chat CRUD + image upload + file validation
│   ├── app.py                      # Main Flask app + AI engine + security
│   ├── upload_medicines.py         # Medicine database uploader (44+ medicines)
│   ├── scrape_medicines.py         # MedEx.com.bd scraper (optional)
│   ├── requirements.txt
│   └── .env                        # Environment variables (not in git)
├── frontend/static/
│   ├── index.html                  # Landing page
│   ├── login.html                  # Login with error handling
│   ├── register.html               # Registration with password strength indicator
│   ├── chat.html                   # Chat interface with image upload + profile modal
│   ├── auth_page.js                # Auth logic + password validation
│   ├── chat_app.js                 # Chat logic + token refresh + XSS-safe rendering
│   ├── style.css                   # All styles (responsive)
│   └── hero_medical.png            # Landing page hero image
├── .gitignore
├── start.bat                       # Windows startup script
└── README.md
```

## Deployment (VPS)

### Requirements
- **Minimum:** 2GB RAM, 1 vCPU, 10GB disk
- **Recommended:** 4GB RAM, 2 vCPU, 20GB disk
- **OS:** Ubuntu 22.04

### Why 2GB+ RAM?
| Component | Memory |
|---|---|
| PyTorch (CPU) | ~300MB |
| sentence-transformers model | ~100MB |
| Flask + extensions | ~50MB |
| **Total** | **~450MB** |

Free hosting platforms like Render (512MB) and Google Cloud e2-micro (614MB) don't have enough headroom. A VPS with 2GB+ RAM is recommended.

### Deployment Steps

1. SSH into your VPS
2. Install Python 3.10+, Nginx, Git
3. Clone the repo and install dependencies
4. Configure `.env` with production keys
5. Set `FLASK_DEBUG=false` and `ALLOWED_ORIGINS=https://your-domain.com`
6. Run with gunicorn: `gunicorn app:app --bind 127.0.0.1:5000 --workers 2 --timeout 120`
7. Configure Nginx as reverse proxy
8. (Optional) Add SSL with Let's Encrypt

## Adding More Medical Data

### Upload more medicines:
```bash
# Edit upload_medicines.py to add more medicines to the MEDICINES list
python upload_medicines.py
```

### Scrape from medex.com.bd:
```bash
python scrape_medicines.py --pages 5
```

### Add more medical PDFs:
Place PDF files in `backend/research/data/` and re-run the Pinecone indexing pipeline from `trails.ipynb`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | Neon.tech PostgreSQL connection string |
| `SECRET_KEY` | Yes | Flask secret key (64 char hex) |
| `JWT_SECRET_KEY` | Yes | JWT signing key (64 char hex) |
| `PINECONE_API_KEY` | Yes | Pinecone vector database key |
| `HUGGINGFACE_API_KEY` | No | HuggingFace API key (for image analysis) |
| `OPENAI_API_KEY` | No | OpenAI key (for GPT-powered responses) |
| `ALLOWED_ORIGINS` | No | CORS whitelist (default: localhost) |
| `FLASK_DEBUG` | No | Debug mode (default: true locally) |
| `PORT` | No | Server port (default: 5000) |

## ⚠️ Medical Disclaimer

CureAI provides preliminary health information only. It is **NOT** a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional for medical concerns.

## License

MIT
#   C u r e A I  
 
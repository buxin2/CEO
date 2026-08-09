# My Management System

A simple dashboard for one administrator to manage companies, employees, and weekly tasks — plus employee-facing task links with no login.

The project is split into two deployable parts:

| Folder | Deploy to | Role |
|--------|-----------|------|
| `frontend/` | GitHub Pages | Static HTML/CSS/JS UI |
| `backend/` | Render | Flask REST API + PostgreSQL |

---

## Project Structure

```
my-management-system/
├── frontend/          # GitHub Pages — static site
│   ├── index.html
│   ├── login.html
│   ├── dashboard.html
│   ├── company.html
│   ├── employee-tasks.html
│   ├── task.html          # Employee public task page (?token=...)
│   ├── css/style.css
│   └── js/
│       ├── config.js      # Set API_BASE_URL before deploy
│       └── common.js
│
├── backend/           # Render — API only
│   ├── app.py
│   ├── config.py
│   ├── models.py
│   ├── utils.py
│   ├── requirements.txt
│   ├── Procfile
│   ├── .env.example
│   └── routes/
│       ├── auth.py
│       ├── admin.py
│       ├── company.py
│       ├── employee.py
│       └── public.py
│
└── README.md
```

---

## Local Development

### 1. Backend (API)

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DATABASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, FRONTEND_URL=http://localhost:8080
python app.py
```

API runs at `http://localhost:5000`. Health check: `http://localhost:5000/api/health`

### 2. Frontend (static site)

Edit `frontend/js/config.js`:

```javascript
window.APP_CONFIG = {
  API_BASE_URL: "http://localhost:5000",
};
```

Serve the frontend folder:

```bash
cd frontend
python -m http.server 8080
```

Open `http://localhost:8080` and log in with your `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

For local cross-origin cookies, set in `backend/.env`:

```ini
FRONTEND_URL=http://localhost:8080
CORS_ORIGINS=http://localhost:8080
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=Lax
FLASK_ENV=development
```

---

## Deploy Backend to Render

1. Push this repo to GitHub.
2. In [Render](https://render.com), create a **Web Service** connected to your repo.
3. Set **Root Directory** to `backend`.
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `gunicorn app:app` (from `Procfile`)
6. Add environment variables:

| Variable | Example |
|----------|---------|
| `SECRET_KEY` | long random string |
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `ADMIN_EMAIL` | your admin email |
| `ADMIN_PASSWORD` | your admin password |
| `FRONTEND_URL` | `https://yourusername.github.io/my-management-system` |
| `CORS_ORIGINS` | same as `FRONTEND_URL` |
| `SESSION_COOKIE_SECURE` | `true` |
| `SESSION_COOKIE_SAMESITE` | `None` |
| `FLASK_ENV` | `production` |

7. Deploy and note your Render URL (e.g. `https://my-app.onrender.com`).

---

## Deploy Frontend to GitHub Pages

1. Edit `frontend/js/config.js` and set your Render API URL:

```javascript
window.APP_CONFIG = {
  API_BASE_URL: "https://my-app.onrender.com",
};
```

2. In your GitHub repo **Settings → Pages**, set:
   - **Source:** Deploy from a branch
   - **Branch:** `main` (or your default branch)
   - **Folder:** `/frontend`

3. After deploy, your site will be at:
   `https://yourusername.github.io/my-management-system/`

4. Update Render `FRONTEND_URL` and `CORS_ORIGINS` to match that exact URL (no trailing slash).

---

## How It Connects

```
GitHub Pages (frontend)          Render (backend)
─────────────────────           ─────────────────
login.html  ──fetch──►  POST /api/login  (session cookie)
dashboard.html ──fetch──►  GET /api/dashboard
company.html ──fetch──►  GET /api/companies/:id
task.html?token=xxx ──fetch──►  GET /api/public/tasks/:token
```

- All API calls use `credentials: "include"` so the admin session cookie is sent cross-origin.
- CORS is enabled on the backend for your `FRONTEND_URL`.
- Employee task links look like: `https://yourusername.github.io/my-management-system/task.html?token=AbC123...`

---

## Features

- Single secure admin login
- Companies, employees, weekly tasks (CRUD)
- Week navigation and "Copy Last Week"
- Employee task links (no employee login)
- Dashboard with completion statistics
- PostgreSQL (Neon) via `DATABASE_URL`

---

## Security Notes

- Passwords are hashed with Werkzeug.
- Admin APIs require a signed session cookie.
- Employee APIs are scoped by secret token only.
- Cross-origin sessions use `SameSite=None` + `Secure` in production.
- Never commit `.env` files or real secrets.

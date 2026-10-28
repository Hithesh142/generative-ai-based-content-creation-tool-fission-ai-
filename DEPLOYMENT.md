# 🚀 Fission AI — Deployment Guide

This guide covers deploying **Fission AI** to **Streamlit Community Cloud**, running in **Docker containers**, and hardening storage architecture for production environments.

---

## ☁️ 1. Streamlit Community Cloud (Quickest Deployment)

Streamlit Community Cloud offers free, instant hosting for Streamlit applications connected to GitHub repositories.

### Step-by-Step Setup:
1. **Push Code to GitHub:**
   Ensure your repository is pushed to GitHub with `frontend/main.py` as the main app entrypoint.
2. **Connect Streamlit Community Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
   - Click **"New app"**.
   - Select your repository (`Hithesh142/generative-ai-based-content-creation-tool-fission-ai-`), branch (`main`), and set **Main file path** to:
     ```
     frontend/main.py
     ```
3. **Configure Cloud Secrets:**
   In your app settings on Streamlit Cloud, open **Advanced Settings > Secrets** and paste your environment variables in TOML format:
   ```toml
   GROQ_API_KEY = "gsk_your_groq_api_key_here"
   CLOUDFLARE_ACCOUNT_ID = "your_cloudflare_account_id_here"
   CLOUDFLARE_API_TOKEN = "your_cloudflare_api_token_here"
   GEMINI_API_KEY = "your_gemini_api_key_here"
   HF_TOKEN = "hf_your_huggingface_token_here"
   ```
4. **Deploy:**
   Click **Deploy!**. Streamlit will install `requirements.txt` and launch the studio at a public `https://<your-app>.streamlit.app` URL.

---

## ⚠️ 2. Ephemeral Storage Advisory & Production Hardening

> [!WARNING]
> **Ephemeral Disk Storage on Streamlit Cloud:**  
> Free hosting tiers (including Streamlit Community Cloud and Render Free Tier) run containers with **ephemeral filesystems**. When the container restarts or goes to sleep, any files saved in `data/fission.db` or `data/images/` are reset to git defaults.

### Recommended Production Storage Architecture:

For persistent production workloads with continuous user traffic, decouple database and visual asset storage:

```
┌────────────────────────────────────────────────────────┐
│                   Fission AI Frontend                  │
│                (Streamlit / Docker / K8s)              │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       (PostgreSQL Queries)      (S3 Multipart / presigned)
                │                        │
                ▼                        ▼
┌────────────────────────┐      ┌────────────────────────┐
│  Supabase / Neon DB    │      │  Cloudflare R2 / S3    │
│  (Managed PostgreSQL)  │      │  (Zero-Egress Storage) │
│                        │      │                        │
│  - content_items       │      │  - generated visuals   │
│  - brand_profiles      │      │  - export zip bundles  │
│  - app_settings        │      │  - image variations    │
└────────────────────────┘      └────────────────────────┘
```

1. **Database Decoupling:**
   - Migrate `database/db.py` from `sqlite3` to SQLAlchemy with **Supabase** or **Neon PostgreSQL** (both provide free persistent tiers).
   - Set `DATABASE_URL=postgresql://user:password@host/fission`.
2. **Object Storage Decoupling:**
   - Route visual file uploads and downloads to **Cloudflare R2** or **AWS S3** using `boto3`.
   - Cloudflare R2 provides 10 GB of free storage every month with **zero egress fees**.

---

## 🐳 3. Docker Container Deployment

For private VPS hosting (DigitalOcean Droplet, Hetzner, AWS EC2), deploy Fission AI as an isolated Docker container.

### Production `Dockerfile`

Create `Dockerfile` in the project root:

```dockerfile
# Use official lightweight Python runtime
FROM python:3.12-slim

# Prevent Python from writing .pyc and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies for image processing and SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install pinned Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data directories exist and have proper permissions
RUN mkdir -p data/images data/exports data/logs data/plans && \
    chmod -R 777 data

# Expose default Streamlit port
EXPOSE 8501

# Configure container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Launch Streamlit server
ENTRYPOINT ["streamlit", "run", "frontend/main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

### Build and Run with Docker:

```bash
# 1. Build Docker image
docker build -t fission-ai:latest .

# 2. Run container with persistent data volume mounted to host
docker run -d \
  --name fission-studio \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  fission-ai:latest

# 3. Check container logs
docker logs -f fission-studio
```

---

## 🔒 4. Environment Variables Reference

| Variable | Required | Description |
|:---|:---:|:---|
| `GROQ_API_KEY` | **Yes** | Groq API Key (`gsk_...`) for `llama-3.3-70b-versatile` text generation. |
| `CLOUDFLARE_ACCOUNT_ID` | Recommended | Cloudflare Account ID (found in Cloudflare dashboard URL) for serverless FLUX Schnell. |
| `CLOUDFLARE_API_TOKEN` | Recommended | Cloudflare API Token with `Workers AI: Read` permission. |
| `HF_TOKEN` | Optional | Hugging Face Access Token (`hf_...`) for secondary FLUX inference. |
| `GEMINI_API_KEY` | Optional | Google Gemini Developer API Key. |

---

## 🛡️ 5. Security & Operational Hardening Checklist

- [x] **Secret Redaction:** Logs written to `data/logs/app.log` automatically mask `gsk_`, `hf_`, `Bearer`, and Cloudflare account IDs using `SecretRedactingFormatter`.
- [x] **Parameterized Queries:** All SQLite interactions in `database/db.py` use strictly parameterized SQL (`?` placeholders) to prevent SQL injection.
- [x] **Safe Filenames:** Exported filenames are sanitized through `slugify_filename` using regex stripping to eliminate path traversal (`../`) attacks.
- [x] **CORS & XSRF:** Streamlit server headers configured for secure origin handling.

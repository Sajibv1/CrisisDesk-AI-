# CrisisDesk AI

**Backend-only FastAPI service for citizen report intake, AI-assisted triage, duplicate detection, admin management, and analytics.**

CrisisDesk AI is built for emergency-style public reporting, where reports arrive fragmented, multilingual, and often duplicated. The backend accepts a citizen report, enriches it with external context (translation, geocoding, weather), classifies the issue and its urgency, screens it against recent reports for duplicates, and persists the result in PostgreSQL for responders and administrators to act on.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Core Capabilities](#core-capabilities)
- [Architecture Diagram](#architecture-diagram)
- [Architecture Description](#architecture-description)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Docker Setup](#docker-setup)
- [Database Details](#database-details)
- [CI/CD Explanation](#cicd-explanation)
- [Azure VM Deployment](#azure-vm-deployment)
- [Local Development (without Docker)](#local-development-without-docker)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Problem Statement

During emergencies and public-service incidents, reports come from ordinary citizens who may write in Bangla or English, in incomplete sentences, and without knowing precisely where things stand or what channel to use. Responders need those reports **normalized, classified, prioritized, and de-duplicated** quickly, so they can route effort to what matters instead of triaging noise by hand. CrisisDesk AI automates that first mile: intake → enrichment → classification → duplicate check → structured storage.

## Core Capabilities

| Endpoint | Description |
|---|---|
| `POST /api/reports` | Accepts a citizen report, enriches and classifies it, stores it |
| `GET /api/reports` | Lists reports, filterable by category, urgency, status, search text, date range |
| `GET /api/reports/{id}` | Fetches a single report |
| `PATCH /api/reports/{id}/status` | Admin-only workflow status update (JWT-protected) |
| `DELETE /api/reports/{id}` | Removes a report |
| `GET /api/reports/stats/summary` | Aggregate totals and breakdowns for analytics/dashboards |
| `POST /api/admin/login` | Issues a JWT for protected admin actions |
| `GET /health` | Liveness/readiness probe |

Supporting features:

- Bangla → English translation for non-English reports
- Location resolution to coordinates + place metadata
- Weather/disaster context enrichment for the reported location
- AI-assisted classification (category, urgency, summary, suggested action, confidence) with heuristic fallback
- Duplicate detection against recently submitted reports
- Rate limiting and a consistent success/error response envelope

---

## Architecture Diagram

### System / Data Flow

```mermaid
flowchart LR
  Client[Citizen / Admin Client] --> API[FastAPI]
  API --> Validate[Pydantic Validation]
  Validate --> Translate[Translation Service]
  Translate --> Geo[Geocoding Service]
  Geo --> Weather[Weather Context Service]
  Weather --> Classify[Classifier]
  Classify --> Dedupe[Duplicate Detection]
  Dedupe --> DB[(PostgreSQL)]
  DB --> Analytics[Stats & Filters]
  API --> Auth[JWT Admin Auth]
  Auth --> DB
```

### Request Sequence

```mermaid
sequenceDiagram
  participant C as Citizen
  participant A as FastAPI
  participant T as Translation
  participant G as Geocoding
  participant W as Weather
  participant L as Classifier
  participant D as Duplicate Detection
  participant P as PostgreSQL

  C->>A: POST /api/reports
  A->>A: Validate and normalize input
  A->>T: Translate Bangla to English if needed
  T-->>A: Normalized text
  A->>G: Resolve location
  G-->>A: Coordinates / place metadata
  A->>W: Fetch context for coordinates
  W-->>A: Weather context
  A->>L: Classify + summarize
  L-->>A: Category, urgency, summary, action, confidence
  A->>D: Compare with existing reports
  D-->>A: possibleDuplicate + matchedReportId
  A->>P: Persist report
  P-->>A: Stored report
  A-->>C: Structured JSON response
```

### Deployment Diagram

```mermaid
flowchart TB
  Dev[Developer pushes to main] --> GH[GitHub Actions]
  GH -->|docker build + push| Hub[(Docker Hub<br/>sajib25/crisis-desk-ai)]
  GH -->|SSH deploy step| VM[Azure VM]
  Hub -->|docker compose pull| VM
  VM --> Compose[docker compose up -d]
  Compose --> APIContainer[API Container :8000]
  Compose --> DBContainer[(PostgreSQL Container :5432)]
  APIContainer --> DBContainer
  Users[Citizens / Admins] -->|HTTP| APIContainer
```

---

## Architecture Description

CrisisDesk AI is a **single backend service** (no frontend in this repo) organized as a layered FastAPI application:

- **API layer** (`app/api/routes`) — thin route handlers for reports, auth, and health, each returning a consistent response envelope.
- **Core layer** (`app/core`) — cross-cutting concerns: configuration (Pydantic Settings, env-driven), JWT-based admin authentication/security, a fixed-window rate-limiting middleware, and shared response/error helpers.
- **Service layer** (`app/services`) — the enrichment and intelligence pipeline: `translation.py`, `geocoding.py`, `weather.py`, `classification.py` (with optional Gemini integration and a heuristic fallback), `duplicates.py`, orchestrated by `report_service.py`.
- **Persistence layer** (`app/db`, `app/models`) — SQLAlchemy engine/session setup, table creation and admin-user seeding on startup, and two models: `Report` and `AdminUser`.
- **Schemas** (`app/schemas`) — Pydantic request/response contracts, decoupled from the ORM models.

**Design principles reflected in the code:**

1. **Resilience over completeness** — every external integration (translation, geocoding, weather, Gemini classification) degrades to a heuristic/local fallback on failure or rate-limit, so report submission never hard-fails because of a third-party outage (see `app/services/*` and the "External Services" note below).
2. **Consistent contracts** — every endpoint returns the same `{success, message, data}` (or `details` on failure) envelope via `app/core/response.py`, and errors are centralized through global exception handlers registered in `app/main.py`.
3. **Stateless, horizontally deployable API** — the FastAPI process holds no in-memory session state beyond the rate limiter; all durable state lives in PostgreSQL, which is what makes the `docker compose pull && docker compose up -d` deployment strategy (below) safe to repeat on every push to `main`.
4. **Security boundary at the admin layer** — public citizens can submit/read reports without authentication; mutating admin actions (`PATCH .../status`, future admin operations) require a JWT obtained via `POST /api/admin/login`, backed by a bcrypt-hashed password stored in `admin_users`.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language / Runtime | Python 3.11 |
| Web framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x |
| Database | PostgreSQL 16 (via `psycopg`) |
| Validation | Pydantic / Pydantic Settings |
| Auth | JWT (`python-jose`) + `passlib[bcrypt]` |
| AI classification | Google Gemini (`gemini-1.5-flash`), optional, with heuristic fallback |
| External enrichment | LibreTranslate (translation), Nominatim (geocoding), Open-Meteo (weather) |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions → Docker Hub → Azure VM (SSH deploy) |
| Testing | Pytest, pytest-cov |

## Project Structure

```text
app/
  api/routes/        # HTTP routes: reports, auth, health
  core/               # config, JWT auth, response envelope, rate-limit middleware
  db/                 # engine/session setup and startup seeding
  models/             # SQLAlchemy models (Report, AdminUser)
  schemas/            # Pydantic request/response schemas
  services/           # classification, translation, geocoding, weather, duplicates
  utils/              # ID generation, similarity helpers
tests/                # integration + unit tests
docs/                 # architecture notes
.github/workflows/    # CI/CD pipeline (deploy.yml)
Dockerfile            # API container image
docker-compose.yml    # local/production orchestration (API + PostgreSQL)
```

---

## Docker Setup

The project ships two Docker artifacts: `Dockerfile` (API image) and `docker-compose.yml` (API + PostgreSQL orchestration). This is the same setup used both for local development and production on the Azure VM.

### Dockerfile

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY app /app/app

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- Base image: `python:3.11-slim` for a small footprint.
- `build-essential` is installed to compile any native wheels (e.g. `psycopg`), then apt caches are removed to keep the image lean.
- The package is installed with `pip install -e .`, using the metadata in `pyproject.toml`.
- The container listens on port `8000` and runs the API with Uvicorn bound to `0.0.0.0` so it's reachable from outside the container.

### docker-compose.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: citizen_reports
      POSTGRES_USER: citizen_reports
      POSTGRES_PASSWORD: citizen_reports
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  api:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+psycopg://citizen_reports:citizen_reports@db:5432/citizen_reports
      ADMIN_USERNAME: admin
      ADMIN_PASSWORD: admin123
      JWT_SECRET_KEY: change-me-in-production
    ports:
      - "8000:8000"
    depends_on:
      - db

volumes:
  postgres_data:
```

- **`db` service** — PostgreSQL 16 (Alpine variant), with a named volume (`postgres_data`) so data survives container restarts/recreation.
- **`api` service** — built from the local `Dockerfile`, depends on `db`, and connects to it over the Compose network via the `db` hostname (no need to hardcode IPs).
- Both services are exposed to the host (`5432` for Postgres, `8000` for the API) for local debugging; in production, only `8000` needs to be externally reachable (ideally behind a reverse proxy/HTTPS terminator).

### Running with Docker

```bash
# Start PostgreSQL only (for local dev against uvicorn --reload)
docker compose up -d db

# Or start the full stack: API + PostgreSQL
docker compose up -d --build

# View logs
docker compose logs -f api

# Stop everything
docker compose down
```

> ⚠️ The credentials and `JWT_SECRET_KEY` in `docker-compose.yml` are development defaults. Override them (via `.env`, Compose overrides, or deployment-time secrets) for any real deployment.

---

## Database Details

- **Engine:** PostgreSQL 16 — the only supported database backend (no SQLite fallback in code).
- **Access:** SQLAlchemy 2.x (declarative `Mapped`/`mapped_column` style) over `psycopg` (binary driver), connection string read from `DATABASE_URL`.
- **Schema management:** Tables are created automatically on API startup via `Base.metadata.create_all(bind=engine)` in `app/main.py` — there is no separate Alembic migration step in this repo.
- **Seeding:** On startup, `app/db/init_db.py::seed_if_needed` checks for the configured admin username and creates it (bcrypt-hashed password) if missing, so a fresh database is always immediately usable.

### Tables

**`reports`** (`app/models/report.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` PK | UUID-style report ID |
| `name`, `contact` | `String(120)`, nullable | Reporter identity (optional/anonymous) |
| `location` | `String(255)`, indexed | Raw citizen-provided location text |
| `normalized_location` | `String(255)`, indexed | Post-geocoding normalized location |
| `location_lat`, `location_lon` | `Float`, nullable | Resolved coordinates |
| `description` | `Text` | Original report text |
| `translated_description` | `Text`, nullable | English translation, if applicable |
| `language` | `String(16)` | Source language code (e.g. `bn`, `en`) |
| `category` | `String(64)`, indexed | Classified issue category |
| `urgency` | `String(16)`, indexed | Classified urgency level |
| `summary` | `String(500)` | AI/heuristic-generated summary |
| `suggested_action` | `String(500)` | AI/heuristic-generated recommended action |
| `confidence` | `Float`, default `0.5` | Classification confidence score |
| `possible_duplicate` | `Boolean`, default `False` | Duplicate-detection flag |
| `matched_report_id` | `String(36)`, FK → `reports.id`, nullable | Linked report if a duplicate match is found |
| `status` | `String(32)`, indexed, default `pending` | Admin-managed workflow state |
| `source_metadata` | `JSON`, nullable | Free-form enrichment metadata |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | UTC timestamps, auto-managed |

**`admin_users`** (`app/models/admin.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | `Integer` PK, autoincrement | |
| `username` | `String(120)`, unique, indexed | |
| `password_hash` | `String(255)` | bcrypt hash via `passlib` |
| `is_active` | `Boolean`, default `True` | |
| `created_at` | `DateTime(timezone=True)` | UTC timestamp |

### Connection

```
DATABASE_URL=postgresql+psycopg://citizen_reports:citizen_reports@localhost:5432/citizen_reports
```

In Docker Compose, `localhost` is replaced with the service name `db` so the API container can resolve the database over the internal Compose network.

---

## CI/CD Explanation

CI/CD is implemented as a single GitHub Actions workflow: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml). It triggers **on every push to `main`** and runs two sequential jobs:

### Job 1 — `build-and-push`

1. **Checkout** the repository (`actions/checkout@v4`).
2. **Log in to Docker Hub** (`docker/login-action@v3`) using `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` repository secrets.
3. **Extract metadata/tags** (`docker/metadata-action@v5`) for the image `sajib25/crisis-desk-ai`, producing:
   - a tag matching the branch name (`main`)
   - a short-SHA tag for traceability back to the exact commit
   - a floating `latest` tag
4. **Build and push** the image (`docker/build-push-action@v6`) using the repo's `Dockerfile`, pushing all tags generated above straight to Docker Hub.

### Job 2 — `deploy` (depends on `build-and-push`)

1. Runs only after the image has successfully built and pushed.
2. **SSHes into the Azure VM** (`appleboy/ssh-action@v1.0.3`) using `VM_HOST`, `VM_USERNAME`, and `SSH_PRIVATE_KEY` secrets.
3. On the VM, it runs:
   ```bash
   cd ~/CrisisDesk-AI-
   docker compose pull api   # fetch the newly pushed image
   docker compose up -d      # recreate the api container with the new image
   ```

This gives a simple, zero-manual-step pipeline: **push to `main` → image built and published → VM pulls and restarts the API container** — typically finishing within a couple of minutes of the push.

### Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub login for pushing images |
| `DOCKERHUB_TOKEN` | Docker Hub access token |
| `VM_HOST` | Azure VM public IP / DNS name |
| `VM_USERNAME` | SSH user on the Azure VM |
| `SSH_PRIVATE_KEY` | Private key matching an authorized key on the VM |

### Notes / Improvement Opportunities

- The workflow does **not** currently run the test suite (`pytest`) before building/pushing — for a hackathon-grade pipeline that's acceptable, but adding a `test` job ahead of `build-and-push` (gating the build on green tests) is a natural next step.
- Because `db` is not rebuilt/recreated by the deploy step (only `api` is pulled), the PostgreSQL volume and data on the VM persist across deploys — schema changes are picked up automatically since `Base.metadata.create_all` runs on API startup.

---

## Azure VM Deployment

Production hosting is a single **Azure Virtual Machine** running Docker and Docker Compose, kept in sync by the CI/CD pipeline above.

### One-time VM setup

1. **Provision an Azure VM** (Ubuntu recommended) and open inbound port `8000` (and `22` for SSH) in its Network Security Group.
2. **Install Docker + Docker Compose plugin** on the VM:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   ```
3. **Clone the repository** into the deploy user's home directory, matching the path the workflow expects:
   ```bash
   git clone https://github.com/Sajibv1/CrisisDesk-AI-.git ~/CrisisDesk-AI-
   cd ~/CrisisDesk-AI-
   ```
4. **Provide production environment values** — either edit `docker-compose.yml` on the VM directly or supply a `.env`/Compose override for `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, `GEMINI_API_KEY`, etc., so the running containers don't use the repo's development defaults.
5. **Bring the stack up once manually** to confirm it works end-to-end:
   ```bash
   docker compose up -d
   curl http://localhost:8000/health
   ```
6. **Generate an SSH key pair** dedicated to deployments, add the public key to the VM's `~/.ssh/authorized_keys`, and store the private key as the `SSH_PRIVATE_KEY` GitHub secret (along with `VM_HOST` and `VM_USERNAME`).

### Ongoing deploys

From that point on, deployment is fully automated: every push to `main` triggers the GitHub Actions workflow, which builds and pushes the image, then SSHes into the VM to run `docker compose pull api && docker compose up -d`, recreating only the API container with zero manual intervention. The PostgreSQL container and its volume are left untouched, so report/admin data is preserved across deploys.

### Verifying a deployment

```bash
curl http://<VM_HOST>:8000/health
# {"success":true,"message":"OK","data":{"status":"healthy"}}
```

---

## Local Development (without Docker)

```bash
# 1. Start PostgreSQL only
docker compose up -d db

# 2. Install dependencies (editable install with dev extras)
pip install -e .[dev]

# 3. Configure environment
cp .env.example .env

# 4. Run the API with auto-reload
uvicorn app.main:app --reload
```

The server starts on `http://127.0.0.1:8000`. Interactive API docs are available at `http://127.0.0.1:8000/docs` (Swagger UI) courtesy of FastAPI.

---

## API Reference

### Submit a report

```bash
curl -X POST http://127.0.0.1:8000/api/reports \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Rahim",
    "contact": "017xxxxxxxx",
    "location": "Sylhet Bondor Bazar",
    "description": "There is a fire near a shop and people are trapped.",
    "language": "bn"
  }'
```

### Admin login

```bash
curl -X POST http://127.0.0.1:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Update report status (admin, JWT required)

```bash
curl -X PATCH http://127.0.0.1:8000/api/reports/report_123/status \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "assigned"}'
```

### Response envelope

All responses share a consistent shape:

```json
{
  "success": true,
  "message": "Report submitted successfully.",
  "data": {
    "id": "report_123",
    "category": "fire",
    "urgency": "critical"
  }
}
```

Validation/error responses use `success: false` and, where relevant, a `details` array.

---

## Environment Variables

| Variable | Purpose | Default (dev) |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://citizen_reports:citizen_reports@localhost:5432/citizen_reports` |
| `ADMIN_USERNAME` | Seeded admin username | `admin` |
| `ADMIN_PASSWORD` | Seeded admin password | `admin123` |
| `JWT_SECRET_KEY` | JWT signing secret | `change-me-in-production` |
| `GEMINI_API_KEY` | Optional Gemini API key for AI classification | *(empty — heuristic fallback used)* |

> Set real values for `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, and `DATABASE_URL` in any non-local environment — the defaults above are for local development only.

## External Services

The backend integrates free external APIs on a best-effort basis, always with a local fallback so report submission never blocks on a third party:

- **LibreTranslate** — Bangla → English translation
- **Nominatim** — geocoding / location enrichment
- **Open-Meteo** — weather / disaster context
- **Gemini** (optional) — AI-assisted classification and summary generation

If any external service is unavailable or rate-limited, the API falls back to heuristic logic and still returns a successful response.

## Testing

```bash
pytest
```

The suite (`tests/`) covers report submission, admin login, status updates, and analytics against PostgreSQL, plus unit tests for the classification, duplicate-detection, and report services.

## Troubleshooting

- **API fails to start** — confirm the PostgreSQL container is running and reachable on port `5432` (`docker compose ps`, `docker compose logs db`).
- **Admin login fails** — check that the seeded admin credentials match `ADMIN_USERNAME` / `ADMIN_PASSWORD` in your environment; a stale database won't re-seed a changed password.
- **External APIs rate-limited/unreachable** — expected and handled; the backend still processes reports using fallback logic, but classification/geocoding quality may be reduced.
- **Deploy didn't pick up changes** — confirm the GitHub Actions run succeeded on both jobs, and that the VM's `docker compose pull api` actually found a newer image (check the run logs and `docker images` on the VM).

---

## Related Files

- [app/main.py](app/main.py)
- [app/core/config.py](app/core/config.py)
- [app/services/report_service.py](app/services/report_service.py)
- [docker-compose.yml](docker-compose.yml)
- [Dockerfile](Dockerfile)
- [.github/workflows/deploy.yml](.github/workflows/deploy.yml)
- [docs/architecture.md](docs/architecture.md)

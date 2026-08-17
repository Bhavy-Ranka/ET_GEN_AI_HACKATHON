#  AI Smart City — Intelligent Civic Grievance Management System

> An AI-powered multi-agent platform for automated civic issue detection, deduplication, objective severity scoring, and dynamic priority escalation — built for Indian smart cities.

---

##  Problem Statement

Citizens report civic issues (potholes, garbage heaps, broken streetlights, water leakage) through fragmented, manual channels. Municipalities receive thousands of duplicate complaints, lack priority intelligence, and have no automated triage. This results in SLA breaches, wasted resources, and unresolved issues.

**AI Smart City** solves this with a fully autonomous, multi-agent AI pipeline that ingests a photo + text complaint, understands it using vision + LLM models, deduplicates it against a vector database, objectively scores its severity, and dynamically escalates priority based on public report frequency — all without human intervention.

---

##  Features

- **Vision AI Analysis** — Gemini 2.5 Flash analyzes uploaded images to identify civic issue type, structural severity, and surroundings.
- **LLM Report Structuring** — Llama 3.3 70B (via Groq) and Gemini Flash convert raw user text + image description into a structured JSON report.
- **Objective Multi-Factor Severity Scoring** — Assesses baseline issue urgency (`High`, `Medium`, `Low`) strictly according to safety risk, infrastructure damage, and service disruption.
- **3-Stage Deduplication Pipeline** — Vector Search $\rightarrow$ Multi-Provider LLM Location Verification $\rightarrow$ Calibrated Cosine Similarity (`0.35` threshold).
- **Dynamic Report Count & Severity Escalation** — Duplicate reports automatically increment `report_count`, escalate issue `priority`, and dynamically upgrade severity (e.g., $\ge 4$ duplicate reports auto-escalates to `High` severity).
- **Multi-Provider Resilient LLM Engine** — Graceful fallback chain (Groq LLM $\rightarrow$ Gemini 2.5 Flash $\rightarrow$ Fuzzy token address matcher) ensures zero downtime even during API rate limits.
- **Secure 2-Step OTP Authentication** — Email + Password signup/login with 6-digit OTP email verification via SMTP, protected by short-lived JWT access tokens & 7-day refresh tokens.
- **Dual Database Architecture** — SQLite + SQLAlchemy for user credentials & auth; MongoDB Atlas for vector-indexed grievance storage.
- **Admin Dashboard** — Real-time severity-sorted complaint board with image previews, user tracking, and one-click resolution.

---

##  Architecture

```
                      User (Streamlit Frontend)
                                  │
                                  ▼
                 FastAPI Backend (REST API, JWT Auth)
                                  │
            ┌─────────────────────┴─────────────────────┐
            │                                           │
   SQLite Database                              AI Pipeline (gen_ai/)
(Users & Credentials)                                   │
                                      ┌─────────────────┼─────────────────┐
                                      │                 │                 │
                                Gemini Vision       Groq LLM       Gemini Embeddings
                                 (Image Text)      (RAG Struct)      (Vector Match)
                                      │                 │                 │
                                      └─────────────────┼─────────────────┘
                                                        │
                                                  MongoDB Atlas
                                               (Vector & Metadata)
```

### AI Pipeline & Deduplication Stages

| Stage | Module | Model / Engine | Role |
|-------|--------|----------------|------|
| **Image Analysis** | `image_processing.py` | Gemini 2.5 Flash | Extract visual context from photo |
| **Grievance Structuring** | `rag.py` | Llama 3.3 70B / Gemini Flash | Multi-factor severity scoring & JSON generation |
| **Vector Embedding** | `match.py` | Gemini Embedding 001 | Semantic vector encoding |
| **Candidate Retrieval** | `match.py` | MongoDB Atlas Vector Search | Query vector nearest neighbors (with scan fallback) |
| **Location Verification** | `match.py` | Groq / Gemini 2.5 Flash | Fuzzy landmark & address matching |
| **Duplicate Escalation** | `match.py` | Cosine Similarity (<0.35) | Auto-increment report count & escalate priority/severity |

---

##  Severity Scoring Matrix & Escalation Rules

### 1. Baseline Severity Scoring (Vision + LLM Analysis)
- 🔴 **High (Score 3)**: Immediate safety hazards, structural damage, active health risks, main road obstructions, live electrical wires, water main bursts, or sewage overflows.
- 🟡 **Medium (Score 2)**: Moderate traffic/service disruptions, local road potholes, uncollected garbage heaps, flickering streetlights, or minor pipe leakages.
- 🟢 **Low (Score 1)**: Minor cosmetic issues, non-urgent public maintenance, small litter items, or faded road markings.

### 2. Dynamic Escalation Engine
When duplicate complaints are submitted for an active issue:
- **Report 1**: Initial report filed with baseline severity and priority.
- **Report 2–3**: `report_count`, priority increases, `Low` severity upgrades to `Medium`.
- **Report 4+**: Issue automatically escalates to **High Severity** and surfaces at the top of the Admin Triage board.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit |
| **Backend** | FastAPI + Uvicorn |
| **Vision AI** | Google Gemini 2.5 Flash |
| **LLM Engine** | Meta Llama 3.3 70B (Groq) & Google Gemini 2.5 Flash |
| **Embeddings** | Google Gemini Embedding 001 (`text-embedding-004`) |
| **Vector DB** | MongoDB Atlas (Vector Search & Metadata Store) |
| **Auth DB** | SQLite + SQLAlchemy |
| **Auth & Security** | JWT (`python-jose`) + `passlib` bcrypt + SMTP Email OTP |
| **Process Manager** | Python subprocess orchestration (`run_app.py`) |

---

##  Project Structure

```
ET/
├── README.md
├── requirement.txt
├── run_app.py                  # Orchestrator: launches backend + frontend
├── .env                        # Central environment configuration
└── src/
    ├── backend/
    │   ├── main.py             # FastAPI REST routes, CORS, image service
    │   ├── authentication.py   # 2-Step OTP Auth, JWT tokens, SMTP dispatcher
    │   ├── database.py         # SQLite models & schema auto-migration
    │   └── gen_ai/
    │       ├── ai_main.py      # AI pipeline entry point
    │       ├── image_processing.py  # Gemini Vision AI
    │       ├── rag.py          # LLM structuring & severity matrix
    │       ├── match.py        # 3-stage deduplication & escalation engine
    │       └── model.py        # MongoDB schema & vector index spec
    └── frontend/
        └── app.py              # Streamlit UI (Citizen portal & Admin Triage)
```

---

##  Setup & Installation

### Prerequisites
- Python 3.10+
- MongoDB Atlas account (free tier compatible)
- Google Gemini API key
- Groq API key (optional fallback)
- Gmail account with **App Password** (for SMTP OTP delivery)

### 1. Clone the Repository
```bash
git clone https://github.com/Bhavy-Ranka/ET.git
cd ET
```

### 2. Install Dependencies
```bash
pip install -r requirement.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:

### 4. Run the Application
```bash
python run_app.py
```

This single command launches:
- **Backend API** $\rightarrow$ `http://127.0.0.1:8000`
- **Streamlit Web UI** $\rightarrow$ `http://localhost:8501`

---

##  Authentication & Roles

| Role | Capabilities | Verification |
|------|--------------|--------------|
| **Citizen** | Register account, submit photo/text grievances, view real-time complaint status | Email + Password + 6-Digit Email OTP |
| **Admin** (`admin_email_id`) | Priority triage dashboard, view all grievances by severity column, resolve issues | Admin Role Token + JWT Refresh |

---

## 👥 Team

- **Bhavy Ranka**
- **Aditya Rai**

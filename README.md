# ET-Gen-AI-hackathon-

# Intelligent Civic Grievance Management System

> An AI-powered multi-agent platform for automated civic issue detection, deduplication, categorization, and resolution tracking — built for Indian smart cities.

---

##  Problem Statement

Citizens report civic issues (potholes, garbage, broken lights, water leakage) through fragmented, manual channels. Municipalities receive thousands of duplicate complaints, lack priority intelligence, and have no automated triage. This results in SLA breaches, wasted resources, and unresolved issues.

**AI Smart City** solves this with a fully autonomous, multi-agent AI pipeline that ingests a photo + text complaint, understands it using vision + LLM models, deduplicates it against a vector database, and routes it to the right authority — all without human intervention.

---

## Features

- **Vision AI** — Gemini 2.5 Flash analyzes uploaded images to detect civic issue type, severity, and surroundings
- **LLM Structuring** — Llama 3.3 70B (via Groq) converts raw user text + image description into a structured JSON grievance report
- **3-Stage Deduplication Pipeline** — Vector search → LLM location matching → cosine similarity threshold to prevent duplicate complaints
- **Smart Location Normalization** — Tokenized location matching with LLM fallback for fuzzy address resolution
- **Dual Database Architecture** — SQLite for user auth, MongoDB Atlas for vector-indexed grievance storage
- **JWT Authentication** — Secure role-based access with admin and citizen roles
- **Admin Dashboard** — Real-time severity-sorted complaint board with image preview and one-click resolution
- **Auto Priority Escalation** — Report count and priority auto-incremented on duplicate detections

---

##  Architecture

```
User (Streamlit Frontend)
        │
        ▼
FastAPI Backend (REST API, JWT Auth)
        │
   ┌────┴────┐
   │         │
SQLite    AI Pipeline (gen_ai/)
(Users)        │
          ┌────┼────┐
          │    │    │
     Gemini  Groq  Gemini
     Vision  LLM  Embeddings
     (img)  (RAG) (match)
               │
          MongoDB Atlas
          (Vector Store)
```

### AI Pipeline Stages

| Stage | Module | Model | Role |
|-------|--------|-------|------|
| Image Analysis | `image_processing.py` | Gemini 2.5 Flash | Describe civic issue from photo |
| Grievance Structuring | `rag.py` | Llama 3.3 70B (Groq) | JSON report generation |
| Vector Embedding | `match.py` | Gemini Embedding 001 | Semantic similarity encoding |
| Location Matching | `match.py` | Llama 3.3 70B (Groq) | Fuzzy address deduplication |
| Duplicate Detection | `match.py` | Cosine Similarity | Threshold-based dedup |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| Backend | FastAPI + Uvicorn |
| Vision AI | Google Gemini 2.5 Flash |
| LLM | Meta Llama 3.3 70B via Groq |
| Embeddings | Google Gemini Embedding 001 |
| Vector DB | MongoDB Atlas (Vector Search) |
| Auth DB | SQLite + SQLAlchemy |
| Auth | JWT (python-jose) + bcrypt |
| Process Mgmt | Python subprocess orchestration |

---

##  Project Structure

```
ET/
├── README.md
├── requirement.txt
├── run_app.py                  # Orchestrator: launches backend + frontend
└── src/
    ├── backend/
    │   ├── main.py             # FastAPI app, routes, CORS
    │   ├── authentication.py   # JWT auth, signup/login
    │   ├── database.py         # SQLAlchemy models (User, Complaint)
    │   └── gen_ai/
    │       ├── ai_main.py      # Pipeline entry point
    │       ├── image_processing.py  # Gemini Vision
    │       ├── rag.py          # LLM grievance structuring
    │       ├── match.py        # Deduplication + MongoDB ops
    │       └── model.py        # MongoDB schema + vector index spec
    └── frontend/
        └── app.py              # Streamlit UI (citizen + admin views)
```

---

##  Setup & Installation

### Prerequisites
- Python 3.10+
- MongoDB Atlas account (free tier works)
- Google Gemini API key
- Groq API key

### 1. Clone the Repository
```bash
git clone https://github.com/Bhavy-Ranka/ET.git
cd ET
```

### 2. Install Dependencies
```bash
pip install -r requirement.txt
```

### 3. Set Environment Variables
```bash
export GEMINI_API_KEY="your_gemini_api_key"
export GROK_API_KEY="your_groq_api_key"
export MONGO_URI="your_mongodb_atlas_connection_string"
export MONGO_DB="hack"
export MONGO_COLLECTION="grievances"
export MONGO_VECTOR_INDEX="your_vector_index_name"   # optional, enables Atlas Vector Search
```

### 4. Run the Application
```bash
python run_app.py
```

This starts:
- **Backend** → `http://127.0.0.1:8000`
- **Frontend** → `http://localhost:8501`

---

##  Authentication

| Role | Access |
|------|--------|
| Citizen | Submit complaints, view results |
| Admin (`BHAVY`, `SMARTYY`) | Dashboard with all complaints, severity triage, resolve issues |


        ADMIN_CREDENTIALS = {
            "BHAVY": "2HJR3Y37Dbvhsd@#jnde",
            "SMARTYY": "238guwdd@#Eekjdkui"
        }

Admin credentials are environment-hardened. Regular users sign up via the UI.

---

## How the AI Pipeline Works

1. **Citizen uploads** a photo of a civic issue (pothole, garbage, etc.) with a text description and location
2. **Gemini Vision** analyzes the image and returns a natural language description of the issue
3. **Groq LLM** combines image description + user text + location into a structured JSON:
   ```json
   {
     "issue_title": "Large pothole on main road",
     "category": "Road",
     "severity": "High",
     "formatted_location": "Near IIT Indore Gate 2",
     "tags": ["pothole", "road damage"],
     "detailed_description": "..."
   }
   ```
4. **Gemini Embeddings** convert the description into a semantic vector
5. **MongoDB Vector Search** finds similar existing complaints
6. **Groq LLM location check** confirms if it's the same physical location
7. **Cosine similarity** makes the final dedup decision:
   - If duplicate → increments `report_count` and `priority` on existing record
   - If new → saved as fresh grievance with full metadata

---

##  Admin Dashboard

Admins see complaints sorted into three real-time columns:

| 🔴 High Severity | 🟡 Medium Severity | 🟢 Low Severity |
|------------------|-------------------|-----------------|
| Immediate action | Schedule soon | Monitor |

Each complaint card shows image, description, reporter, location, and a **Mark Resolved** button that removes it from the active queue.

---

##  Real-World Impact

- **Deduplication** prevents the same pothole from being filed 50 times, saving municipality processing time
- **Auto-prioritization** ensures high-severity issues surface first without manual sorting
- **Audit trail** — every complaint stored with user, timestamp, severity, category, and image
- **Scalable** — MongoDB Atlas vector search scales to millions of records

---


##  Team

- **Bhavy Ranka**

- **Aditya Rai**

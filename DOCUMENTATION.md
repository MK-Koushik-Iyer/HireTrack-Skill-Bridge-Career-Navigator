# HireTrack – Skill Bridge Career Navigator

## 📄 Design Documentation

---

## 1. 🧩 Overview

**HireTrack** is an AI-powered web application that analyzes a user’s resume against job descriptions to:

- Identify **skill gaps** using semantic matching
- Recommend **personalized learning resources**
- Generate **targeted interview questions**

The system focuses on **practical career navigation** by combining:

- Natural Language Processing (NLP)
- Embeddings
- Structured datasets

---

## 2. 🏗 System Architecture

### 🔄 High-Level Flow

1. User uploads resume (PDF)
2. Backend extracts text and skills (**AI + fallback**)
3. Semantic matching compares skills with job requirements
4. Gap analysis categorizes skills
5. Learning roadmap is generated from database
6. Interview questions are generated using LLM
7. Results are stored per session

---

## 3. 🛠 Tech Stack

### ⚙️ Backend

- **Framework:** FastAPI
- **Language:** Python 3.10+
- **Database:** MongoDB (Motor async client)
- **PDF Parsing:** PyPDF2
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`)
- **LLM:** Hugging Face Inference API (`Mistral-7B-Instruct`)

---

### 🎨 Frontend

- **Framework:** React 18
- **Styling:** Tailwind CSS
- **HTTP Client:** Axios
- **State Management:** React Hooks
- **Storage:** localStorage (`user_id`)

---

## 4. 🧠 Key Design Decisions

### 4.1 Semantic Matching over Keyword Matching

- Uses **sentence embeddings** instead of string matching
- Handles variations like:
  - `K8s → Kubernetes`
- Improves **real-world accuracy**

---

### 4.2 AI + Fallback Strategy

- **Primary:** LLM-based skill extraction
- **Fallback:** Regex + 1000+ skills database

✅ Ensures reliability even when AI fails

---

### 4.3 Session-Based Architecture

- Each analysis stored with a unique `session_id`

Enables:

- History tracking
- Filtering
- Reusability

---

### 4.4 Transparent AI Outputs

- Returns **similarity scores** to users
- Indicates:
  - AI vs fallback usage

✅ Improves trust and explainability

---

### 4.5 Modular API Design

Separate endpoints for:

- Analysis
- Roadmap
- Interview questions

✅ Enables:

- Independent scaling
- Better caching

---

## 5. Core Features

### 📄 Resume Processing

- PDF upload → text extraction → skill detection

---

### Gap Analysis

- Identifies:
  - ✅ Matched skills
  - ❌ Missing skills
  - 🔄 Transferable skills

- Includes:
  - Match percentage

---

### Learning Roadmap

- Suggests:
  - Courses
  - Projects

- Organized by:
  - Duration
  - Relevance

---

### Interview Preparation

- Generates questions from:
  - Existing skills

- Organized by:
  - Skill
  - Difficulty (Easy / Medium / Hard)

---

## 6. Limitations

- LLM latency (~30–40 seconds for questions)
- Limited job dataset (seeded data)
- No authentication (localStorage-based user ID)
- English-only support
- No mobile-first optimization

---

## 7. Future Enhancements

### High Priority

- Resume improvement suggestions (AI rewriting)
- Interview answer guidance
- Job API integration (LinkedIn / Indeed)

---

### ⚡ Medium Priority

- Progress tracking for learning roadmap
- Skill validation via quizzes
- Export reports as PDF

---

### Advanced Features

- Real-time collaboration with recruiters
- Analytics dashboard (skill trends)
- Full authentication system (JWT / OAuth)

---

## 8. 📈 Scalability Considerations

- Preload embedding model to reduce cold start
- Introduce caching for repeated queries
- Use background jobs (Celery + Redis) for LLM tasks
- Replace free LLM API with dedicated hosted model

---

## 9. 🏁 Conclusion

HireTrack is designed as a **scalable, modular, AI-assisted career platform** that bridges the gap between user skills and job requirements.

By combining:

- Semantic intelligence
- Structured data
- Explainable AI

…it delivers **actionable insights**, not just analysis.

---

## 10. Project Structure

```
/app/
├── backend/
│   ├── server.py              # Main FastAPI application
│   ├── enhanced_skills_db.py  # 1000+ skills database
│   ├── requirements.txt       # Python dependencies
│   └── tests/                 # pytest test files
│
├── frontend/
│   ├── src/
│   │   ├── App.js             # Main React component
│   │   ├── App.css            # Styles
│   │   └── index.js           # Entry point
│   ├── package.json           # Node dependencies
│   └── tailwind.config.js     # Tailwind CSS config
│
│── backend_test.py            #E2E testing of the backend
│── context.md                 #context provided for better understanding
│── Sample_Data.json           #Sample Job description details
│── DOCUMENTATION.md            #Design Documentation
└── README.md                   #README file
```

---

## 11. Key API Endpoints

| Method | Endpoint                   | Description                 |
| ------ | -------------------------- | --------------------------- |
| GET    | `/api/health`              | Health check + model status |
| GET    | `/api/jobs`                | List all job descriptions   |
| POST   | `/api/upload-resume`       | Upload PDF & extract skills |
| POST   | `/api/analyze`             | Semantic gap analysis       |
| POST   | `/api/roadmap`             | Learning recommendations    |
| POST   | `/api/interview-questions` | Generate 10+ interview Qs   |
| POST   | `/api/sessions/create`     | Create new session          |
| GET    | `/api/sessions`            | List/filter past sessions   |
| DELETE | `/api/sessions/{id}`       | Delete session              |

## 12. LLM Configuration

The application uses **FREE open-source LLMs** via Hugging Face Inference API:

| Component           | Model               | Cost         |
| ------------------- | ------------------- | ------------ |
| Skill Extraction    | Mistral-7B-Instruct | FREE         |
| Interview Questions | Mistral-7B-Instruct | FREE         |
| Learning Roadmap    | Mistral-7B-Instruct | FREE         |
| Semantic Matching   | all-MiniLM-L6-v2    | FREE (local) |

**To use a different model**, edit `/app/backend/server.py`:

```python
HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"  # Change this
# Alternatives:
# - "microsoft/Phi-3-mini-4k-instruct"
# - "google/gemma-2-2b-it"
# - "meta-llama/Llama-3.2-3B-Instruct"
```

### Final Vision

> Help users answer:  
> **“What should I do next to get my target job?”**

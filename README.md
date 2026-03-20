# HireTrack-Skill-Bridge-Career-Navigator

## Candidate Information

- **Candidate Name**: M K Koushik Iyer
- **Scenario Chosen**: Skill-Bridge Career Navigator
- **Estimated Time Spent**: 5 hours

---

## Youtube Link (DEMO)

- Link - https://youtu.be/ZGmtHoFeW8Q

## Quick Start

### Prerequisites

| Requirement | Version                                                 |
| ----------- | ------------------------------------------------------- |
| Python      | 3.10+                                                   |
| Node.js     | 18.x+                                                   |
| MongoDB     | 4.4+                                                    |
| RAM         | 4GB minimum (8GB recommended for Sentence Transformers) |

**API Keys needed:**

- `MONGO_URL` - MongoDB connection string (default: `mongodb://localhost:27017/skillbridge`)
- `HF_API_TOKEN` - (OPTIONAL) Hugging Face API token for higher rate limits. Works without it!

**LLM Used:** Hugging Face Inference API (FREE)

- Model: `mistralai/Mistral-7B-Instruct-v0.3`
- No API key required (rate-limited without token)
- Alternative models: `microsoft/Phi-3-mini-4k-instruct`, `google/gemma-2-2b-it`

### Run Commands

**Backend:**

```bash
cd /app/backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**Frontend:**

```bash
cd /app/frontend
yarn install
yarn start

or

cd /app/frontend
npm install
npm start
```

**MongoDB (if using Docker):**

```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### Test Commands

**Backend Tests:**

```bash
cd /app/backend
pytest tests/ -v                         # Run all tests
pytest tests/ --cov=. --cov-report=html  # With coverage
curl http://localhost:8001/api/health    # Quick health check
```

**Frontend Tests:**

```bash
cd /app/frontend
yarn test              # Run React tests
yarn test --coverage   # With coverage
```

**API Quick Tests:**

```bash
# Health check
curl http://localhost:8001/api/health

# List jobs
curl http://localhost:8001/api/jobs

# Generate interview questions
curl -X POST http://localhost:8001/api/interview-questions \
  -H \"Content-Type: application/json\" \
  -d '{\"skills\": [\"Python\", \"Docker\", \"AWS\"], \"count\": 12}'
```

---

## AI Disclosure

- **Did you use an AI assistant (Copilot, ChatGPT, etc.)?** - Yes, I used Claude LLM assistant
- **How did you verify the suggestions?** - I used actor-critic principles of AI, criticizing the assistant wherever it went off the requirement
- **Give one example of a suggestion you rejected or changed:** - Giving context was a big hurdle, I used a context.md which was asked to be refered for keeping sanity of the requirements context

---

## Tradeoffs & Prioritization

### What did you cut to stay within the time limit?

1. **User Authentication System** - Opted for localStorage-based user IDs instead of full auth (JWT/OAuth). This simplified session management while still enabling personalized history tracking.

2. **Export to PDF Feature** - Planned but not implemented. The analysis results can be viewed in-app but cannot be downloaded as a formatted PDF report.

3. **Real-time Collaboration** - No sharing functionality for analyses with recruiters or mentors.

4. **Advanced Analytics Dashboard** - Skipped skill trend analysis over time and comparative analytics across multiple job applications.

5. **Email Notifications** - No automated alerts for new matching jobs or learning resource recommendations.

### What would you build next if you had more time?

1. **Interview Answer Hints** - AI-generated sample answers/talking points for each interview question to help candidates prepare better.

2. **Resume Improvement Suggestions** - AI feedback on how to rewrite resume sections to better highlight skills for target roles.

3. **Job Board Integration** - Connect with LinkedIn, Indeed, or other job APIs to pull real job descriptions instead of seeded data.

4. **Progress Tracking** - Allow users to mark courses as completed and track their learning journey over time.

5. **Skill Verification** - Mini-quizzes or coding challenges to validate claimed skills before interviews.

6. **Full User Authentication** - Proper login/signup with email verification, password reset, and OAuth (Google/GitHub).

### Known Limitations

1. **Interview Question Generation Time** - Takes 30-40 seconds due to LLM processing. Could be improved with caching or background job queues.

2. **Sentence Transformer Model Loading** - ~3 second cold start when the backend initializes. Pre-loading in production deployment recommended.

3. **No Offline Support** - Application requires active internet connection for all AI features.

4. **Limited Job Database** - Currently seeded with 100+ generic tech jobs. Real-world usage would need integration with live job boards.

5. **Single Language Support** - Only English resumes and job descriptions are supported. No localization.

6. **No Mobile Optimization** - UI is responsive but not optimized for mobile-first experience.

---

## Project Structure

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

## Key API Endpoints

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

## LLM Configuration

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

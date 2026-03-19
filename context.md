# HireTrack-Skill-Bridge Career Navigator - Implementation Context

## Project Goal

Build a web application that analyzes resumes against job descriptions, identifies skill gaps using AI-powered semantic matching, recommends learning resources, and generates interview questions based on the user's existing skills.

---

## Functional Requirements

### FR-1: Resume Upload & Skill Extraction

- Accept PDF file upload
- Extract text from PDF using PyPDF2
- Use LLM to extract skills from resume text
- Fallback to regex-based extraction if LLM fails
- Return list of extracted skills to frontend
- Display extraction method to user (AI vs fallback)

### FR-2: Semantic Skill Matching

- DO NOT use simple keyword/string matching
- Use sentence embeddings (Sentence Transformers) for semantic similarity
- Implement skill aliases for common abbreviations:
  - "K8s" → "Kubernetes"
  - "ML" → "Machine Learning"
  - "JS" → "JavaScript"
  - "AWS Lambda" → "AWS"
- Similarity threshold: 0.55 for matches
- Return similarity scores for transparency

### FR-3: Gap Analysis

- Compare user skills against job's required_skills
- Calculate match percentage: (matched / total_required) \* 100
- Categorize skills into:
  - Matched Skills (user has)
  - Missing Skills (user lacks)
  - Transferable Skills (nice-to-have that user has)

### FR-4: Learning Roadmap

- Query database for courses/projects matching missing skills
- Sort by duration (shortest first)
- Limit: 8 courses, 5 projects
- Generate AI recommendations for learning order and tips
- Include: title, provider, duration, difficulty, price, skill_tags

### FR-5: Interview Questions

- Generate questions based on skills PRESENT in resume (NOT missing skills)
- Minimum 10 questions per request
- Cover up to 8 different skills
- Include difficulty level (intermediate/advanced)
- Group questions by skill
- Fallback to template questions if LLM fails

### FR-6: Session Management

- Create unique session_id (UUID) per analysis
- Store user_id (from frontend localStorage)
- Persist: resume_text, extracted_skills, analysis, roadmap, interview_questions
- Support filtering by: user_id, job_title, match_percentage range
- Support session deletion

### FR-7: AI Fallback & Transparency

- If LLM extraction fails, use regex with 1000+ skill keywords
- Return is_fallback: true in response
- Frontend must show: "AI unavailable - showing approximate analysis"

---

## Technical Specifications

### Backend Stack

```
Framework: FastAPI
Python: 3.10+
Database: MongoDB (async with Motor)
PDF Parser: PyPDF2
LLM: Hugging Face Inference API (free tier)
Embeddings: sentence-transformers/all-MiniLM-L6-v2
```

### Frontend Stack

```
Framework: React 18
Styling: Tailwind CSS
HTTP Client: Axios
State: React useState/useEffect
Storage: localStorage for user_id
```

### Database Collections

#### jobs

```json
{
  "_id": "uuid",
  "job_title": "string",
  "description": "string",
  "required_skills": ["string"],
  "nice_to_have_skills": ["string"],
  "level": "Junior|Mid|Senior",
  "created_at": "datetime"
}
```

#### resources

```json
{
  "_id": "uuid",
  "title": "string",
  "provider": "string",
  "type": "course|project",
  "skill_tags": ["string"],
  "price": "number",
  "is_premium": "boolean",
  "duration_hours": "number",
  "difficulty": "Beginner|Intermediate|Advanced",
  "url": "string"
}
```

#### sessions

```json
{
  "_id": "uuid (session_id)",
  "user_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "resume_text": "string",
  "extracted_skills": ["string"],
  "manual_skills": ["string"],
  "analysis": {
    "job_id": "string",
    "job_title": "string",
    "match_percentage": "number",
    "matched_skills": ["string"],
    "missing_skills": ["string"],
    "transferable_skills": ["string"]
  },
  "roadmap": {},
  "interview_questions": [],
  "status": "created|resume_uploaded|analyzed|roadmap_generated|interview_ready"
}
```

---

## API Endpoints

### POST /api/upload-resume

```
Input: multipart/form-data with PDF file
Optional Query: session_id

Output:
{
  "resume_text": "string",
  "extracted_skills": ["string"],
  "extraction_insights": {
    "extraction_method": "ai_semantic_extraction|regex_keyword_matching",
    "is_fallback": boolean,
    "skills_count": number
  }
}
```

### GET /api/jobs

```
Output: Array of job objects (limit 150)
```

### POST /api/analyze

```
Input:
{
  "resume_text": "string",
  "job_id": "string",
  "session_id": "string (optional)",
  "user_skills": ["string"] (optional - if provided, skip extraction)
}

Output:
{
  "id": "uuid",
  "job_title": "string",
  "match_percentage": number,
  "matched_skills": ["string"],
  "missing_skills": ["string"],
  "transferable_skills": ["string"],
  "semantic_scores": {
    "SkillName": {"similarity": 0.85, "matched_with": "UserSkill"}
  }
}
```

### POST /api/roadmap

```
Input:
{
  "missing_skills": ["string"],
  "job_title": "string (optional)",
  "session_id": "string (optional)"
}

Output:
{
  "courses": [resource objects],
  "projects": [resource objects],
  "ai_recommendations": "string (nullable)"
}
```

### POST /api/interview-questions

```
Input:
{
  "skills": ["string"],  // Skills PRESENT in resume
  "count": 10,           // Minimum questions
  "session_id": "string (optional)"
}

Output:
{
  "total_questions": number,
  "skills_covered": ["string"],
  "questions": [
    {"skill": "string", "question": "string", "difficulty": "string"}
  ],
  "questions_by_skill": {
    "SkillName": ["question1", "question2"]
  }
}
```

### POST /api/sessions/create

```
Input: {"user_id": "string (optional)"}
Output: {"session_id": "uuid", "user_id": "string"}
```

### GET /api/sessions

```
Query Params: user_id, job_title, min_match, max_match, limit, skip
Output: {"sessions": [], "total": number}
```

### GET /api/sessions/{session_id}

```
Output: Full session object
```

### DELETE /api/sessions/{session_id}

```
Output: {"success": true}
```

---

## Semantic Matching Implementation

### Skill Aliases (expand before matching)

```python
SKILL_ALIASES = {
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "ml": "machine learning",
    "dl": "deep learning",
    "ai": "artificial intelligence",
    "aws lambda": "aws",
    "react.js": "react",
    "node.js": "nodejs",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "ci/cd": "cicd"
}
```

### Matching Algorithm

```python
1. Expand user_skills with aliases
2. Generate embeddings for expanded_user_skills
3. Generate embeddings for required_skills
4. Compute cosine similarity matrix
5. For each required_skill:
   - Find max similarity with any user skill
   - If similarity >= 0.55: mark as matched
   - Else: mark as missing
6. Return matched, missing, and similarity scores
```

---

## Frontend Components

### Tab Structure

1. **Upload Tab**: PDF upload, extracted skills display, manual skill input, job selector
2. **Analysis Tab**: Match percentage, skill cards (green/red/yellow), action buttons
3. **Roadmap Tab**: Course cards, project cards, AI recommendations
4. **Interview Tab**: Questions grouped by skill, regenerate button

### State Management

```javascript
- jobs: []              // From /api/jobs
- selectedJob: string   // Job ID
- resumeText: string
- extractedSkills: []
- manualSkills: []
- analysis: object
- roadmap: object
- interviewData: object
- sessionId: string
- userId: string        // From localStorage
- loading: boolean
- activeTab: string
- aiStatus: {message, isAi}
```

### Key Behaviors

- When resume changes → clear analysis, roadmap, interview
- When job changes → clear analysis, roadmap, interview
- When manual skill added/removed → clear analysis
- Session history in sidebar with filters
- "New Analysis" button resets all state

---

## Environment Variables

### Backend (.env)

```
MONGO_URL=mongodb://localhost:27017/skillbridge
HF_API_TOKEN=  # Optional for Hugging Face
```

### Frontend (.env)

```
REACT_APP_BACKEND_URL=http://localhost:8001
PORT=3000
```

---

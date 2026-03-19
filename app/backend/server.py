from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime, timezone
import PyPDF2
import io
import re
import json
import httpx
from enhanced_skills_db import TECH_SKILLS_DATABASE, ALL_TECH_SKILLS

# Sentence Transformers for semantic matching
from sentence_transformers import SentenceTransformer
import numpy as np

load_dotenv()

app = FastAPI(title="Skill-Bridge Navigator")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Setup
MONGO_URL = os.environ.get("MONGO_URL")
client = AsyncIOMotorClient(MONGO_URL)
db = client.skillbridge

# Collections
sessions_collection = db.sessions
jobs_collection = db.jobs
resources_collection = db.resources
gap_analysis_collection = db.gap_analysis
interview_questions_collection = db.interview_questions

# ============== FREE OPEN-SOURCE LLM SETUP ==============
# Using Hugging Face Inference API (Free Tier)
# No API key required for many models, but rate-limited
# Set HF_API_TOKEN for higher rate limits (optional)

HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")  # Optional - works without it
HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"  # Free open-source model

# Alternative free models you can use:
# - "microsoft/Phi-3-mini-4k-instruct" 
# - "google/gemma-2-2b-it"
# - "meta-llama/Llama-3.2-3B-Instruct"

# Semantic Model - Load once at startup
embedding_model = None
SKILL_EMBEDDINGS_CACHE = {}

# Pydantic Models
class AnalyzeRequest(BaseModel):
    resume_text: str
    job_id: str
    session_id: Optional[str] = None
    user_skills: Optional[List[str]] = None

class RoadmapRequest(BaseModel):
    missing_skills: List[str]
    job_title: Optional[str] = None
    session_id: Optional[str] = None

class InterviewRequest(BaseModel):
    skills: List[str]
    session_id: Optional[str] = None
    count: Optional[int] = 10

class SessionCreateRequest(BaseModel):
    user_id: Optional[str] = None

class SessionSearchRequest(BaseModel):
    user_id: Optional[str] = None
    job_title: Optional[str] = None
    min_match: Optional[float] = None
    max_match: Optional[float] = None

# ============== HUGGING FACE LLM FUNCTIONS ==============

async def call_huggingface_llm(prompt: str, max_tokens: int = 1000) -> Optional[str]:
    """
    Call Hugging Face Inference API with free open-source models.
    Works without API key (rate-limited) or with HF_API_TOKEN for higher limits.
    """
    try:
        url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
        
        headers = {"Content-Type": "application/json"}
        if HF_API_TOKEN:
            headers["Authorization"] = f"Bearer {HF_API_TOKEN}"
        
        # Format prompt for Mistral instruction format
        formatted_prompt = f"<s>[INST] {prompt} [/INST]"
        
        payload = {
            "inputs": formatted_prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True,
                "return_full_text": False
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get("generated_text", "")
                    return generated_text.strip()
                return str(result)
            elif response.status_code == 503:
                # Model is loading, wait and retry
                print(f"Model loading, waiting...")
                import asyncio
                await asyncio.sleep(20)
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get("generated_text", "").strip()
            else:
                print(f"HuggingFace API error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"HuggingFace API call failed: {e}")
        return None

# ============== SEMANTIC MATCHING ENGINE ==============

def get_embedding_model():
    """Load or return cached embedding model"""
    global embedding_model
    if embedding_model is None:
        print("Loading Sentence Transformer model...")
        embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        print("Model loaded successfully!")
    return embedding_model

def get_skill_embeddings(skills: List[str]) -> np.ndarray:
    """Get embeddings for skills with caching"""
    model = get_embedding_model()
    
    uncached_skills = []
    uncached_indices = []
    
    for i, skill in enumerate(skills):
        skill_lower = skill.lower()
        if skill_lower not in SKILL_EMBEDDINGS_CACHE:
            uncached_skills.append(skill)
            uncached_indices.append(i)
    
    if uncached_skills:
        new_embeddings = model.encode(uncached_skills, convert_to_numpy=True)
        for skill, embedding in zip(uncached_skills, new_embeddings):
            SKILL_EMBEDDINGS_CACHE[skill.lower()] = embedding
    
    result = []
    for skill in skills:
        result.append(SKILL_EMBEDDINGS_CACHE[skill.lower()])
    
    return np.array(result)

# Common skill aliases for better matching
SKILL_ALIASES = {
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "ml": "machine learning",
    "dl": "deep learning",
    "ai": "artificial intelligence",
    "aws lambda": "aws",
    "ec2": "aws",
    "s3": "aws",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "node.js": "nodejs",
    "node": "nodejs",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "tf": "terraform",
    "gcp": "google cloud platform",
    "ci/cd": "cicd",
    "devops": "ci/cd"
}

def expand_skill_aliases(skills: List[str]) -> List[str]:
    """Expand skills with their aliases for better matching"""
    expanded = []
    for skill in skills:
        expanded.append(skill)
        skill_lower = skill.lower()
        if skill_lower in SKILL_ALIASES:
            expanded.append(SKILL_ALIASES[skill_lower])
        for alias, target in SKILL_ALIASES.items():
            if skill_lower == target:
                expanded.append(alias)
    return list(set(expanded))

def semantic_skill_match(user_skills: List[str], required_skills: List[str], threshold: float = 0.55) -> Dict:
    """
    Perform semantic matching between user skills and required skills.
    """
    if not user_skills or not required_skills:
        return {"matched": [], "unmatched": required_skills or [], "scores": {}}
    
    expanded_user_skills = expand_skill_aliases(user_skills)
    
    user_embeddings = get_skill_embeddings(expanded_user_skills)
    required_embeddings = get_skill_embeddings(required_skills)
    
    user_norm = user_embeddings / np.linalg.norm(user_embeddings, axis=1, keepdims=True)
    required_norm = required_embeddings / np.linalg.norm(required_embeddings, axis=1, keepdims=True)
    
    similarity_matrix = np.dot(required_norm, user_norm.T)
    
    matched = []
    unmatched = []
    scores = {}
    
    for i, req_skill in enumerate(required_skills):
        max_similarity = float(np.max(similarity_matrix[i]))
        best_match_idx = int(np.argmax(similarity_matrix[i]))
        best_match_skill = expanded_user_skills[best_match_idx]
        
        scores[req_skill] = {
            "similarity": round(max_similarity, 3),
            "matched_with": best_match_skill if max_similarity >= threshold else None
        }
        
        if max_similarity >= threshold:
            matched.append(req_skill)
        else:
            unmatched.append(req_skill)
    
    return {
        "matched": matched,
        "unmatched": unmatched,
        "scores": scores
    }

# ============== SKILL EXTRACTION ==============

def extract_skills_regex(text: str) -> tuple[List[str], Dict]:
    """Enhanced regex-based skill extraction with 1000+ keywords"""
    text_lower = text.lower()
    found_skills = []
    insights = {
        "total_keywords_scanned": len(ALL_TECH_SKILLS),
        "matches_by_category": {},
        "extraction_method": "regex_keyword_matching",
        "is_fallback": False
    }
    
    for category, skills in TECH_SKILLS_DATABASE.items():
        category_matches = []
        for skill in skills:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.append(skill.title())
                category_matches.append(skill.title())
        
        if category_matches:
            insights["matches_by_category"][category.replace('_', ' ').title()] = len(category_matches)
    
    return list(set(found_skills)), insights

async def extract_skills_llm(text: str) -> tuple[List[str], Dict]:
    """LLM-based skill extraction using free Hugging Face model"""
    insights = {
        "extraction_method": "ai_semantic_extraction",
        "model": HF_MODEL,
        "is_fallback": False
    }
    
    prompt = f"""You are an expert technical recruiter. Extract ALL technical and professional skills from this resume.

Include: programming languages, frameworks, tools, databases, cloud platforms, methodologies, and soft skills.

Resume text:
{text[:3000]}

Return ONLY a JSON array of skills. Example: ["Python", "React", "AWS", "Docker", "Machine Learning"]

JSON array:"""
    
    try:
        response = await call_huggingface_llm(prompt, max_tokens=500)
        
        if response:
            # Try to parse JSON array from response
            try:
                # Find JSON array in response
                start_idx = response.find('[')
                end_idx = response.rfind(']') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    skills = json.loads(json_str)
                    if isinstance(skills, list) and len(skills) > 0:
                        # Clean skills
                        skills = [s.strip() for s in skills if isinstance(s, str) and len(s) > 1]
                        insights["skills_count"] = len(skills)
                        return skills, insights
            except json.JSONDecodeError:
                pass
            
            # Fallback: extract comma-separated skills
            skills = [s.strip().strip('"').strip("'").strip('[').strip(']') 
                     for s in response.split(',')]
            skills = [s for s in skills if len(s) > 1 and len(s) < 50 and not s.startswith('{')]
            if len(skills) > 3:
                insights["skills_count"] = len(skills)
                insights["parse_method"] = "comma_split"
                return skills, insights
    
    except Exception as e:
        print(f"LLM extraction failed: {e}")
    
    # Fallback to regex
    skills, regex_insights = extract_skills_regex(text)
    regex_insights["is_fallback"] = True
    regex_insights["fallback_reason"] = "LLM parsing failed"
    return skills, regex_insights

# ============== SESSION MANAGEMENT ==============

async def create_session(user_id: str = None) -> Dict:
    """Create a new analysis session"""
    session_id = str(uuid.uuid4())
    session = {
        "_id": session_id,
        "user_id": user_id or "anonymous",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "resume_text": None,
        "extracted_skills": [],
        "manual_skills": [],
        "analysis": None,
        "roadmap": None,
        "interview_questions": [],
        "status": "created"
    }
    await sessions_collection.insert_one(session)
    return {"session_id": session_id, "user_id": session["user_id"]}

async def update_session(session_id: str, update_data: Dict) -> bool:
    """Update session data"""
    update_data["updated_at"] = datetime.now(timezone.utc)
    result = await sessions_collection.update_one(
        {"_id": session_id},
        {"$set": update_data}
    )
    return result.modified_count > 0

async def get_session(session_id: str) -> Optional[Dict]:
    """Get session by ID"""
    session = await sessions_collection.find_one({"_id": session_id})
    if session:
        session["id"] = session.pop("_id")
    return session

# ============== STARTUP ==============

@app.on_event("startup")
async def startup_db():
    """Initialize embedding model and seed database"""
    get_embedding_model()
    
    if await jobs_collection.count_documents({}) > 0:
        return
    
    jobs = [
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Cloud Engineer",
            "description": "Design and manage cloud infrastructure",
            "required_skills": ["AWS", "Terraform", "Docker", "Kubernetes", "Python", "CI/CD"],
            "nice_to_have_skills": ["Azure", "GCP", "Ansible"],
            "level": "Mid",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Data Scientist",
            "description": "Build ML models and analyze data",
            "required_skills": ["Python", "Machine Learning", "Pandas", "Scikit-Learn", "SQL", "Statistics"],
            "nice_to_have_skills": ["PyTorch", "TensorFlow", "Deep Learning"],
            "level": "Senior",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "DevOps Engineer",
            "description": "Automate deployment and infrastructure",
            "required_skills": ["Jenkins", "Docker", "Kubernetes", "Git", "Linux", "Bash"],
            "nice_to_have_skills": ["Prometheus", "Grafana", "Helm"],
            "level": "Mid",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Frontend Developer",
            "description": "Build responsive web applications",
            "required_skills": ["React", "JavaScript", "HTML5", "CSS3", "TypeScript"],
            "nice_to_have_skills": ["Next.js", "Tailwind CSS", "Redux"],
            "level": "Junior",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Backend Developer",
            "description": "Develop scalable server-side applications",
            "required_skills": ["Python", "Django", "PostgreSQL", "REST API", "Redis"],
            "nice_to_have_skills": ["FastAPI", "GraphQL", "MongoDB"],
            "level": "Mid",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Full Stack Developer",
            "description": "Work on both frontend and backend",
            "required_skills": ["React", "Node.js", "Express", "MongoDB", "JavaScript"],
            "nice_to_have_skills": ["TypeScript", "Next.js", "AWS"],
            "level": "Senior",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "ML Engineer",
            "description": "Deploy and scale machine learning models",
            "required_skills": ["Python", "TensorFlow", "Docker", "Kubernetes", "MLOps"],
            "nice_to_have_skills": ["AWS SageMaker", "Kubeflow", "Airflow"],
            "level": "Senior",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Cybersecurity Analyst",
            "description": "Protect systems from security threats",
            "required_skills": ["Security", "Penetration Testing", "Cryptography", "Linux", "Networking"],
            "nice_to_have_skills": ["OWASP", "CISSP", "Ethical Hacking"],
            "level": "Mid",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Mobile Developer",
            "description": "Build native mobile applications",
            "required_skills": ["React Native", "JavaScript", "iOS", "Android", "Mobile Development"],
            "nice_to_have_skills": ["Flutter", "Swift", "Kotlin"],
            "level": "Mid",
            "created_at": datetime.now(timezone.utc)
        },
        {
            "_id": str(uuid.uuid4()),
            "job_title": "Data Engineer",
            "description": "Build and maintain data pipelines",
            "required_skills": ["Python", "Apache Spark", "Kafka", "SQL", "ETL", "Airflow"],
            "nice_to_have_skills": ["Databricks", "Snowflake", "DBT"],
            "level": "Senior",
            "created_at": datetime.now(timezone.utc)
        }
    ]
    
    await jobs_collection.insert_many(jobs)
    
    resources = [
        {"_id": str(uuid.uuid4()), "title": "AWS Solutions Architect Professional", "provider": "Coursera", "type": "course", "skill_tags": ["AWS", "Cloud Computing"], "price": 49.99, "is_premium": True, "duration_hours": 40, "difficulty": "Advanced", "url": "https://coursera.com/aws-architect", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Docker Mastery", "provider": "Udemy", "type": "course", "skill_tags": ["Docker", "DevOps"], "price": 29.99, "is_premium": True, "duration_hours": 20, "difficulty": "Intermediate", "url": "https://udemy.com/docker-mastery", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Kubernetes for Developers", "provider": "Pluralsight", "type": "course", "skill_tags": ["Kubernetes", "K8s"], "price": 39.99, "is_premium": True, "duration_hours": 15, "difficulty": "Intermediate", "url": "https://pluralsight.com/k8s", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Terraform Infrastructure as Code", "provider": "A Cloud Guru", "type": "course", "skill_tags": ["Terraform", "IaC"], "price": 0, "is_premium": False, "duration_hours": 12, "difficulty": "Beginner", "url": "https://acloudguru.com/terraform", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Complete Python Bootcamp", "provider": "Udemy", "type": "course", "skill_tags": ["Python"], "price": 19.99, "is_premium": True, "duration_hours": 25, "difficulty": "Beginner", "url": "https://udemy.com/python-bootcamp", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "React Complete Guide", "provider": "Udemy", "type": "course", "skill_tags": ["React", "JavaScript"], "price": 29.99, "is_premium": True, "duration_hours": 30, "difficulty": "Intermediate", "url": "https://udemy.com/react-guide", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Machine Learning A-Z", "provider": "Udemy", "type": "course", "skill_tags": ["Machine Learning", "Python"], "price": 34.99, "is_premium": True, "duration_hours": 44, "difficulty": "Intermediate", "url": "https://udemy.com/ml-az", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Deep Learning Specialization", "provider": "Coursera", "type": "course", "skill_tags": ["Deep Learning", "TensorFlow"], "price": 49.99, "is_premium": True, "duration_hours": 60, "difficulty": "Advanced", "url": "https://coursera.com/deeplearning", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "PostgreSQL Mastery", "provider": "Udemy", "type": "course", "skill_tags": ["PostgreSQL", "SQL"], "price": 24.99, "is_premium": True, "duration_hours": 18, "difficulty": "Intermediate", "url": "https://udemy.com/postgresql", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "MongoDB Complete Guide", "provider": "MongoDB University", "type": "course", "skill_tags": ["MongoDB", "NoSQL"], "price": 0, "is_premium": False, "duration_hours": 15, "difficulty": "Beginner", "url": "https://university.mongodb.com", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Build a Cloud-Native App on AWS", "provider": "AWS Labs", "type": "project", "skill_tags": ["AWS", "Cloud Computing"], "price": 0, "is_premium": False, "duration_hours": 8, "difficulty": "Advanced", "url": "https://aws.amazon.com/getting-started", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Dockerize a Full-Stack Application", "provider": "Docker Labs", "type": "project", "skill_tags": ["Docker", "DevOps"], "price": 0, "is_premium": False, "duration_hours": 4, "difficulty": "Intermediate", "url": "https://labs.docker.com", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Deploy Microservices with Kubernetes", "provider": "K8s Tutorials", "type": "project", "skill_tags": ["Kubernetes", "Microservices"], "price": 0, "is_premium": False, "duration_hours": 6, "difficulty": "Advanced", "url": "https://kubernetes.io/docs/tutorials", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Build a REST API with FastAPI", "provider": "Real Python", "type": "project", "skill_tags": ["FastAPI", "Python"], "price": 0, "is_premium": False, "duration_hours": 5, "difficulty": "Intermediate", "url": "https://realpython.com/fastapi", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "React E-Commerce Store", "provider": "FreeCodeCamp", "type": "project", "skill_tags": ["React", "JavaScript"], "price": 0, "is_premium": False, "duration_hours": 10, "difficulty": "Intermediate", "url": "https://freecodecamp.org/react-ecommerce", "created_at": datetime.now(timezone.utc)},
        {"_id": str(uuid.uuid4()), "title": "Build a Machine Learning Model", "provider": "Kaggle", "type": "project", "skill_tags": ["Machine Learning", "Python"], "price": 0, "is_premium": False, "duration_hours": 12, "difficulty": "Advanced", "url": "https://kaggle.com/competitions", "created_at": datetime.now(timezone.utc)},
    ]
    
    await resources_collection.insert_many(resources)
    print("Database seeded with jobs and resources")

# ============== API ENDPOINTS ==============

@app.get("/")
async def root():
    return {"message": "Skill-Bridge Navigator API is running", "version": "2.1", "llm": "Hugging Face (Free)"}

# SESSION ENDPOINTS
@app.post("/api/sessions/create")
async def api_create_session(request: SessionCreateRequest = None):
    """Create a new analysis session"""
    user_id = request.user_id if request else None
    return await create_session(user_id)

@app.get("/api/sessions/{session_id}")
async def api_get_session(session_id: str):
    """Get session details"""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.get("/api/sessions")
async def api_list_sessions(
    user_id: str = Query(None),
    job_title: str = Query(None),
    min_match: float = Query(None),
    max_match: float = Query(None),
    limit: int = Query(20),
    skip: int = Query(0)
):
    """List and filter past sessions"""
    query = {}
    
    if user_id:
        query["user_id"] = user_id
    if job_title:
        query["analysis.job_title"] = {"$regex": job_title, "$options": "i"}
    if min_match is not None:
        query["analysis.match_percentage"] = {"$gte": min_match}
    if max_match is not None:
        if "analysis.match_percentage" in query:
            query["analysis.match_percentage"]["$lte"] = max_match
        else:
            query["analysis.match_percentage"] = {"$lte": max_match}
    
    cursor = sessions_collection.find(query, {"_id": 1, "user_id": 1, "created_at": 1, "analysis": 1, "status": 1})
    cursor = cursor.sort("created_at", -1).skip(skip).limit(limit)
    
    sessions = []
    async for session in cursor:
        session["id"] = session.pop("_id")
        sessions.append(session)
    
    total = await sessions_collection.count_documents(query)
    
    return {
        "sessions": sessions,
        "total": total,
        "limit": limit,
        "skip": skip
    }

@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str):
    """Delete a session"""
    result = await sessions_collection.delete_one({"_id": session_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "message": "Session deleted"}

# RESUME & SKILLS ENDPOINTS
@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...), session_id: str = None):
    """Parse PDF resume and extract skills using AI with regex fallback"""
    try:
        contents = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF contains no readable text")
        
        # Extract skills using LLM (with fallback to regex)
        extracted_skills, extraction_insights = await extract_skills_llm(text)
        
        # If LLM extraction yields too few skills, supplement with regex
        if len(extracted_skills) < 5:
            regex_skills, _ = extract_skills_regex(text)
            extracted_skills = list(set(extracted_skills + regex_skills))
            extraction_insights["supplemented_with_regex"] = True
        
        # Update session if provided
        if session_id:
            await update_session(session_id, {
                "resume_text": text,
                "extracted_skills": extracted_skills,
                "status": "resume_uploaded"
            })
        
        return {
            "resume_text": text,
            "extracted_skills": extracted_skills,
            "extraction_insights": extraction_insights,
            "session_id": session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.get("/api/jobs")
async def get_jobs():
    """Get all job descriptions"""
    jobs = await jobs_collection.find({}, {"_id": 1, "job_title": 1, "description": 1, "required_skills": 1, "nice_to_have_skills": 1, "level": 1}).to_list(150)
    return jobs

# GAP ANALYSIS ENDPOINT
@app.post("/api/analyze")
async def analyze_gap(request: AnalyzeRequest):
    """Perform semantic gap analysis between resume skills and job requirements"""
    try:
        job = await jobs_collection.find_one({"_id": request.job_id})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if request.user_skills:
            user_skills = request.user_skills
        else:
            user_skills, _ = await extract_skills_llm(request.resume_text)
        
        required_skills = job["required_skills"]
        nice_to_have = job.get("nice_to_have_skills", [])
        
        match_result = semantic_skill_match(user_skills, required_skills, threshold=0.55)
        nice_match_result = semantic_skill_match(user_skills, nice_to_have, threshold=0.55)
        
        matched_skills = match_result["matched"]
        missing_skills = match_result["unmatched"]
        transferable_skills = nice_match_result["matched"]
        
        total_required = len(required_skills)
        match_percentage = (len(matched_skills) / total_required * 100) if total_required > 0 else 0
        
        analysis_id = str(uuid.uuid4())
        analysis_result = {
            "_id": analysis_id,
            "job_id": request.job_id,
            "job_title": job["job_title"],
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "transferable_skills": transferable_skills,
            "match_percentage": round(match_percentage, 2),
            "semantic_scores": match_result["scores"],
            "user_skills_analyzed": user_skills,
            "analyzed_at": datetime.now(timezone.utc),
            "matching_method": "semantic_ai"
        }
        
        await gap_analysis_collection.insert_one(analysis_result)
        
        if request.session_id:
            await update_session(request.session_id, {
                "analysis": {
                    "id": analysis_id,
                    "job_id": request.job_id,
                    "job_title": job["job_title"],
                    "match_percentage": round(match_percentage, 2),
                    "matched_skills": matched_skills,
                    "missing_skills": missing_skills,
                    "transferable_skills": transferable_skills
                },
                "status": "analyzed"
            })
        
        del analysis_result["_id"]
        analysis_result["id"] = analysis_id
        
        return analysis_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# ROADMAP ENDPOINT
@app.post("/api/roadmap")
async def get_roadmap(request: RoadmapRequest):
    """Generate AI-powered learning roadmap for missing skills"""
    try:
        if not request.missing_skills:
            return {"courses": [], "projects": [], "ai_recommendations": None}
        
        courses = await resources_collection.find({
            "type": "course",
            "skill_tags": {"$in": [re.compile(skill, re.IGNORECASE) for skill in request.missing_skills]}
        }).sort("duration_hours", 1).limit(8).to_list(8)
        
        projects = await resources_collection.find({
            "type": "project",
            "skill_tags": {"$in": [re.compile(skill, re.IGNORECASE) for skill in request.missing_skills]}
        }).sort("duration_hours", 1).limit(5).to_list(5)
        
        # Generate AI recommendations using free HuggingFace model
        ai_recommendations = None
        try:
            prompt = f"""You are a career coach. Create a brief learning roadmap for these skills: {', '.join(request.missing_skills[:6])}

Target role: {request.job_title or 'Tech Professional'}

For each skill provide:
1. Learning order (which to learn first)
2. Time estimate (weeks)
3. One key tip

Be concise and practical."""

            ai_recommendations = await call_huggingface_llm(prompt, max_tokens=600)
        except Exception as e:
            print(f"AI roadmap generation failed: {e}")
            ai_recommendations = None
        
        if request.session_id:
            await update_session(request.session_id, {
                "roadmap": {
                    "missing_skills": request.missing_skills,
                    "courses_count": len(courses),
                    "projects_count": len(projects),
                    "generated_at": datetime.now(timezone.utc).isoformat()
                },
                "status": "roadmap_generated"
            })
        
        return {
            "courses": courses,
            "projects": projects,
            "ai_recommendations": ai_recommendations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Roadmap generation failed: {str(e)}")

# INTERVIEW QUESTIONS ENDPOINT
@app.post("/api/interview-questions")
async def generate_interview_questions(request: InterviewRequest):
    """Generate interview questions based on skills PRESENT in the user's resume."""
    try:
        if not request.skills:
            raise HTTPException(status_code=400, detail="No skills provided")
        
        skills_to_cover = request.skills[:8]
        total_questions_needed = request.count
        
        all_questions = []
        questions_by_skill = {}
        
        # Generate questions using free HuggingFace model
        try:
            prompt = f"""Generate {total_questions_needed} technical interview questions for a candidate with these skills: {', '.join(skills_to_cover)}

Requirements:
- Test practical knowledge and problem-solving
- Mix of conceptual, scenario-based, and experience questions
- Cover all listed skills
- Intermediate to advanced difficulty

Return as JSON:
{{"questions": [{{"skill": "SkillName", "question": "Question?", "difficulty": "intermediate"}}]}}

Generate {total_questions_needed} questions:"""

            response = await call_huggingface_llm(prompt, max_tokens=1200)
            
            if response:
                try:
                    # Find JSON in response
                    start_idx = response.find('{')
                    end_idx = response.rfind('}') + 1
                    
                    if start_idx != -1 and end_idx > start_idx:
                        json_str = response[start_idx:end_idx]
                        parsed = json.loads(json_str)
                        
                        if "questions" in parsed:
                            for q in parsed["questions"]:
                                skill = q.get("skill", skills_to_cover[0])
                                question = q.get("question", "")
                                difficulty = q.get("difficulty", "intermediate")
                                
                                if question:
                                    all_questions.append({
                                        "skill": skill,
                                        "question": question,
                                        "difficulty": difficulty
                                    })
                                    
                                    if skill not in questions_by_skill:
                                        questions_by_skill[skill] = []
                                    questions_by_skill[skill].append(question)
                except json.JSONDecodeError:
                    # Parse line by line
                    lines = response.split('\n')
                    for line in lines:
                        if '?' in line and len(line) > 20:
                            question_text = line.strip()
                            if question_text[0].isdigit():
                                question_text = question_text.split('.', 1)[-1].strip()
                            
                            assigned_skill = skills_to_cover[len(all_questions) % len(skills_to_cover)]
                            all_questions.append({
                                "skill": assigned_skill,
                                "question": question_text,
                                "difficulty": "intermediate"
                            })
                            
                            if assigned_skill not in questions_by_skill:
                                questions_by_skill[assigned_skill] = []
                            questions_by_skill[assigned_skill].append(question_text)
                            
                            if len(all_questions) >= total_questions_needed:
                                break
                                
        except Exception as e:
            print(f"AI question generation failed: {e}")
        
        # Fallback questions if AI fails
        if len(all_questions) < total_questions_needed:
            fallback_templates = [
                "Explain your experience working with {skill} in a production environment.",
                "What are the best practices you follow when using {skill}?",
                "Describe a challenging problem you solved using {skill}.",
                "How would you explain {skill} to a junior developer?",
                "What are the common pitfalls when working with {skill} and how do you avoid them?",
                "Compare {skill} with its alternatives. When would you choose each?",
                "How do you stay updated with the latest developments in {skill}?",
                "Describe a project where {skill} significantly improved the outcome.",
                "What metrics would you use to measure success when implementing {skill}?",
                "How do you handle debugging issues related to {skill}?",
                "What's the most complex feature you've built using {skill}?",
                "How would you optimize performance when working with {skill}?"
            ]
            
            for i in range(len(all_questions), total_questions_needed):
                skill = skills_to_cover[i % len(skills_to_cover)]
                template = fallback_templates[i % len(fallback_templates)]
                question = template.format(skill=skill)
                
                all_questions.append({
                    "skill": skill,
                    "question": question,
                    "difficulty": "intermediate"
                })
                
                if skill not in questions_by_skill:
                    questions_by_skill[skill] = []
                questions_by_skill[skill].append(question)
        
        result = {
            "skills_covered": list(questions_by_skill.keys()),
            "total_questions": len(all_questions),
            "questions": all_questions,
            "questions_by_skill": questions_by_skill,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": HF_MODEL
        }
        
        if request.session_id:
            await update_session(request.session_id, {
                "interview_questions": all_questions,
                "status": "interview_ready"
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Question generation failed: {str(e)}")

# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "embedding_model_loaded": embedding_model is not None,
        "llm_provider": "Hugging Face (Free)",
        "llm_model": HF_MODEL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

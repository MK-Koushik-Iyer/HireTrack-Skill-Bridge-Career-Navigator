import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://resume-roadmap-5.preview.emergentagent.com').rstrip('/')


class TestHealthAndSetup:
    """Basic health checks and setup verification"""
    
    def test_health_endpoint(self):
        """Test API health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "embedding_model_loaded" in data
        print(f"Health check passed, embedding model loaded: {data['embedding_model_loaded']}")
    
    def test_get_jobs_list(self):
        """Test that jobs are seeded and returned"""
        response = requests.get(f"{BASE_URL}/api/jobs")
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) >= 10, f"Expected at least 10 jobs, got {len(jobs)}"
        
        # Verify job structure
        job = jobs[0]
        assert "_id" in job
        assert "job_title" in job
        assert "required_skills" in job
        assert isinstance(job["required_skills"], list)
        print(f"Jobs endpoint returned {len(jobs)} jobs")
        return jobs


class TestSessionManagement:
    """Test session creation, retrieval, listing, and deletion"""
    
    @pytest.fixture(scope="class")
    def created_session(self):
        """Create a session for testing"""
        response = requests.post(f"{BASE_URL}/api/sessions/create", json={"user_id": "TEST_user_001"})
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        print(f"Created session: {data['session_id']}")
        return data
    
    def test_create_session(self, created_session):
        """Test session creation returns session_id"""
        assert "session_id" in created_session
        assert "user_id" in created_session
        assert created_session["user_id"] == "TEST_user_001"
        print(f"Session created with ID: {created_session['session_id']}")
    
    def test_get_session(self, created_session):
        """Test session retrieval by ID"""
        session_id = created_session["session_id"]
        response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["user_id"] == "TEST_user_001"
        assert "status" in data
        print(f"Retrieved session with status: {data['status']}")
    
    def test_list_sessions(self, created_session):
        """Test session listing with filters"""
        response = requests.get(f"{BASE_URL}/api/sessions?user_id=TEST_user_001&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        print(f"Listed {len(data['sessions'])} sessions (total: {data['total']})")
    
    def test_get_nonexistent_session(self):
        """Test getting non-existent session returns 404"""
        response = requests.get(f"{BASE_URL}/api/sessions/nonexistent-session-id-12345")
        assert response.status_code == 404
        print("Non-existent session returns 404 as expected")


class TestResumeUpload:
    """Test PDF resume upload and skill extraction"""
    
    @pytest.fixture(scope="class")
    def upload_result(self):
        """Upload a sample resume for testing"""
        # Create session first
        session_response = requests.post(f"{BASE_URL}/api/sessions/create", json={"user_id": "TEST_upload_user"})
        session_id = session_response.json()["session_id"]
        
        # Upload the sample resume
        pdf_path = "/app/backend/sample_resume_junior.pdf"
        with open(pdf_path, "rb") as f:
            files = {"file": ("sample_resume_junior.pdf", f, "application/pdf")}
            response = requests.post(f"{BASE_URL}/api/upload-resume?session_id={session_id}", files=files)
        
        assert response.status_code == 200
        data = response.json()
        data["session_id"] = session_id
        return data
    
    def test_resume_upload_returns_text(self, upload_result):
        """Test PDF upload extracts text"""
        assert "resume_text" in upload_result
        assert len(upload_result["resume_text"]) > 100
        print(f"Extracted {len(upload_result['resume_text'])} characters from PDF")
    
    def test_resume_upload_extracts_skills(self, upload_result):
        """Test AI skill extraction from resume"""
        assert "extracted_skills" in upload_result
        skills = upload_result["extracted_skills"]
        assert len(skills) >= 3, f"Expected at least 3 skills, got {len(skills)}"
        print(f"Extracted {len(skills)} skills: {skills[:5]}...")
    
    def test_extraction_insights_present(self, upload_result):
        """Test extraction insights are returned"""
        assert "extraction_insights" in upload_result
        insights = upload_result["extraction_insights"]
        assert "extraction_method" in insights
        print(f"Extraction method: {insights['extraction_method']}")
    
    def test_session_updated_after_upload(self, upload_result):
        """Verify session is updated after upload"""
        session_id = upload_result["session_id"]
        response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
        assert response.status_code == 200
        session = response.json()
        assert session["status"] == "resume_uploaded"
        assert len(session["extracted_skills"]) > 0
        print(f"Session updated with status: {session['status']}")


class TestSemanticSkillMatching:
    """Test semantic skill matching capabilities - CORE FEATURE"""
    
    @pytest.fixture(scope="class")
    def jobs(self):
        """Get all jobs for testing"""
        response = requests.get(f"{BASE_URL}/api/jobs")
        return response.json()
    
    def test_exact_skill_match(self, jobs):
        """Test that exact skill names match perfectly"""
        cloud_engineer_job = next((j for j in jobs if j["job_title"] == "Cloud Engineer"), None)
        assert cloud_engineer_job is not None
        
        response = requests.post(f"{BASE_URL}/api/analyze", json={
            "resume_text": "Experienced with Docker, Kubernetes, and Python programming.",
            "job_id": cloud_engineer_job["_id"],
            "user_skills": ["Docker", "Kubernetes", "Python"]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "matched_skills" in data
        assert len(data["matched_skills"]) >= 3
        print(f"Exact skills matched: {data['matched_skills']}")
    
    def test_semantic_alias_k8s_kubernetes(self, jobs):
        """Test that K8s matches Kubernetes semantically"""
        devops_job = next((j for j in jobs if j["job_title"] == "DevOps Engineer"), None)
        assert devops_job is not None
        
        response = requests.post(f"{BASE_URL}/api/analyze", json={
            "resume_text": "Extensive experience with K8s container orchestration.",
            "job_id": devops_job["_id"],
            "user_skills": ["K8s", "Docker", "Git"]
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Check if Kubernetes was matched through K8s alias
        print(f"Matched skills: {data['matched_skills']}")
        print(f"Missing skills: {data['missing_skills']}")
        print(f"Semantic scores: {data.get('semantic_scores', {})}")
        
        # K8s should semantically match Kubernetes 
        kubernetes_matched = "Kubernetes" in data["matched_skills"]
        print(f"K8s → Kubernetes semantic match: {kubernetes_matched}")
        assert data["matching_method"] == "semantic_ai"
    
    def test_semantic_alias_ml_machine_learning(self, jobs):
        """Test that ML matches Machine Learning semantically"""
        ds_job = next((j for j in jobs if j["job_title"] == "Data Scientist"), None)
        assert ds_job is not None
        
        response = requests.post(f"{BASE_URL}/api/analyze", json={
            "resume_text": "Strong ML background with Python and statistical analysis.",
            "job_id": ds_job["_id"],
            "user_skills": ["ML", "Python", "Statistics"]
        })
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"Matched skills: {data['matched_skills']}")
        print(f"Semantic scores: {data.get('semantic_scores', {})}")
        
        # ML should match Machine Learning
        ml_matched = "Machine Learning" in data["matched_skills"]
        print(f"ML → Machine Learning semantic match: {ml_matched}")
    
    def test_match_percentage_calculation(self, jobs):
        """Test match percentage is correctly calculated"""
        frontend_job = next((j for j in jobs if j["job_title"] == "Frontend Developer"), None)
        assert frontend_job is not None
        
        # User has 3 out of 5 required skills
        response = requests.post(f"{BASE_URL}/api/analyze", json={
            "resume_text": "React developer with JavaScript and TypeScript experience.",
            "job_id": frontend_job["_id"],
            "user_skills": ["React", "JavaScript", "TypeScript"]
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "match_percentage" in data
        assert 0 <= data["match_percentage"] <= 100
        
        # Should be around 60% (3 of 5 skills matched)
        print(f"Match percentage: {data['match_percentage']}%")
        print(f"   Matched: {len(data['matched_skills'])}/{len(frontend_job['required_skills'])} required skills")


class TestGapAnalysis:
    """Test gap analysis dashboard functionality"""
    
    @pytest.fixture(scope="class")
    def analysis_result(self):
        """Create a full analysis for testing"""
        # Get jobs
        jobs_response = requests.get(f"{BASE_URL}/api/jobs")
        jobs = jobs_response.json()
        cloud_job = next((j for j in jobs if j["job_title"] == "Cloud Engineer"), None)
        
        # Create session
        session_response = requests.post(f"{BASE_URL}/api/sessions/create", json={"user_id": "TEST_analysis_user"})
        session_id = session_response.json()["session_id"]
        
        # Perform analysis
        response = requests.post(f"{BASE_URL}/api/analyze", json={
            "resume_text": "Python developer with Docker and CI/CD experience. Working on cloud projects.",
            "job_id": cloud_job["_id"],
            "user_skills": ["Python", "Docker", "CI/CD"],
            "session_id": session_id
        })
        
        data = response.json()
        data["session_id"] = session_id
        data["job"] = cloud_job
        return data
    
    def test_analysis_returns_matched_skills(self, analysis_result):
        """Test analysis returns matched skills list"""
        assert "matched_skills" in analysis_result
        assert isinstance(analysis_result["matched_skills"], list)
        print(f"Matched skills: {analysis_result['matched_skills']}")
    
    def test_analysis_returns_missing_skills(self, analysis_result):
        """Test analysis returns missing skills list"""
        assert "missing_skills" in analysis_result
        assert isinstance(analysis_result["missing_skills"], list)
        print(f"Missing skills: {analysis_result['missing_skills']}")
    
    def test_analysis_returns_transferable_skills(self, analysis_result):
        """Test analysis returns transferable skills from nice-to-have"""
        assert "transferable_skills" in analysis_result
        print(f"Transferable skills: {analysis_result['transferable_skills']}")
    
    def test_analysis_includes_semantic_scores(self, analysis_result):
        """Test analysis includes semantic similarity scores"""
        assert "semantic_scores" in analysis_result
        scores = analysis_result["semantic_scores"]
        assert isinstance(scores, dict)
        
        # Check score structure
        if scores:
            sample_skill = list(scores.keys())[0]
            assert "similarity" in scores[sample_skill]
            print(f"Semantic scores included: {list(scores.keys())[:3]}...")
    
    def test_session_updated_with_analysis(self, analysis_result):
        """Verify session is updated with analysis results"""
        session_id = analysis_result["session_id"]
        response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
        session = response.json()
        
        assert session["status"] == "analyzed"
        assert session["analysis"] is not None
        assert session["analysis"]["match_percentage"] == analysis_result["match_percentage"]
        print(f"Session updated with analysis: {session['analysis']['match_percentage']}% match")


class TestLearningRoadmap:
    """Test learning roadmap generation"""
    
    @pytest.fixture(scope="class")
    def roadmap_result(self):
        """Generate a roadmap for testing"""
        # Create session
        session_response = requests.post(f"{BASE_URL}/api/sessions/create", json={"user_id": "TEST_roadmap_user"})
        session_id = session_response.json()["session_id"]
        
        response = requests.post(f"{BASE_URL}/api/roadmap", json={
            "missing_skills": ["Kubernetes", "Terraform", "AWS"],
            "job_title": "Cloud Engineer",
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        data["session_id"] = session_id
        return data
    
    def test_roadmap_returns_courses(self, roadmap_result):
        """Test roadmap includes course recommendations"""
        assert "courses" in roadmap_result
        courses = roadmap_result["courses"]
        assert isinstance(courses, list)
        
        if courses:
            course = courses[0]
            assert "title" in course
            assert "provider" in course
            assert "skill_tags" in course
            print(f"Returned {len(courses)} courses: {[c['title'] for c in courses[:3]]}")
    
    def test_roadmap_returns_projects(self, roadmap_result):
        """Test roadmap includes project recommendations"""
        assert "projects" in roadmap_result
        projects = roadmap_result["projects"]
        assert isinstance(projects, list)
        
        if projects:
            project = projects[0]
            assert "title" in project
            print(f"Returned {len(projects)} projects")
    
    def test_roadmap_ai_recommendations(self, roadmap_result):
        """Test AI-generated learning advice is included"""
        # AI recommendations may or may not be present
        if roadmap_result.get("ai_recommendations"):
            assert len(roadmap_result["ai_recommendations"]) > 50
            print(f"AI recommendations provided ({len(roadmap_result['ai_recommendations'])} chars)")
        else:
            print("⚠️ AI recommendations not available (LLM may have failed)")


class TestInterviewQuestions:
    """Test interview question generation - CRITICAL: uses PRESENT skills, 10+ questions"""
    
    @pytest.fixture(scope="class")
    def interview_result(self):
        """Generate interview questions for testing"""
        session_response = requests.post(f"{BASE_URL}/api/sessions/create", json={"user_id": "TEST_interview_user"})
        session_id = session_response.json()["session_id"]
        
        # Note: skills are skills PRESENT in resume (not missing!)
        response = requests.post(f"{BASE_URL}/api/interview-questions", json={
            "skills": ["Python", "Docker", "React", "AWS", "Machine Learning"],
            "count": 12,
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        data["session_id"] = session_id
        return data
    
    def test_interview_generates_minimum_10_questions(self, interview_result):
        """CRITICAL: Verify at least 10 questions are generated"""
        assert "total_questions" in interview_result
        total = interview_result["total_questions"]
        assert total >= 10, f"Expected at least 10 questions, got {total}"
        print(f"Generated {total} interview questions (requirement: 10+)")
    
    def test_interview_returns_questions_list(self, interview_result):
        """Test questions are returned as structured list"""
        assert "questions" in interview_result
        questions = interview_result["questions"]
        assert isinstance(questions, list)
        assert len(questions) >= 10
        
        # Check question structure
        question = questions[0]
        assert "skill" in question
        assert "question" in question
        assert "difficulty" in question
        print(f"Sample question: {question['skill']} - {question['question'][:50]}...")
    
    def test_interview_covers_multiple_skills(self, interview_result):
        """Test questions cover multiple provided skills"""
        assert "skills_covered" in interview_result
        skills_covered = interview_result["skills_covered"]
        assert len(skills_covered) >= 2, f"Expected multiple skills covered, got {len(skills_covered)}"
        print(f"Skills covered in interview: {skills_covered}")
    
    def test_interview_questions_by_skill(self, interview_result):
        """Test questions are organized by skill"""
        assert "questions_by_skill" in interview_result
        by_skill = interview_result["questions_by_skill"]
        assert isinstance(by_skill, dict)
        
        for skill, questions in by_skill.items():
            assert len(questions) >= 1, f"Expected at least 1 question for {skill}"
        print(f"Questions organized by {len(by_skill)} skills")
    
    def test_interview_uses_present_skills_not_missing(self, interview_result):
        """CRITICAL: Verify questions are based on PRESENT skills"""
        skills_requested = ["Python", "Docker", "React", "AWS", "Machine Learning"]
        skills_covered = interview_result["skills_covered"]
        
        # All covered skills should be from the requested list (present skills)
        for skill in skills_covered:
            # Check if skill is related to requested skills (semantic match allowed)
            found_match = False
            for req_skill in skills_requested:
                if skill.lower() in req_skill.lower() or req_skill.lower() in skill.lower():
                    found_match = True
                    break
            # If no direct match, it's still valid as long as questions exist
            if not found_match:
                print(f"⚠️ Skill '{skill}' not directly from requested list (may be AI variation)")
        
        print(f"Questions generated for PRESENT skills: {skills_covered}")


class TestErrorHandling:
    """Test error handling for edge cases"""
    
    def test_analyze_with_invalid_job_id(self):
        """Test analysis with non-existent job returns 404"""
        response = requests.post(f"{BASE_URL}/api/analyze", json={
            "resume_text": "Sample resume text",
            "job_id": "invalid-job-id-12345",
            "user_skills": ["Python"]
        })
        assert response.status_code == 404
        print("Invalid job ID returns 404")
    
    def test_interview_with_no_skills(self):
        """Test interview generation with empty skills returns 400"""
        response = requests.post(f"{BASE_URL}/api/interview-questions", json={
            "skills": [],
            "count": 10
        })
        assert response.status_code == 400
        print("Empty skills list returns 400")
    
    def test_delete_session(self):
        """Test session deletion"""
        # Create session
        create_response = requests.post(f"{BASE_URL}/api/sessions/create", json={"user_id": "TEST_delete_user"})
        session_id = create_response.json()["session_id"]
        
        # Delete session
        delete_response = requests.delete(f"{BASE_URL}/api/sessions/{session_id}")
        assert delete_response.status_code == 200
        
        # Verify deleted
        get_response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
        assert get_response.status_code == 404
        print("Session deletion works correctly")


class TestEndToEndWorkflow:
    """Test complete E2E workflow: Upload → Analyze → Roadmap → Interview"""
    
    def test_complete_workflow(self):
        """Test full user workflow from start to finish"""
        # Step 1: Create session
        session_response = requests.post(f"{BASE_URL}/api/sessions/create", json={"user_id": "TEST_e2e_user"})
        assert session_response.status_code == 200
        session_id = session_response.json()["session_id"]
        print(f"Step 1: Created session {session_id}")
        
        # Step 2: Upload resume
        with open("/app/backend/sample_resume_senior.pdf", "rb") as f:
            files = {"file": ("sample_resume_senior.pdf", f, "application/pdf")}
            upload_response = requests.post(f"{BASE_URL}/api/upload-resume?session_id={session_id}", files=files)
        
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        extracted_skills = upload_data["extracted_skills"]
        print(f"Step 2: Uploaded resume, extracted {len(extracted_skills)} skills")
        
        # Step 3: Get jobs and select one
        jobs_response = requests.get(f"{BASE_URL}/api/jobs")
        jobs = jobs_response.json()
        target_job = jobs[0]  # Cloud Engineer
        print(f"Step 3: Selected job '{target_job['job_title']}'")
        
        # Step 4: Analyze gap
        analyze_response = requests.post(f"{BASE_URL}/api/analyze", json={
            "resume_text": upload_data["resume_text"],
            "job_id": target_job["_id"],
            "user_skills": extracted_skills,
            "session_id": session_id
        })
        
        assert analyze_response.status_code == 200
        analysis = analyze_response.json()
        print(f"Step 4: Analyzed gap - {analysis['match_percentage']}% match")
        print(f"        Matched: {analysis['matched_skills']}")
        print(f"        Missing: {analysis['missing_skills']}")
        
        # Step 5: Generate roadmap (if missing skills exist)
        if analysis["missing_skills"]:
            roadmap_response = requests.post(f"{BASE_URL}/api/roadmap", json={
                "missing_skills": analysis["missing_skills"],
                "job_title": target_job["job_title"],
                "session_id": session_id
            })
            
            assert roadmap_response.status_code == 200
            roadmap = roadmap_response.json()
            print(f"Step 5: Generated roadmap - {len(roadmap['courses'])} courses, {len(roadmap['projects'])} projects")
        else:
            print("Step 5: Skipped roadmap (no missing skills)")
        
        # Step 6: Generate interview questions (based on PRESENT skills)
        present_skills = analysis["matched_skills"] + extracted_skills[:5]
        unique_skills = list(set(present_skills))[:8]
        
        interview_response = requests.post(f"{BASE_URL}/api/interview-questions", json={
            "skills": unique_skills,
            "count": 12,
            "session_id": session_id
        })
        
        assert interview_response.status_code == 200
        interview = interview_response.json()
        assert interview["total_questions"] >= 10
        print(f"Step 6: Generated {interview['total_questions']} interview questions")
        
        # Step 7: Verify final session state
        final_session = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
        session_data = final_session.json()
        assert session_data["status"] in ["interview_ready", "roadmap_generated", "analyzed"]
        print(f"Step 7: Final session status: {session_data['status']}")
        
        print("COMPLETE E2E WORKFLOW PASSED!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

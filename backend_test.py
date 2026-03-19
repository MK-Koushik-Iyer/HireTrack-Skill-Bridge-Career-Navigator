#!/usr/bin/env python3
import requests
import sys
import json
import os
from datetime import datetime
from pathlib import Path

class SkillBridgeAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_result(self, test_name, passed, message, response_data=None):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "response": response_data
        }
        self.test_results.append(result)
        print(f"{status}: {test_name} - {message}")
        return passed

    def test_api_health(self):
        """Test basic API health"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            expected = "Skill-Bridge Navigator API is running"
            
            if response.status_code == 200 and expected in response.json().get("message", ""):
                return self.log_result("API Health Check", True, f"API is running (Status: {response.status_code})")
            else:
                return self.log_result("API Health Check", False, f"Unexpected response: {response.status_code}")
                
        except Exception as e:
            return self.log_result("API Health Check", False, f"Connection failed: {str(e)}")

    def test_get_jobs(self):
        """Test jobs endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/jobs", timeout=10)
            
            if response.status_code == 200:
                jobs = response.json()
                if isinstance(jobs, list) and len(jobs) > 0:
                    # Validate job structure
                    first_job = jobs[0]
                    required_fields = ["_id", "job_title", "required_skills", "level"]
                    
                    if all(field in first_job for field in required_fields):
                        return self.log_result("Get Jobs", True, f"Retrieved {len(jobs)} jobs successfully")
                    else:
                        return self.log_result("Get Jobs", False, f"Missing required fields in job: {first_job}")
                else:
                    return self.log_result("Get Jobs", False, f"Expected job array, got: {type(jobs)}")
            else:
                return self.log_result("Get Jobs", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            return self.log_result("Get Jobs", False, f"Error: {str(e)}")

    def test_upload_resume(self):
        """Test resume upload with sample PDF"""
        try:
            # Try to find sample resume
            sample_paths = [
                "/app/backend/sample_resume_junior.pdf",
                "/app/backend/sample_resume_senior.pdf",
                "/app/backend/sample_resume_switcher.pdf"
            ]
            
            sample_file = None
            for path in sample_paths:
                if os.path.exists(path):
                    sample_file = path
                    break
            
            if not sample_file:
                return self.log_result("Upload Resume", False, "No sample PDF found for testing")
            
            with open(sample_file, 'rb') as f:
                files = {'file': ('sample_resume.pdf', f, 'application/pdf')}
                response = requests.post(
                    f"{self.base_url}/api/upload-resume", 
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                data = response.json()
                if "resume_text" in data and "extracted_skills" in data:
                    skills_count = len(data["extracted_skills"])
                    return self.log_result("Upload Resume", True, f"PDF processed, extracted {skills_count} skills", {"skills": data["extracted_skills"][:5]})
                else:
                    return self.log_result("Upload Resume", False, f"Missing required fields in response: {data}")
            else:
                return self.log_result("Upload Resume", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            return self.log_result("Upload Resume", False, f"Error: {str(e)}")

    def test_analyze_gap(self, resume_text=None, job_id=None):
        """Test gap analysis"""
        try:
            # If no resume text provided, use a sample
            if not resume_text:
                resume_text = """
                John Doe
                Software Engineer
                
                Skills: Python, JavaScript, React, HTML, CSS, Git, MongoDB
                
                Experience:
                - Frontend Developer at Tech Corp (2 years)
                - Built web applications using React and JavaScript
                - Worked with REST APIs and MongoDB databases
                - Version control with Git
                """
            
            # Get a job ID if not provided
            if not job_id:
                jobs_response = requests.get(f"{self.base_url}/api/jobs", timeout=10)
                if jobs_response.status_code == 200:
                    jobs = jobs_response.json()
                    if jobs:
                        job_id = jobs[0]["_id"]
                    else:
                        return self.log_result("Analyze Gap", False, "No jobs available for analysis")
                else:
                    return self.log_result("Analyze Gap", False, "Could not fetch jobs for analysis")
            
            # Test both LLM and fallback modes
            for use_fallback in [False, True]:
                mode = "Fallback (Regex)" if use_fallback else "LLM"
                
                payload = {
                    "resume_text": resume_text,
                    "job_id": job_id,
                    "use_fallback": use_fallback
                }
                
                response = requests.post(
                    f"{self.base_url}/api/analyze", 
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    required_fields = ["matched_skills", "missing_skills", "match_percentage"]
                    
                    if all(field in data for field in required_fields):
                        match_pct = data["match_percentage"]
                        matched_count = len(data["matched_skills"])
                        missing_count = len(data["missing_skills"])
                        
                        self.log_result(
                            f"Analyze Gap ({mode})", 
                            True, 
                            f"Analysis complete: {match_pct}% match, {matched_count} matched, {missing_count} missing",
                            {
                                "match_percentage": match_pct,
                                "matched_skills": data["matched_skills"][:3],
                                "missing_skills": data["missing_skills"][:3]
                            }
                        )
                    else:
                        self.log_result(f"Analyze Gap ({mode})", False, f"Missing required fields: {data}")
                else:
                    self.log_result(f"Analyze Gap ({mode})", False, f"Status: {response.status_code}, Response: {response.text}")
                    
        except Exception as e:
            return self.log_result("Analyze Gap", False, f"Error: {str(e)}")

    def test_roadmap_generation(self):
        """Test learning roadmap generation"""
        try:
            # Test with common missing skills
            missing_skills = ["Docker", "Kubernetes", "Machine Learning", "AWS"]
            
            payload = {
                "missing_skills": missing_skills
            }
            
            response = requests.post(
                f"{self.base_url}/api/roadmap", 
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "courses" in data and "projects" in data:
                    courses_count = len(data["courses"])
                    projects_count = len(data["projects"])
                    
                    # Validate course structure if courses exist
                    if courses_count > 0:
                        first_course = data["courses"][0]
                        course_fields = ["title", "provider", "duration_hours", "price"]
                        
                        if all(field in first_course for field in course_fields):
                            return self.log_result(
                                "Roadmap Generation", 
                                True, 
                                f"Generated roadmap: {courses_count} courses, {projects_count} projects",
                                {
                                    "sample_course": {
                                        "title": first_course.get("title"),
                                        "provider": first_course.get("provider"),
                                        "duration": first_course.get("duration_hours"),
                                        "is_premium": first_course.get("is_premium", False)
                                    }
                                }
                            )
                        else:
                            return self.log_result("Roadmap Generation", False, f"Invalid course structure: {first_course}")
                    else:
                        return self.log_result("Roadmap Generation", True, f"Generated roadmap: {courses_count} courses, {projects_count} projects")
                else:
                    return self.log_result("Roadmap Generation", False, f"Missing courses/projects in response: {data}")
            else:
                return self.log_result("Roadmap Generation", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            return self.log_result("Roadmap Generation", False, f"Error: {str(e)}")

    def test_interview_questions(self):
        """Test interview questions generation"""
        try:
            test_skills = ["Python", "Docker", "JavaScript"]
            
            for skill in test_skills:
                payload = {"skill": skill}
                
                response = requests.post(
                    f"{self.base_url}/api/interview-questions", 
                    json=payload,
                    timeout=20
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "questions" in data and isinstance(data["questions"], list):
                        questions_count = len(data["questions"])
                        
                        # Should have 6 questions
                        if questions_count >= 6:
                            self.log_result(
                                f"Interview Questions ({skill})", 
                                True, 
                                f"Generated {questions_count} questions",
                                {"sample_questions": data["questions"][:2]}
                            )
                        else:
                            self.log_result(f"Interview Questions ({skill})", False, f"Expected 6 questions, got {questions_count}")
                    else:
                        self.log_result(f"Interview Questions ({skill})", False, f"Invalid questions format: {data}")
                else:
                    self.log_result(f"Interview Questions ({skill})", False, f"Status: {response.status_code}, Response: {response.text}")
                    
        except Exception as e:
            return self.log_result("Interview Questions", False, f"Error: {str(e)}")

    def test_error_handling(self):
        """Test API error handling"""
        try:
            # Test invalid job ID
            payload = {
                "resume_text": "test resume",
                "job_id": "invalid-job-id",
                "use_fallback": False
            }
            
            response = requests.post(f"{self.base_url}/api/analyze", json=payload, timeout=10)
            
            if response.status_code == 404:
                self.log_result("Error Handling (Invalid Job)", True, "Correctly returns 404 for invalid job ID")
            else:
                self.log_result("Error Handling (Invalid Job)", False, f"Expected 404, got {response.status_code}")
            
            # Test empty resume upload
            files = {'file': ('empty.pdf', b'', 'application/pdf')}
            response = requests.post(f"{self.base_url}/api/upload-resume", files=files, timeout=10)
            
            if response.status_code == 400 or response.status_code == 500:
                self.log_result("Error Handling (Empty PDF)", True, f"Correctly handles empty PDF: {response.status_code}")
            else:
                self.log_result("Error Handling (Empty PDF)", False, f"Expected 400/500, got {response.status_code}")
                
        except Exception as e:
            self.log_result("Error Handling", False, f"Error: {str(e)}")

    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting Skill-Bridge Navigator API Tests...")
        print("=" * 60)
        
        # Core functionality tests
        self.test_api_health()
        self.test_get_jobs()
        self.test_upload_resume()
        self.test_analyze_gap()
        self.test_roadmap_generation()
        self.test_interview_questions()
        self.test_error_handling()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("⚠️ SOME TESTS FAILED - Check logs above")
            return 1

    def save_results(self, filename="backend_test_results.json"):
        """Save test results to file"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "success_rate": (self.tests_passed/self.tests_run*100) if self.tests_run > 0 else 0,
            "test_details": self.test_results
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📄 Results saved to {filename}")

if __name__ == "__main__":
    # Use environment variable or default
    base_url = os.getenv("REACT_APP_BACKEND_URL", "http://localhost:8001")
    
    tester = SkillBridgeAPITester(base_url)
    exit_code = tester.run_all_tests()
    tester.save_results("/app/test_reports/backend_test_results.json")
    
    sys.exit(exit_code)
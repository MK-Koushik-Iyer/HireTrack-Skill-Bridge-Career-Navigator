import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function App() {
  // Core state
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeText, setResumeText] = useState('');
  const [extractedSkills, setExtractedSkills] = useState([]);
  const [manualSkills, setManualSkills] = useState([]);
  const [newSkill, setNewSkill] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [roadmap, setRoadmap] = useState(null);
  const [interviewData, setInterviewData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('upload');
  
  // Session management
  const [sessionId, setSessionId] = useState(null);
  const [userId, setUserId] = useState(() => {
    // Get or create a persistent user ID
    let id = localStorage.getItem('skillbridge_user_id');
    if (!id) {
      id = 'user_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('skillbridge_user_id', id);
    }
    return id;
  });
  const [pastSessions, setPastSessions] = useState([]);
  const [showSessionHistory, setShowSessionHistory] = useState(false);
  const [sessionFilter, setSessionFilter] = useState({ minMatch: '', maxMatch: '', jobTitle: '' });
  
  // AI status
  const [aiStatus, setAiStatus] = useState({ message: '', isAi: true });
  const [extractionInsights, setExtractionInsights] = useState(null);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/jobs`);
      setJobs(response.data);
      if (response.data.length > 0) {
        setSelectedJob(response.data[0]._id);
      }
    } catch (error) {
      console.error('Error fetching jobs:', error);
    }
  };

  const fetchPastSessions = useCallback(async () => {
    try {
      let url = `${API_URL}/api/sessions?user_id=${userId}&limit=20`;
      if (sessionFilter.jobTitle) {
        url += `&job_title=${encodeURIComponent(sessionFilter.jobTitle)}`;
      }
      if (sessionFilter.minMatch) {
        url += `&min_match=${sessionFilter.minMatch}`;
      }
      if (sessionFilter.maxMatch) {
        url += `&max_match=${sessionFilter.maxMatch}`;
      }
      
      const response = await axios.get(url);
      setPastSessions(response.data.sessions || []);
    } catch (error) {
      console.error('Error fetching sessions:', error);
    }
  }, [userId, sessionFilter]);

  useEffect(() => {
    if (showSessionHistory) {
      fetchPastSessions();
    }
  }, [showSessionHistory, fetchPastSessions]);

  const createNewSession = async () => {
    try {
      const response = await axios.post(`${API_URL}/api/sessions/create`, { user_id: userId });
      setSessionId(response.data.session_id);
      return response.data.session_id;
    } catch (error) {
      console.error('Error creating session:', error);
      return null;
    }
  };

  const resetForNewUpload = async () => {
    // Clear all state for a fresh start
    setResumeFile(null);
    setResumeText('');
    setExtractedSkills([]);
    setManualSkills([]);
    setAnalysis(null);
    setRoadmap(null);
    setInterviewData(null);
    setExtractionInsights(null);
    setAiStatus({ message: '', isAi: true });
    setActiveTab('upload');
    
    // Create a new session
    await createNewSession();
  };

  const loadSession = async (session) => {
    setShowSessionHistory(false);
    
    if (session.analysis) {
      setAnalysis(session.analysis);
      
      // Find the job
      const job = jobs.find(j => j._id === session.analysis.job_id);
      if (job) {
        setSelectedJob(job._id);
      }
      
      setActiveTab('analysis');
    }
    
    setSessionId(session.id);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setResumeFile(file);
    setLoading(true);
    setAiStatus({ message: 'Analyzing resume with AI...', isAi: true });

    // Create session if not exists
    let currentSessionId = sessionId;
    if (!currentSessionId) {
      currentSessionId = await createNewSession();
    }

    const formData = new FormData();
    formData.append('file', file);
    if (currentSessionId) {
      formData.append('session_id', currentSessionId);
    }

    try {
      const response = await axios.post(`${API_URL}/api/upload-resume?session_id=${currentSessionId || ''}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setResumeText(response.data.resume_text);
      setExtractedSkills(response.data.extracted_skills);
      setExtractionInsights(response.data.extraction_insights);
      
      // Update AI status based on extraction method
      if (response.data.extraction_insights?.is_fallback) {
        setAiStatus({ 
          message: 'AI unavailable - Using keyword-based extraction', 
          isAi: false 
        });
      } else {
        setAiStatus({ 
          message: `AI extracted ${response.data.extracted_skills.length} skills`, 
          isAi: true 
        });
      }
      
      // Clear previous analysis since resume changed
      setAnalysis(null);
      setRoadmap(null);
      setInterviewData(null);
      
    } catch (error) {
      alert('Error uploading resume: ' + (error.response?.data?.detail || error.message));
      setAiStatus({ message: '', isAi: true });
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!resumeText || !selectedJob) {
      alert('Please upload a resume and select a job');
      return;
    }

    setLoading(true);
    setAiStatus({ message: 'Performing semantic skill matching...', isAi: true });

    try {
      const allUserSkills = [...extractedSkills, ...manualSkills];
      
      const response = await axios.post(`${API_URL}/api/analyze`, {
        resume_text: resumeText,
        job_id: selectedJob,
        user_skills: allUserSkills,
        session_id: sessionId
      });
      
      setAnalysis(response.data);
      setActiveTab('analysis');
      
      setAiStatus({ 
        message: `Semantic matching: ${response.data.match_percentage}% match`, 
        isAi: true 
      });
      
      // Clear roadmap and interview since job changed
      setRoadmap(null);
      setInterviewData(null);
      
    } catch (error) {
      alert('Error analyzing gap: ' + (error.response?.data?.detail || error.message));
      setAiStatus({ message: '', isAi: true });
    } finally {
      setLoading(false);
    }
  };

  const handleGetRoadmap = async () => {
    if (!analysis || analysis.missing_skills.length === 0) {
      alert('No missing skills to generate roadmap');
      return;
    }

    setLoading(true);
    setAiStatus({ message: 'AI generating personalized learning path...', isAi: true });

    try {
      const response = await axios.post(`${API_URL}/api/roadmap`, {
        missing_skills: analysis.missing_skills,
        job_title: analysis.job_title,
        session_id: sessionId
      });
      
      setRoadmap(response.data);
      setActiveTab('roadmap');
      
      setAiStatus({ 
        message: response.data.ai_recommendations ? 'AI roadmap generated' : 'Roadmap generated (AI tips unavailable)', 
        isAi: !!response.data.ai_recommendations 
      });
      
    } catch (error) {
      alert('Error generating roadmap: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateInterviewQuestions = async () => {
    // Use MATCHED skills + manual skills (skills PRESENT in resume)
    const presentSkills = [...(analysis?.matched_skills || []), ...manualSkills, ...extractedSkills];
    const uniqueSkills = [...new Set(presentSkills)];
    
    if (uniqueSkills.length === 0) {
      alert('No skills found to generate interview questions');
      return;
    }

    setLoading(true);
    setAiStatus({ message: 'AI generating interview questions based on YOUR skills...', isAi: true });

    try {
      const response = await axios.post(`${API_URL}/api/interview-questions`, {
        skills: uniqueSkills.slice(0, 8), // Top 8 skills
        count: 12, // Generate 12 questions
        session_id: sessionId
      });
      
      setInterviewData(response.data);
      setActiveTab('interview');
      
      setAiStatus({ 
        message: `${response.data.total_questions} interview questions generated`, 
        isAi: true 
      });
      
    } catch (error) {
      alert('Error generating questions: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const addManualSkill = () => {
    if (newSkill.trim() && !extractedSkills.includes(newSkill.trim()) && !manualSkills.includes(newSkill.trim())) {
      setManualSkills([...manualSkills, newSkill.trim()]);
      setNewSkill('');
      // Clear analysis since skills changed
      setAnalysis(null);
      setRoadmap(null);
      setInterviewData(null);
    }
  };

  const removeManualSkill = (skill) => {
    setManualSkills(manualSkills.filter(s => s !== skill));
    // Clear analysis since skills changed
    setAnalysis(null);
    setRoadmap(null);
    setInterviewData(null);
  };

  const selectedJobData = jobs.find(j => j._id === selectedJob);
  const totalUserSkills = extractedSkills.length + manualSkills.length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-bg via-slate-900 to-dark-bg text-white">
      {/* Header */}
      <header className="border-b border-slate-700 bg-dark-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-r from-bridge-purple to-bridge-blue rounded-lg flex items-center justify-center">
                <span className="text-2xl">&#x1F309;</span>
              </div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-bridge-purple to-bridge-blue bg-clip-text text-transparent">
                Skill-Bridge Navigator
              </h1>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* AI Status Indicator */}
              {aiStatus.message && (
                <div className={`px-3 py-1 rounded-full text-sm flex items-center space-x-2 ${
                  aiStatus.isAi ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
                }`} data-testid="ai-status">
                  <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: aiStatus.isAi ? '#4ade80' : '#facc15' }}></span>
                  <span>{aiStatus.message}</span>
                </div>
              )}
              
              {/* Session History Button */}
              <button
                onClick={() => setShowSessionHistory(!showSessionHistory)}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors flex items-center space-x-2"
                data-testid="history-button"
              >
                <span>&#x1F4C2;</span>
                <span>History</span>
              </button>
              
              {/* New Analysis Button */}
              <button
                onClick={resetForNewUpload}
                className="px-4 py-2 bg-bridge-purple hover:bg-purple-600 rounded-lg transition-colors flex items-center space-x-2"
                data-testid="new-analysis-button"
              >
                <span>&#x2795;</span>
                <span>New Analysis</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Session History Sidebar */}
      {showSessionHistory && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40" onClick={() => setShowSessionHistory(false)}>
          <div className="absolute right-0 top-0 h-full w-96 bg-dark-card border-l border-slate-700 p-6 overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold">Past Analyses</h2>
              <button onClick={() => setShowSessionHistory(false)} className="text-gray-400 hover:text-white">
                &#x2715;
              </button>
            </div>
            
            {/* Filters */}
            <div className="space-y-3 mb-6">
              <input
                type="text"
                placeholder="Filter by job title..."
                value={sessionFilter.jobTitle}
                onChange={(e) => setSessionFilter(prev => ({ ...prev, jobTitle: e.target.value }))}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:outline-none focus:border-bridge-purple"
                data-testid="filter-job-title"
              />
              <div className="flex space-x-2">
                <input
                  type="number"
                  placeholder="Min %"
                  value={sessionFilter.minMatch}
                  onChange={(e) => setSessionFilter(prev => ({ ...prev, minMatch: e.target.value }))}
                  className="w-1/2 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:outline-none focus:border-bridge-purple"
                  data-testid="filter-min-match"
                />
                <input
                  type="number"
                  placeholder="Max %"
                  value={sessionFilter.maxMatch}
                  onChange={(e) => setSessionFilter(prev => ({ ...prev, maxMatch: e.target.value }))}
                  className="w-1/2 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-sm focus:outline-none focus:border-bridge-purple"
                  data-testid="filter-max-match"
                />
              </div>
              <button
                onClick={fetchPastSessions}
                className="w-full px-4 py-2 bg-bridge-blue hover:bg-blue-600 rounded-lg text-sm transition-colors"
                data-testid="apply-filters-button"
              >
                Apply Filters
              </button>
            </div>
            
            {/* Session List */}
            <div className="space-y-3">
              {pastSessions.length === 0 ? (
                <p className="text-gray-400 text-center py-8">No past analyses found</p>
              ) : (
                pastSessions.map((session, idx) => (
                  <div
                    key={session.id}
                    onClick={() => loadSession(session)}
                    className="p-4 bg-slate-800 rounded-lg border border-slate-700 hover:border-bridge-purple cursor-pointer transition-colors"
                    data-testid={`session-item-${idx}`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium">{session.analysis?.job_title || 'No analysis'}</span>
                      {session.analysis && (
                        <span className={`px-2 py-1 rounded text-xs ${
                          session.analysis.match_percentage >= 70 ? 'bg-green-500/20 text-green-400' :
                          session.analysis.match_percentage >= 40 ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-red-500/20 text-red-400'
                        }`}>
                          {session.analysis.match_percentage}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">
                      {new Date(session.created_at).toLocaleDateString()} at {new Date(session.created_at).toLocaleTimeString()}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="container mx-auto px-6 py-4">
        <div className="flex space-x-2 border-b border-slate-700">
          {['upload', 'analysis', 'roadmap', 'interview'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              data-testid={`tab-${tab}`}
              className={`px-6 py-3 font-medium transition-all ${
                activeTab === tab
                  ? 'border-b-2 border-bridge-purple text-bridge-purple'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab === 'upload' && `Upload Resume ${totalUserSkills > 0 ? `(${totalUserSkills} skills)` : ''}`}
              {tab === 'analysis' && `Gap Analysis ${analysis ? `(${analysis.match_percentage}%)` : ''}`}
              {tab === 'roadmap' && `Learning Roadmap ${roadmap ? `(${roadmap.courses.length + roadmap.projects.length} resources)` : ''}`}
              {tab === 'interview' && `Mock Interview ${interviewData ? `(${interviewData.total_questions} Qs)` : ''}`}
            </button>
          ))}
        </div>
      </div>

      <div className="container mx-auto px-6 py-8">
        {/* Upload Tab */}
        {activeTab === 'upload' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-dark-card rounded-xl p-8 border border-slate-700">
              <h2 className="text-2xl font-bold mb-4">Upload Your Resume</h2>
              <p className="text-gray-400 mb-6">Upload a PDF resume to begin your AI-powered skill analysis</p>
              
              <div className="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center hover:border-bridge-purple transition-colors">
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  className="hidden"
                  id="resume-upload"
                  data-testid="resume-upload-input"
                />
                <label htmlFor="resume-upload" className="cursor-pointer block">
                  <div className="text-6xl mb-4">&#x1F4CE;</div>
                  <p className="text-lg mb-2">Click to upload or drag and drop</p>
                  <p className="text-sm text-gray-500">PDF files only</p>
                </label>
                <button
                  onClick={() => document.getElementById('resume-upload').click()}
                  className="mt-4 px-6 py-2 bg-bridge-purple hover:bg-purple-600 rounded-lg transition-colors"
                  data-testid="resume-upload-button"
                >
                  Browse Files
                </button>
              </div>

              {resumeFile && (
                <div className="mt-6 p-4 bg-slate-800 rounded-lg flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-400">Uploaded: {resumeFile.name}</p>
                    {extractionInsights && (
                      <p className="text-xs text-gray-500 mt-1">
                        Extraction: {extractionInsights.extraction_method}
                        {extractionInsights.is_fallback && ' (Fallback mode)'}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={resetForNewUpload}
                    className="text-sm text-red-400 hover:text-red-300"
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>

            {extractedSkills.length > 0 && (
              <div className="bg-dark-card rounded-xl p-8 border border-slate-700">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-bold">Extracted Skills ({extractedSkills.length})</h3>
                  {extractionInsights?.is_fallback && (
                    <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 rounded-full text-sm" data-testid="fallback-indicator">
                      Approximate Analysis
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 mb-6">
                  {extractedSkills.map((skill, idx) => (
                    <span key={idx} className="px-3 py-1 bg-bridge-purple/20 text-bridge-purple rounded-full text-sm" data-testid={`extracted-skill-${idx}`}>
                      {skill}
                    </span>
                  ))}
                </div>

                <h3 className="text-xl font-bold mb-4">Add Skills Manually</h3>
                <p className="text-gray-400 text-sm mb-4">Add any skills the AI might have missed from your resume</p>
                <div className="flex space-x-2 mb-4">
                  <input
                    type="text"
                    value={newSkill}
                    onChange={(e) => setNewSkill(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addManualSkill()}
                    placeholder="Enter a skill..."
                    className="flex-1 px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg focus:outline-none focus:border-bridge-purple"
                    data-testid="manual-skill-input"
                  />
                  <button
                    onClick={addManualSkill}
                    className="px-6 py-2 bg-bridge-blue hover:bg-blue-600 rounded-lg transition-colors"
                    data-testid="add-skill-button"
                  >
                    Add
                  </button>
                </div>

                {manualSkills.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    {manualSkills.map((skill, idx) => (
                      <span key={idx} className="px-3 py-1 bg-bridge-blue/20 text-bridge-blue rounded-full text-sm flex items-center space-x-2" data-testid={`manual-skill-${idx}`}>
                        <span>{skill}</span>
                        <button onClick={() => removeManualSkill(skill)} className="text-red-400 hover:text-red-300">&#x00D7;</button>
                      </span>
                    ))}
                  </div>
                )}

                <div className="mt-6">
                  <label className="block text-sm font-medium mb-2">Select Target Job</label>
                  <select
                    value={selectedJob || ''}
                    onChange={(e) => {
                      setSelectedJob(e.target.value);
                      setAnalysis(null);
                      setRoadmap(null);
                      setInterviewData(null);
                    }}
                    className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg focus:outline-none focus:border-bridge-purple"
                    data-testid="job-select"
                  >
                    {jobs.map(job => (
                      <option key={job._id} value={job._id}>
                        {job.job_title} ({job.level}) - {job.required_skills?.length || 0} required skills
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={handleAnalyze}
                  disabled={loading}
                  className="w-full mt-6 px-6 py-3 bg-gradient-to-r from-bridge-purple to-bridge-blue hover:from-purple-600 hover:to-blue-600 rounded-lg font-semibold transition-all disabled:opacity-50"
                  data-testid="analyze-button"
                >
                  {loading ? 'Analyzing with AI...' : 'Analyze Skills Gap (Semantic Matching)'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Analysis Tab */}
        {activeTab === 'analysis' && analysis && (
          <div className="max-w-6xl mx-auto space-y-6">
            <div className="bg-dark-card rounded-xl p-8 border border-slate-700">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-3xl font-bold">Gap Analysis Dashboard</h2>
                <div className="text-right">
                  <p className="text-sm text-gray-400">Target Position</p>
                  <p className="text-xl font-bold text-bridge-purple">{selectedJobData?.job_title}</p>
                </div>
              </div>

              {/* Match Percentage */}
              <div className="mb-8 p-6 bg-gradient-to-r from-bridge-purple/20 to-bridge-blue/20 rounded-lg border border-bridge-purple/30">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-400 mb-1">Semantic Skills Match</p>
                    <p className="text-5xl font-bold" data-testid="match-percentage">{analysis.match_percentage}%</p>
                    <p className="text-xs text-gray-500 mt-2">Powered by AI semantic matching</p>
                  </div>
                  <div className="text-6xl">
                    {analysis.match_percentage >= 80 ? '\u{1F3AF}' : analysis.match_percentage >= 50 ? '\u{1F4C8}' : '\u{1F680}'}
                  </div>
                </div>
              </div>

              {/* Skills Grid */}
              <div className="grid md:grid-cols-3 gap-6">
                {/* Matched Skills */}
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-6">
                  <h3 className="text-lg font-bold text-green-400 mb-4 flex items-center" data-testid="matched-skills-header">
                    <span className="mr-2">&#x2705;</span> Matched Skills ({analysis.matched_skills.length})
                  </h3>
                  <div className="space-y-2">
                    {analysis.matched_skills.map((skill, idx) => (
                      <div key={idx} className="px-3 py-2 bg-green-500/20 rounded text-sm" data-testid={`matched-skill-${idx}`}>
                        {skill}
                        {analysis.semantic_scores?.[skill] && (
                          <span className="text-xs text-green-300 ml-2">
                            ({Math.round(analysis.semantic_scores[skill].similarity * 100)}% match)
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Missing Skills */}
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6">
                  <h3 className="text-lg font-bold text-red-400 mb-4 flex items-center" data-testid="missing-skills-header">
                    <span className="mr-2">&#x274C;</span> Missing Skills ({analysis.missing_skills.length})
                  </h3>
                  <div className="space-y-2">
                    {analysis.missing_skills.map((skill, idx) => (
                      <div key={idx} className="px-3 py-2 bg-red-500/20 rounded text-sm" data-testid={`missing-skill-${idx}`}>
                        {skill}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Transferable Skills */}
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-6">
                  <h3 className="text-lg font-bold text-yellow-400 mb-4 flex items-center" data-testid="transferable-skills-header">
                    <span className="mr-2">&#x26A1;</span> Transferable Skills ({analysis.transferable_skills.length})
                  </h3>
                  <div className="space-y-2">
                    {analysis.transferable_skills.length > 0 ? (
                      analysis.transferable_skills.map((skill, idx) => (
                        <div key={idx} className="px-3 py-2 bg-yellow-500/20 rounded text-sm" data-testid={`transferable-skill-${idx}`}>
                          {skill}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-gray-500">No transferable skills identified</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex space-x-4 mt-8">
                {analysis.missing_skills.length > 0 && (
                  <button
                    onClick={handleGetRoadmap}
                    disabled={loading}
                    className="flex-1 px-6 py-3 bg-gradient-to-r from-bridge-purple to-bridge-blue hover:from-purple-600 hover:to-blue-600 rounded-lg font-semibold transition-all disabled:opacity-50"
                    data-testid="generate-roadmap-button"
                  >
                    {loading ? 'Generating...' : 'Generate Learning Roadmap'}
                  </button>
                )}
                
                <button
                  onClick={handleGenerateInterviewQuestions}
                  disabled={loading}
                  className="flex-1 px-6 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg font-semibold transition-all disabled:opacity-50"
                  data-testid="generate-interview-button"
                >
                  {loading ? 'Generating...' : 'Prepare for Interview (Based on YOUR Skills)'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Roadmap Tab */}
        {activeTab === 'roadmap' && roadmap && (
          <div className="max-w-6xl mx-auto space-y-6">
            <div className="bg-dark-card rounded-xl p-8 border border-slate-700">
              <h2 className="text-3xl font-bold mb-6">Your Learning Roadmap</h2>
              <p className="text-gray-400 mb-8">AI-curated resources to bridge your skill gaps</p>

              {/* AI Recommendations */}
              {roadmap.ai_recommendations && (
                <div className="mb-8 p-6 bg-gradient-to-r from-bridge-purple/10 to-bridge-blue/10 rounded-lg border border-bridge-purple/30">
                  <h3 className="text-xl font-bold mb-4 flex items-center">
                    <span className="mr-2">&#x1F916;</span> AI Learning Advice
                  </h3>
                  <div className="prose prose-invert max-w-none text-gray-300 whitespace-pre-wrap">
                    {roadmap.ai_recommendations}
                  </div>
                </div>
              )}

              {/* Courses */}
              <div className="mb-12">
                <h3 className="text-2xl font-bold mb-6 flex items-center">
                  <span className="mr-2">&#x1F393;</span> Recommended Courses ({roadmap.courses.length})
                </h3>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {roadmap.courses.map((course, idx) => (
                    <div key={idx} className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-bridge-purple transition-colors" data-testid={`course-${idx}`}>
                      <div className="flex justify-between items-start mb-3">
                        <h4 className="font-bold text-lg">{course.title}</h4>
                        {course.is_premium && (
                          <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded">PREMIUM</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-400 mb-3">{course.provider}</p>
                      <div className="flex flex-wrap gap-2 mb-4">
                        {course.skill_tags?.map((tag, i) => (
                          <span key={i} className="px-2 py-1 bg-bridge-purple/20 text-bridge-purple text-xs rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">&#x23F1; {course.duration_hours}h</span>
                        <span className="text-gray-400">{course.difficulty}</span>
                      </div>
                      <div className="mt-4 flex justify-between items-center">
                        <span className="font-bold text-bridge-blue">
                          {course.price === 0 ? 'FREE' : `$${course.price}`}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Projects */}
              <div>
                <h3 className="text-2xl font-bold mb-6 flex items-center">
                  <span className="mr-2">&#x1F6E0;</span> Hands-On Projects ({roadmap.projects.length})
                </h3>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {roadmap.projects.map((project, idx) => (
                    <div key={idx} className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-bridge-blue transition-colors" data-testid={`project-${idx}`}>
                      <h4 className="font-bold text-lg mb-3">{project.title}</h4>
                      <p className="text-sm text-gray-400 mb-3">{project.provider}</p>
                      <div className="flex flex-wrap gap-2 mb-4">
                        {project.skill_tags?.map((tag, i) => (
                          <span key={i} className="px-2 py-1 bg-bridge-blue/20 text-bridge-blue text-xs rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                      <div className="flex justify-between text-sm text-gray-400">
                        <span>&#x23F1; {project.duration_hours}h</span>
                        <span>{project.difficulty}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Button to generate interview */}
              <div className="mt-8">
                <button
                  onClick={handleGenerateInterviewQuestions}
                  disabled={loading}
                  className="w-full px-6 py-3 bg-gradient-to-r from-bridge-purple to-bridge-blue hover:from-purple-600 hover:to-blue-600 rounded-lg font-semibold transition-all disabled:opacity-50"
                  data-testid="roadmap-interview-button"
                >
                  {loading ? 'Generating...' : 'Practice Interview Questions (Based on YOUR Skills)'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Interview Tab */}
        {activeTab === 'interview' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-dark-card rounded-xl p-8 border border-slate-700">
              <h2 className="text-3xl font-bold mb-2">Mock Interview Questions</h2>
              <p className="text-gray-400 mb-8">
                {interviewData 
                  ? `${interviewData.total_questions} questions based on skills in YOUR resume`
                  : 'Generate interview questions tailored to your skills'
                }
              </p>

              {!interviewData && (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">&#x1F3AF;</div>
                  <p className="text-gray-400 mb-6">
                    Interview questions are generated based on skills PRESENT in your resume, not missing skills.
                    This helps you prepare for questions you're likely to face.
                  </p>
                  <button
                    onClick={handleGenerateInterviewQuestions}
                    disabled={loading || extractedSkills.length === 0}
                    className="px-8 py-3 bg-gradient-to-r from-bridge-purple to-bridge-blue hover:from-purple-600 hover:to-blue-600 rounded-lg font-semibold transition-all disabled:opacity-50"
                    data-testid="generate-questions-main"
                  >
                    {loading ? 'Generating...' : 'Generate Interview Questions'}
                  </button>
                </div>
              )}

              {interviewData && (
                <>
                  {/* Skills covered */}
                  <div className="mb-6 p-4 bg-slate-800 rounded-lg">
                    <p className="text-sm text-gray-400 mb-2">Skills covered in this interview:</p>
                    <div className="flex flex-wrap gap-2">
                      {interviewData.skills_covered?.map((skill, idx) => (
                        <span key={idx} className="px-3 py-1 bg-bridge-purple/20 text-bridge-purple rounded-full text-sm">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  {/* Questions by skill */}
                  {interviewData.questions_by_skill && Object.entries(interviewData.questions_by_skill).map(([skill, questions]) => (
                    <div key={skill} className="mb-8 bg-slate-800 rounded-lg p-6 border border-slate-700">
                      <h3 className="text-xl font-bold mb-6 text-bridge-purple" data-testid={`interview-skill-${skill}`}>
                        {skill} ({questions.length} questions)
                      </h3>
                      <div className="space-y-4">
                        {questions.map((question, idx) => (
                          <div key={idx} className="p-4 bg-dark-card rounded-lg border border-slate-600" data-testid={`interview-question-${skill}-${idx}`}>
                            <div className="flex items-start space-x-3">
                              <span className="flex-shrink-0 w-8 h-8 bg-bridge-blue rounded-full flex items-center justify-center text-sm font-bold">
                                {idx + 1}
                              </span>
                              <p className="flex-1 pt-1">{question}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  
                  {/* Regenerate button */}
                  <button
                    onClick={handleGenerateInterviewQuestions}
                    disabled={loading}
                    className="w-full mt-4 px-6 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg font-semibold transition-all disabled:opacity-50"
                    data-testid="regenerate-questions"
                  >
                    {loading ? 'Generating...' : 'Generate New Questions'}
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {/* Loading Overlay */}
        {loading && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-dark-card rounded-xl p-8 border border-slate-700 max-w-md">
              <div className="animate-spin w-16 h-16 border-4 border-bridge-purple border-t-transparent rounded-full mx-auto mb-4"></div>
              <p className="text-center text-gray-400">{aiStatus.message || 'Processing...'}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

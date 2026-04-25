import pytest
from unittest import mock
import hashlib
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.resume_service import ResumeService
from app.models.orm import Resume, User, MatchCache

# A mock for the background task to avoid actually calling Celery
@pytest.fixture(autouse=True)
def mock_celery_task():
    with mock.patch("app.services.resume_service.analyze_resume_task.delay") as m:
        yield m

@pytest.mark.asyncio
async def test_same_file_uploaded_twice_creates_one_resume(db_session: AsyncSession, test_user: User):
    cv_bytes = b"Dummy CV Content for testing deduplication"
    
    # First upload
    resume1, was_dup1 = await ResumeService.upload_resume(
        user_id=str(test_user.id),
        file_bytes=cv_bytes,
        filename="cv1.pdf",
        db=db_session
    )
    assert not was_dup1
    
    # Second upload with same bytes
    resume2, was_dup2 = await ResumeService.upload_resume(
        user_id=str(test_user.id),
        file_bytes=cv_bytes,
        filename="cv2.pdf",
        db=db_session
    )
    assert was_dup2
    assert resume1.id == resume2.id
    
    # Check total resumes for user
    resumes = await ResumeService.get_user_resumes(str(test_user.id), db_session)
    assert len(resumes) == 1

@pytest.mark.asyncio
async def test_same_file_different_users_creates_two_resumes(db_session: AsyncSession, test_user: User, test_user_2: User):
    cv_bytes = b"Dummy CV Content for testing deduplication across users"
    
    # Upload for user 1
    resume1, _ = await ResumeService.upload_resume(
        user_id=str(test_user.id),
        file_bytes=cv_bytes,
        filename="cv.pdf",
        db=db_session
    )
    
    # Upload for user 2
    resume2, _ = await ResumeService.upload_resume(
        user_id=str(test_user_2.id),
        file_bytes=cv_bytes,
        filename="cv.pdf",
        db=db_session
    )
    
    assert resume1.id != resume2.id
    
    resumes1 = await ResumeService.get_user_resumes(str(test_user.id), db_session)
    assert len(resumes1) == 1
    
    resumes2 = await ResumeService.get_user_resumes(str(test_user_2.id), db_session)
    assert len(resumes2) == 1

@pytest.mark.asyncio
async def test_match_analysis_cached_on_second_call(db_session: AsyncSession, test_user: User):
    # Setup a dummy analyzed resume
    resume_id = uuid.uuid4()
    resume = Resume(
        id=resume_id,
        user_id=test_user.id,
        filename="test.pdf",
        cv_text="Python, AWS",
        file_hash="hash",
        is_analyzed=True,
        analyzed_profile={"detected_skills": ["Python"]}
    )
    db_session.add(resume)
    await db_session.commit()
    
    jd_text = "We need a Python developer."
    
    # Mock the LLM agent
    with mock.patch("app.agents.match_analyzer.run_match_analyzer") as mock_agent:
        mock_agent.return_value = {"match_report": {"global_match_score": 90.0}}
        
        # First call should miss cache and call agent
        r1, was_cached1 = await ResumeService.get_match_analysis(str(resume_id), jd_text, db_session)
        assert not was_cached1
        assert r1["global_match_score"] == 90.0
        mock_agent.assert_called_once()
        
        # Second call should hit cache and NOT call agent
        r2, was_cached2 = await ResumeService.get_match_analysis(str(resume_id), jd_text, db_session)
        assert was_cached2
        assert r2 == r1
        mock_agent.assert_called_once() # Still 1 call

@pytest.mark.asyncio
async def test_session_creation_does_not_trigger_analysis(db_session: AsyncSession, test_user: User):
    # The session creation flow test would go here.
    # In the new architecture, the create_session API just uses the resume_id.
    pass

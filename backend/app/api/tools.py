import logging
import httpx
import urllib.parse
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from app.api.resumes import validate_job_description

logger = logging.getLogger(__name__)

router = APIRouter()

class ExtractJobRequest(BaseModel):
    url: str

@router.post("/extract-job-url")
async def extract_job_url(request: ExtractJobRequest) -> Dict[str, Any]:
    url = request.url.strip()
    
    # Basic URL validation
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid URL format. Must start with http:// or https://")
        
    # Handle LinkedIn URLs with currentJobId (e.g. from collections/recommended)
    if "linkedin.com" in url.lower() and "currentjobid=" in url.lower():
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        # Handle both camelCase and lowercase (just in case)
        job_id = None
        for key in query_params:
            if key.lower() == "currentjobid":
                job_id = query_params[key][0]
                break
        
        if job_id:
            # Rewrite URL to the direct public view
            url = f"https://www.linkedin.com/jobs/view/{job_id}"
            
    # Block obviously generic non-job pages
    blocked_domains = [
        "linkedin.com/feed", "linkedin.com/home", "linkedin.com/mynetwork", 
        "linkedin.com/messaging", "linkedin.com/notifications",
        "indeed.com/?", "indeed.com/m/$" # Base domains without job details
    ]
    
    # But make sure we don't block valid ones. If it has /jobs/view, it's valid.
    is_linkedin_job = "linkedin.com/jobs/view" in url.lower()
    
    if not is_linkedin_job and (any(blocked in url.lower() for blocked in blocked_domains) or url.strip().strip("/") in ["https://www.linkedin.com", "https://linkedin.com", "https://www.indeed.com", "https://indeed.com"]):
        raise HTTPException(status_code=400, detail="Please provide a direct link to a specific job posting, not a general feed or homepage.")

    try:
        # Fetch the URL
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Send standard browser headers to avoid basic blocks
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            html_content = response.text
            
            # Parse HTML
            soup = BeautifulSoup(html_content, "html.parser")
            
            extracted_title = ""
            extracted_text = ""
            
            # LinkedIn specific targeted extraction
            if "linkedin.com" in url.lower():
                # Extract Title
                title_tag = soup.find("h1") or soup.find("title")
                if title_tag:
                    extracted_title = title_tag.get_text(strip=True).replace(" | LinkedIn", "").strip()
                    
                # Extract Description Body specifically
                # LinkedIn uses show-more-less-html__markup for the description body
                body_container = soup.find("div", class_="show-more-less-html__markup")
                if not body_container:
                    # Fallback to description meta or article
                    body_container = soup.find("article") or soup.find("main")
                    
                if body_container:
                    # Remove unwanted tags
                    for el in body_container(["script", "style", "nav", "header", "footer", "aside"]):
                        el.extract()
                    text = body_container.get_text(separator="\n")
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    extracted_text = '\n'.join(chunk for chunk in chunks if chunk)
            else:
                # Generic extraction
                title_tag = soup.find("title")
                if title_tag:
                    extracted_title = title_tag.get_text(strip=True)
                
                for el in soup(["script", "style", "nav", "header", "footer", "aside"]):
                    el.extract()
                text = soup.get_text(separator="\n")
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                extracted_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            if not extracted_text:
                raise HTTPException(status_code=422, detail="We could not extract any text from this URL. It might be blocking scrapers or requires a login.")

            # Run through our existing validation logic
            validation_error = validate_job_description(extracted_text)
            
            # Additional check: If it's a linkedin page but we only got navigation/auth text
            if "linkedin.com" in url.lower() and ("sign in" in extracted_text.lower() or "join now" in extracted_text.lower()) and len(extracted_text) < 500:
                raise HTTPException(status_code=422, detail="LinkedIn blocked automatic extraction. Please copy and paste the job description manually.")
                
            if validation_error:
                # Add context to the error since it came from a URL
                raise HTTPException(
                    status_code=422, 
                    detail=f"We extracted text from the URL, but it doesn't look like a valid job description. {validation_error}"
                )
                
            # Format nicely for the frontend text area
            final_text = f"Title: {extracted_title}\nURL: {url}\n\n{extracted_text}" if extracted_title else f"URL: {url}\n\n{extracted_text}"
                
            return {
                "extracted_text": final_text,
                "source_url": url
            }
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error extracting job URL {url}: {e}")
        status = e.response.status_code
        if status in (401, 403, 999): # LinkedIn often returns 999
            raise HTTPException(status_code=422, detail="LinkedIn blocked automatic extraction. Please copy and paste the job description manually.")
        raise HTTPException(status_code=422, detail=f"Failed to fetch the URL. Server returned status {status}.")
    except httpx.RequestError as e:
        logger.error(f"Request error extracting job URL {url}: {e}")
        raise HTTPException(status_code=400, detail="Failed to connect to the URL. Please check if the link is correct and publicly accessible.")
    except Exception as e:
        logger.error(f"Unexpected error extracting job URL {url}: {e}")
        # Only re-raise if it's already an HTTPException from our validation
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=422, detail="We could not extract a valid job description from this URL. Please paste the job description manually.")

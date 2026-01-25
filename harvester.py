import os
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class JobHarvester:
    """Fetch jobs from multiple job boards API"""
    
    def __init__(self, canada_wide: bool = False):
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        self.canada_wide = canada_wide
        self.now = datetime.now(timezone.utc)
        self.cutoff_48h = self.now - timedelta(hours=48)
        self.cutoff_12h = self.now - timedelta(hours=12)
        self.debug_info = {
            "serpapi_key_loaded": bool(self.serpapi_key),
            "serpapi_fetched": 0,
            "serpapi_after_filter": 0,
            "remotive_fetched": 0,
            "remotive_after_filter": 0,
            "workday_fetched": 0,
            "workday_after_filter": 0,
            "adzuna_fetched": 0,
            "adzuna_after_filter": 0,
            "http_status": None,
            "http_error": None,
        }
    
    def parse_iso_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse ISO 8601 datetime string to UTC datetime"""
        try:
            if date_str.endswith('Z'):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif '+' in date_str or date_str.count('-') > 2:
                return datetime.fromisoformat(date_str)
            else:
                return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return None
    
    def parse_posted_at_extension(self, extension_str: str) -> Optional[datetime]:
        """
        Parse SerpAPI's detected_extensions.posted_at format
        Examples: "2 days ago", "1 hour ago", "30 minutes ago", "Just now"
        Returns UTC datetime, or None if unparsable
        """
        if not extension_str or not isinstance(extension_str, str):
            return None
        
        extension_str = extension_str.strip().lower()
        
        try:
            # Handle "Just now"
            if "just now" in extension_str:
                return self.now
            
            # Extract number and unit: "2 days ago" -> (2, "days")
            parts = extension_str.split()
            if len(parts) < 2:
                return None
            
            num_str = parts[0]
            if num_str == "a":  # "a day ago" -> treat as 1
                num = 1
                unit = parts[1] if len(parts) > 1 else ""
            else:
                num = int(num_str)
                unit = parts[1] if len(parts) > 1 else ""
            
            # Parse unit (day, hour, minute, week, month)
            if "day" in unit:
                delta = timedelta(days=num)
            elif "hour" in unit:
                delta = timedelta(hours=num)
            elif "minute" in unit or "min" in unit:
                delta = timedelta(minutes=num)
            elif "week" in unit:
                delta = timedelta(weeks=num)
            elif "month" in unit:
                delta = timedelta(days=num * 30)  # Approximate
            else:
                return None
            
            return self.now - delta
        
        except (ValueError, IndexError):
            return None
    
    def is_within_cutoff(self, posted_at: str) -> Tuple[bool, bool]:
        """
        Check if job is within 48h and 12h cutoff.
        Returns (within_48h, within_12h)
        If posted_at is missing/unparsable, returns (True, False) to KEEP the job
        """
        if not posted_at:
            return True, False
        
        parsed_date = self.parse_iso_datetime(posted_at)
        if not parsed_date:
            return True, False
        
        within_48h = parsed_date >= self.cutoff_48h
        within_12h = parsed_date >= self.cutoff_12h
        return within_48h, within_12h
    
    def get_remotive_jobs(self) -> List[Dict]:
        """Fetch jobs from Remotive API (no authentication required)"""
        jobs = []
        page = 1
        max_pages = 5  # Limit to first 5 pages (500 jobs max)
        
        while page <= max_pages:
            try:
                url = f"https://remotive.com/api/remote-jobs?limit=100&page={page}"
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("jobs"):
                    break
                
                page_has_valid = False
                for job in data["jobs"]:
                    within_48h, within_12h = self.is_within_cutoff(job.get("publication_date", ""))
                    
                    if not within_48h:
                        continue
                    
                    page_has_valid = True
                    job_obj = {
                        "title": job.get("title", "N/A"),
                        "company": job.get("company_name", "N/A"),
                        "location": job.get("job_geo_location", "Remote"),
                        "url": job.get("url", ""),
                        "posted_at": job.get("publication_date", ""),
                        "source": "Remotive",
                        "priority": 1 if within_12h else 0,
                    }
                    
                    if job_obj["url"]:
                        jobs.append(job_obj)
                
                # Stop if no jobs within cutoff found on this page
                if not page_has_valid:
                    break
                
                page += 1
                
            except requests.RequestException as e:
                print(f"Warning: Error fetching Remotive page {page}: {e}")
                break
            except (KeyError, ValueError) as e:
                print(f"Warning: Error parsing Remotive data: {e}")
                break
        
        self.debug_info["remotive_fetched"] = len(jobs)
        self.debug_info["remotive_after_filter"] = len(jobs)
        print(f"✓ Fetched {len(jobs)} jobs from Remotive")
        return jobs
    
    def get_serpapi_jobs(self) -> List[Dict]:
        """Fetch jobs from Google Jobs via SerpAPI"""
        if not self.serpapi_key:
            print("⚠ Warning: SERPAPI_KEY not set. Skipping Google Jobs.")
            return []
        
        jobs = []
        
        # Define search attempts based on canada_wide toggle
        if self.canada_wide:
            search_attempts = [
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Canada",
                    "attempt_name": "Canada-wide search"
                },
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Toronto, Ontario, Canada",
                    "attempt_name": "Toronto search"
                },
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Vancouver, British Columbia, Canada",
                    "attempt_name": "Vancouver search"
                },
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Calgary, Alberta, Canada",
                    "attempt_name": "Calgary search"
                },
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Montreal, Quebec, Canada",
                    "attempt_name": "Montreal search"
                },
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Ottawa, Ontario, Canada",
                    "attempt_name": "Ottawa search"
                },
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Waterloo, Ontario, Canada",
                    "attempt_name": "Waterloo search"
                },
                {
                    "q": "remote data analyst OR bi analyst OR reporting analyst",
                    "location": None,
                    "attempt_name": "Remote (no location) search"
                }
            ]
        else:
            search_attempts = [
                {
                    "q": "Data Analyst OR BI Analyst OR Reporting Analyst",
                    "location": "Toronto, Ontario, Canada",
                    "attempt_name": "Toronto search"
                },
                {
                    "q": "remote data analyst OR bi analyst OR reporting analyst",
                    "location": None,
                    "attempt_name": "Remote (no location) search"
                }
            ]
        
        for attempt in search_attempts:
            try:
                url = "https://serpapi.com/search.json"
                params = {
                    "api_key": self.serpapi_key,
                    "engine": "google_jobs",
                    "q": attempt["q"],
                    "hl": "en",
                    "num": 100,
                }
                
                if attempt["location"]:
                    params["location"] = attempt["location"]
                
                response = requests.get(url, params=params, timeout=15)
                self.debug_info["http_status"] = response.status_code
                
                # Log request details
                print(f"[SerpAPI] {attempt['attempt_name']}: HTTP {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                if "error" in data:
                    self.debug_info["http_error"] = data.get('error')
                    print(f"  ✗ API error: {data.get('error')}")
                    continue
                
                if "search_metadata" in data:
                    status = data["search_metadata"].get("status")
                    print(f"  Search status: {status}")
                
                job_results = data.get("jobs_results", [])
                attempt_jobs = []
                
                if not job_results:
                    print(f"  ℹ No jobs found in response")
                    continue
                
                print(f"  ✓ Found {len(job_results)} jobs in response")
                self.debug_info["serpapi_fetched"] = len(job_results)
                
                for job in job_results:
                    # Extract posted_at from extension string (e.g., "2 days ago")
                    extension_str = job.get("detected_extensions", {}).get("posted_at", "")
                    
                    # Try to parse the extension format ("2 days ago" -> datetime)
                    parsed_extension_dt = self.parse_posted_at_extension(extension_str)
                    
                    if parsed_extension_dt:
                        # Convert to ISO format UTC
                        posted_at_iso = parsed_extension_dt.isoformat()
                        within_48h = parsed_extension_dt >= self.cutoff_48h
                        within_12h = parsed_extension_dt >= self.cutoff_12h
                    else:
                        # Missing or unparsable: keep as "Unknown"
                        posted_at_iso = "Unknown"
                        within_48h = True  # KEEP jobs without dates
                        within_12h = False
                    
                    if not within_48h:
                        continue
                    
                    # Try multiple ways to get the job URL
                    job_url = job.get("job_link") or job.get("url") or ""
                    
                    if not job_url and "apply_options" in job:
                        apply_options = job.get("apply_options", [])
                        if apply_options and isinstance(apply_options, list):
                            job_url = apply_options[0].get("link", "")
                    
                    if not job_url:
                        continue
                    
                    job_obj = {
                        "title": job.get("title", "N/A"),
                        "company": job.get("company_name", "N/A"),
                        "location": job.get("location", "N/A"),
                        "url": job_url,
                        "posted_at": posted_at_iso,
                        "source": "Google Jobs",
                        "priority": 1 if within_12h else 0,
                    }
                    
                    attempt_jobs.append(job_obj)
                
                kept_after_filter = len(attempt_jobs)
                self.debug_info["serpapi_after_filter"] = kept_after_filter
                print(f"  ✓ Kept {kept_after_filter} jobs after 48h filter")
                
                jobs.extend(attempt_jobs)
                
                # If we got jobs, stop trying other attempts
                if jobs:
                    break
                
            except requests.exceptions.Timeout:
                print(f"  ✗ Timeout: Request took too long")
                self.debug_info["http_error"] = "Timeout"
            except requests.RequestException as e:
                print(f"  ✗ Network error: {e}")
                self.debug_info["http_error"] = str(e)
            except Exception as e:
                print(f"  ✗ Error: {e}")
                self.debug_info["http_error"] = str(e)
        
        print(f"✓ Fetched {len(jobs)} jobs from Google Jobs")
        return jobs
    
    def get_workday_jobs(self) -> List[Dict]:
        """
        Fetch jobs from Workday company boards via public JSON endpoints.
        Uses Workday's public job listing API if available.
        Does NOT scrape HTML - only uses official JSON APIs.
        """
        jobs = []
        total_fetched = 0
        
        # List of Canadian companies with known Workday job boards (public JSON endpoints)
        workday_companies = [
            {"name": "RBC", "domain": "rbc.wd1.myworkdayjobs.com", "company_name": "Royal Bank of Canada"},
            {"name": "TD", "domain": "td.wd5.myworkdayjobs.com", "company_name": "TD Bank"},
            {"name": "Scotiabank", "domain": "scotiabank.wd3.myworkdayjobs.com", "company_name": "Scotiabank"},
            {"name": "BMO", "domain": "bmo.wd5.myworkdayjobs.com", "company_name": "BMO Financial Group"},
            {"name": "CIBC", "domain": "cibc.wd3.myworkdayjobs.com", "company_name": "CIBC"},
        ]
        
        for company in workday_companies:
            try:
                # Workday public API endpoint for job listings
                url = f"https://{company['domain']}/wday/cxs/customreport/scholar?limit=100"
                
                print(f"[Workday] Fetching {company['name']} jobs...")
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    print(f"  ⚠ {company['name']}: HTTP {response.status_code} - skipping")
                    continue
                
                data = response.json()
                job_results = data.get("jobPostings", []) or data.get("jobs", [])
                
                if not job_results:
                    print(f"  ℹ {company['name']}: No jobs found")
                    continue
                
                company_fetched = len(job_results)
                total_fetched += company_fetched
                print(f"  ✓ Found {company_fetched} jobs from {company['name']}")
                
                for job in job_results:
                    # Extract job details from Workday format
                    posted_at = job.get("postedOn", "") or job.get("datePosted", "")
                    
                    # Parse Workday date format if needed
                    parsed_posted_dt = None
                    if posted_at:
                        parsed_posted_dt = self.parse_iso_datetime(posted_at)
                    
                    # Check 48h filter
                    if parsed_posted_dt:
                        within_48h = parsed_posted_dt >= self.cutoff_48h
                        within_12h = parsed_posted_dt >= self.cutoff_12h
                    else:
                        # Keep jobs without dates
                        within_48h = True
                        within_12h = False
                        posted_at = "Unknown"
                    
                    if not within_48h:
                        continue
                    
                    job_url = job.get("url") or job.get("jobUrl") or job.get("externalPath", "")
                    if not job_url:
                        continue
                    
                    # Ensure URL is complete
                    if not job_url.startswith("http"):
                        job_url = f"https://{company['domain']}{job_url}"
                    
                    job_obj = {
                        "title": job.get("title", "") or job.get("jobTitle", "N/A"),
                        "company": company["company_name"],
                        "location": job.get("location", "") or job.get("jobLocation", {}).get("name", "Canada"),
                        "url": job_url,
                        "posted_at": posted_at if isinstance(posted_at, str) else (parsed_posted_dt.isoformat() if parsed_posted_dt else "Unknown"),
                        "source": "Workday",
                        "priority": 1 if within_12h else 0,
                    }
                    
                    jobs.append(job_obj)
                
            except requests.exceptions.Timeout:
                print(f"  ✗ {company['name']}: Request timeout - skipping")
            except requests.exceptions.RequestException as e:
                print(f"  ✗ {company['name']}: Network error - {str(e)[:50]} - skipping")
            except ValueError as e:
                print(f"  ✗ {company['name']}: Invalid JSON response - skipping")
            except KeyError as e:
                print(f"  ✗ {company['name']}: Missing expected field {e} - skipping")
            except Exception as e:
                print(f"  ✗ {company['name']}: Unexpected error - {str(e)[:50]} - skipping")
        
        self.debug_info["workday_fetched"] = total_fetched
        self.debug_info["workday_after_filter"] = len(jobs)
        print(f"✓ Fetched {len(jobs)} total jobs from Workday")
        return jobs
    
    def get_adzuna_jobs(self) -> List[Dict]:
        """Fetch jobs from Adzuna Canada API (no authentication required for basic search)"""
        jobs = []
        
        try:
            # Adzuna Canada API endpoint
            # API is free to use without key for basic searches, but limited to 1000 results per call
            url = "https://api.adzuna.com/v1/api/jobs/ca/search/1"
            
            keywords = ["Data Analyst", "BI Analyst", "Reporting Analyst", "Business Analyst"]
            
            for keyword in keywords:
                try:
                    params = {
                        "app_id": os.getenv("ADZUNA_APP_ID", ""),
                        "app_key": os.getenv("ADZUNA_APP_KEY", ""),
                        "what": keyword,
                        "results_per_page": 50,
                        "sort_by": "date",
                    }
                    
                    # Skip if no API credentials
                    if not params["app_id"] or not params["app_key"]:
                        print("⚠ Warning: ADZUNA_APP_ID or ADZUNA_APP_KEY not set. Skipping Adzuna.")
                        self.debug_info["adzuna_fetched"] = 0
                        self.debug_info["adzuna_after_filter"] = 0
                        return []
                    
                    print(f"[Adzuna] Searching for '{keyword}'...")
                    response = requests.get(url, params=params, timeout=15)
                    response.raise_for_status()
                    data = response.json()
                    
                    job_results = data.get("results", [])
                    
                    if not job_results:
                        print(f"  ℹ No jobs found for '{keyword}'")
                        continue
                    
                    print(f"  ✓ Found {len(job_results)} jobs for '{keyword}'")
                    self.debug_info["adzuna_fetched"] += len(job_results)
                    
                    for job in job_results:
                        # Parse posting date
                        posted_at = job.get("created", "")
                        
                        parsed_posted_dt = None
                        if posted_at:
                            parsed_posted_dt = self.parse_iso_datetime(posted_at)
                        
                        # Check 48h filter
                        if parsed_posted_dt:
                            within_48h = parsed_posted_dt >= self.cutoff_48h
                            within_12h = parsed_posted_dt >= self.cutoff_12h
                        else:
                            # Keep jobs without dates
                            within_48h = True
                            within_12h = False
                            posted_at = "Unknown"
                        
                        if not within_48h:
                            continue
                        
                        job_url = job.get("redirect_url", "")
                        if not job_url:
                            continue
                        
                        job_obj = {
                            "title": job.get("title", "N/A"),
                            "company": job.get("company", {}).get("display_name", "N/A") if isinstance(job.get("company"), dict) else job.get("company", "N/A"),
                            "location": job.get("location", {}).get("display_name", "Canada") if isinstance(job.get("location"), dict) else job.get("location", "Canada"),
                            "url": job_url,
                            "posted_at": posted_at if isinstance(posted_at, str) else (parsed_posted_dt.isoformat() if parsed_posted_dt else "Unknown"),
                            "source": "Adzuna Canada",
                            "priority": 1 if within_12h else 0,
                        }
                        
                        jobs.append(job_obj)
                
                except requests.exceptions.Timeout:
                    print(f"  ✗ Timeout for '{keyword}': Request took too long")
                except requests.RequestException as e:
                    print(f"  ✗ Network error for '{keyword}': {str(e)[:50]}")
                except Exception as e:
                    print(f"  ✗ Error for '{keyword}': {str(e)[:50]}")
        
        except Exception as e:
            print(f"✗ Adzuna error: {str(e)[:100]}")
        
        self.debug_info["adzuna_after_filter"] = len(jobs)
        print(f"✓ Fetched {len(jobs)} jobs from Adzuna Canada")
        return jobs
    
    def fetch_all_jobs(self) -> List[Dict]:
        """Fetch and combine jobs from all sources"""
        all_jobs = []
        
        all_jobs.extend(self.get_remotive_jobs())
        all_jobs.extend(self.get_serpapi_jobs())
        all_jobs.extend(self.get_workday_jobs())
        all_jobs.extend(self.get_adzuna_jobs())
        
        return all_jobs
    
    def get_debug_info(self) -> Dict:
        """Return debug information about the harvest"""
        return self.debug_info
    
    def deduplicate_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """
        Deduplicate jobs by URL, title, and company.
        Keeps jobs with higher priority (within 12h).
        """
        seen = {}
        deduped = []
        
        # Sort by priority (highest first) to keep best duplicates
        sorted_jobs = sorted(jobs, key=lambda x: x.get("priority", 0), reverse=True)
        
        for job in sorted_jobs:
            # Create a composite key
            key = (job.get("url", ""), job.get("title", ""), job.get("company", ""))
            
            if key not in seen:
                seen[key] = True
                deduped.append(job)
        
        return deduped

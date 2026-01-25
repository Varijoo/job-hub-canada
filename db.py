import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Optional
import os

class JobDatabase:
    """SQLite database for job management"""
    
    def __init__(self, db_path: str = "jobs.sqlite"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                source TEXT,
                posted_at TEXT,
                added_at TEXT NOT NULL,
                status TEXT DEFAULT 'New',
                priority INTEGER DEFAULT 0,
                applied_at TEXT,
                follow_up_at TEXT,
                notes TEXT DEFAULT ''
            )
        """)
        
        # Add columns if they don't exist (migration for existing databases)
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "applied_at" not in columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN applied_at TEXT")
        if "follow_up_at" not in columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN follow_up_at TEXT")
        if "notes" not in columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN notes TEXT DEFAULT ''")
        
        conn.commit()
        conn.close()
    
    def job_exists(self, url: str, title: str, company: str) -> bool:
        """Check if a job already exists in database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM jobs WHERE url = ? AND title = ? AND company = ?
        """, (url, title, company))
        
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def add_job(self, job: Dict) -> bool:
        """Add a new job to database. Returns True if added, False if already exists"""
        if self.job_exists(job.get("url", ""), job.get("title", ""), job.get("company", "")):
            return False
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO jobs (url, title, company, location, source, posted_at, added_at, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("url", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("source", ""),
                job.get("posted_at", ""),
                datetime.now(timezone.utc).isoformat(),
                job.get("priority", 0)
            ))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def add_jobs_batch(self, jobs: List[Dict]) -> int:
        """Add multiple jobs. Returns count of jobs added"""
        count = 0
        for job in jobs:
            if self.add_job(job):
                count += 1
        return count
    
    def get_all_jobs(self) -> List[Dict]:
        """Get all jobs from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url, title, company, location, source, posted_at, status, added_at, applied_at, follow_up_at, notes
            FROM jobs
            ORDER BY priority DESC, added_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        jobs = []
        for row in rows:
            jobs.append({
                "id": row[0],
                "url": row[1],
                "title": row[2],
                "company": row[3],
                "location": row[4],
                "source": row[5],
                "posted_at": row[6],
                "status": row[7],
                "added_at": row[8],
                "applied_at": row[9],
                "follow_up_at": row[10],
                "notes": row[11] or "",
            })
        
        return jobs
    
    def get_jobs_by_status(self, status: str) -> List[Dict]:
        """Get jobs filtered by status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url, title, company, location, source, posted_at, status, added_at, applied_at, follow_up_at, notes
            FROM jobs
            WHERE status = ?
            ORDER BY priority DESC, added_at DESC
        """, (status,))
        
        rows = cursor.fetchall()
        conn.close()
        
        jobs = []
        for row in rows:
            jobs.append({
                "id": row[0],
                "url": row[1],
                "title": row[2],
                "company": row[3],
                "location": row[4],
                "source": row[5],
                "posted_at": row[6],
                "status": row[7],
                "added_at": row[8],
                "applied_at": row[9],
                "follow_up_at": row[10],
                "notes": row[11] or "",
            })
        
        return jobs
    
    def update_job_status(self, job_id: int, status: str) -> bool:
        """Update job status. When status changes to 'Applied', set applied_at and follow_up_at (default 4 days)"""
        valid_statuses = ["New", "Saved", "Applied", "Rejected"]
        
        if status not in valid_statuses:
            return False
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # If setting to Applied, auto-set applied_at and follow_up_at
        if status == "Applied":
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            applied_at = now.isoformat()
            follow_up_at = (now + timedelta(days=4)).isoformat()
            
            cursor.execute("""
                UPDATE jobs SET status = ?, applied_at = ?, follow_up_at = ? WHERE id = ?
            """, (status, applied_at, follow_up_at, job_id))
        else:
            cursor.execute("""
                UPDATE jobs SET status = ? WHERE id = ?
            """, (status, job_id))
        
        conn.commit()
        conn.close()
        return True
    
    def update_notes(self, job_id: int, notes: str) -> bool:
        """Update job notes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE jobs SET notes = ? WHERE id = ?
        """, (notes, job_id))
        
        conn.commit()
        conn.close()
        return True
    
    def update_follow_up_at(self, job_id: int, follow_up_at: str) -> bool:
        """Update job follow_up_at date"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE jobs SET follow_up_at = ? WHERE id = ?
        """, (follow_up_at, job_id))
        
        conn.commit()
        conn.close()
        return True
    
    def delete_job(self, job_id: int) -> bool:
        """Delete a job from database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        return True
    
    def get_job_count(self) -> Dict[str, int]:
        """Get count of jobs by status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, COUNT(*) FROM jobs GROUP BY status
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        counts = {
            "New": 0,
            "Saved": 0,
            "Applied": 0,
            "Rejected": 0,
            "Total": len(self.get_all_jobs())
        }
        
        for status, count in rows:
            counts[status] = count
        
        return counts
    
    def calculate_posted_age(self, posted_at: str) -> str:
        """Calculate time since job was posted"""
        if not posted_at:
            return "N/A"
        
        try:
            posted_dt = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
            
            # Ensure timezone-aware in UTC
            if posted_dt.tzinfo is None:
                posted_dt = posted_dt.replace(tzinfo=timezone.utc)
            else:
                posted_dt = posted_dt.astimezone(timezone.utc)
            
            now = datetime.now(timezone.utc)
            delta = now - posted_dt
            
            seconds = int(delta.total_seconds())
            if seconds < 0:
                return "Just now"
            
            if seconds < 60:
                return f"{seconds}s ago"
            if seconds < 3600:
                return f"{seconds // 60}m ago"
            if seconds < 86400:
                return f"{seconds // 3600}h ago"
            return f"{seconds // 86400}d ago"
        except Exception:
            return "N/A"
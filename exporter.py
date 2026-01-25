import csv
from typing import List, Dict
from datetime import datetime, timezone
from db import JobDatabase


class JobExporter:
    """Export jobs to various formats"""
    
    def __init__(self, db: JobDatabase):
        self.db = db
    
    def export_to_markdown(self, output_file: str = "job_feed.md") -> bool:
        """Export jobs to Markdown format"""
        try:
            jobs = self.db.get_all_jobs()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Job Feed\n\n")
                f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
                
                # Group jobs by status
                jobs_by_status = {}
                for job in jobs:
                    status = job.get("status", "New")
                    if status not in jobs_by_status:
                        jobs_by_status[status] = []
                    jobs_by_status[status].append(job)
                
                # Write each status section
                for status in ["New", "Saved", "Applied", "Rejected"]:
                    if status in jobs_by_status:
                        jobs_list = jobs_by_status[status]
                        f.write(f"## {status} ({len(jobs_list)})\n\n")
                        
                        for job in jobs_list:
                            posted_age = self.db.calculate_posted_age(job.get("posted_at", ""))
                            
                            f.write(f"### {job.get('title', 'N/A')}\n")
                            f.write(f"- **Company**: {job.get('company', 'N/A')}\n")
                            f.write(f"- **Location**: {job.get('location', 'N/A')}\n")
                            f.write(f"- **Source**: {job.get('source', 'N/A')}\n")
                            f.write(f"- **Posted**: {posted_age}\n")
                            f.write(f"- **Status**: {status}\n")
                            f.write(f"- **Link**: [{job.get('url', '#')}]({job.get('url', '#')})\n\n")
                
                f.write("---\n")
                f.write(f"Total jobs: {len(jobs)}\n")
            
            return True
        except Exception as e:
            print(f"Error exporting to Markdown: {e}")
            return False
    
    def export_to_csv(self, output_file: str = "job_feed.csv") -> bool:
        """Export jobs to CSV format"""
        try:
            jobs = self.db.get_all_jobs()
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'Title',
                    'Company',
                    'Location',
                    'Source',
                    'Posted Age',
                    'Posted At',
                    'Status',
                    'URL'
                ]
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for job in jobs:
                    posted_age = self.db.calculate_posted_age(job.get("posted_at", ""))
                    
                    writer.writerow({
                        'Title': job.get('title', ''),
                        'Company': job.get('company', ''),
                        'Location': job.get('location', ''),
                        'Source': job.get('source', ''),
                        'Posted Age': posted_age,
                        'Posted At': job.get('posted_at', ''),
                        'Status': job.get('status', ''),
                        'URL': job.get('url', '')
                    })
            
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False
    
    def export_to_json(self, output_file: str = "job_feed.json") -> bool:
        """Export jobs to JSON format"""
        import json
        
        try:
            jobs = self.db.get_all_jobs()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return False

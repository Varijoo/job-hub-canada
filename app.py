import streamlit as st
from dotenv import load_dotenv
import os

# Load environment variables FIRST before importing modules that need them
load_dotenv()

from harvester import JobHarvester
from db import JobDatabase
from exporter import JobExporter

# Log SERPAPI_KEY status (do NOT print the key itself)
serpapi_loaded = bool(os.getenv("SERPAPI_KEY"))
print(f"SERPAPI_KEY loaded: {serpapi_loaded}")


# Page configuration
st.set_page_config(
    page_title="Job Hub",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "db" not in st.session_state:
    st.session_state.db = JobDatabase()

if "exporter" not in st.session_state:
    st.session_state.exporter = JobExporter(st.session_state.db)

if "refresh_needed" not in st.session_state:
    st.session_state.refresh_needed = False

if "target_companies" not in st.session_state:
    st.session_state.target_companies = []

if "target_roles" not in st.session_state:
    st.session_state.target_roles = [
        "Data Analyst",
        "BI Analyst", 
        "Reporting Analyst"
    ]

if "canada_wide" not in st.session_state:
    st.session_state.canada_wide = False


def calculate_priority_score(job: dict, target_roles: list, target_companies: list) -> int:
    """
    Calculate priority score (1-10) for a job based on:
    +2 if title matches target roles
    +2 if location matches Canada list (Toronto, Mississauga, Windsor, KW)
    +2 if posted <= 12h
    +1 if posted <= 48h
    +1 if company is in target list
    """
    score = 1  # Base score
    
    # +2 for matching target roles
    title_lower = job.get("title", "").lower()
    for role in target_roles:
        if role.lower() in title_lower:
            score += 2
            break
    
    # +2 for matching Canada locations
    location_lower = job.get("location", "").lower()
    canada_locations = ["toronto", "mississauga", "windsor", "kitchener", "waterloo", "kw"]
    if any(loc in location_lower for loc in canada_locations):
        score += 2
    
    # Check posted_at for time-based scoring
    posted_at = job.get("posted_at", "")
    if posted_at and posted_at != "Unknown":
        try:
            from datetime import datetime, timezone, timedelta
            
            # Parse ISO format
            if posted_at.endswith('Z'):
                posted_dt = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            else:
                posted_dt = datetime.fromisoformat(posted_at)
            
            # Ensure posted_dt is timezone-aware (UTC)
            if posted_dt.tzinfo is None:
                posted_dt = posted_dt.replace(tzinfo=timezone.utc)
            else:
                posted_dt = posted_dt.astimezone(timezone.utc)
            
            now = datetime.now(timezone.utc)
            hours_ago = (now - posted_dt).total_seconds() / 3600
            
            # +2 if posted <= 12h
            if hours_ago <= 12:
                score += 2
            # +1 if posted <= 48h
            elif hours_ago <= 48:
                score += 1
        except (ValueError, AttributeError, TypeError):
            pass
    
    # +1 for company in target list
    company_lower = job.get("company", "").lower()
    if target_companies:
        for company in target_companies:
            if company.lower() in company_lower or company_lower in company.lower():
                score += 1
                break
    
    # Cap at 10
    return min(score, 10)


def refresh_jobs():
    """Fetch new jobs from APIs and update database"""
    st.session_state.refresh_needed = True


def apply_filters(jobs: list, filters: dict) -> list:
    """Apply search and filter criteria to jobs list"""
    filtered = jobs
    
    # Search filter (title and company)
    if filters.get("search"):
        search_term = filters["search"]
        filtered = [
            job for job in filtered
            if search_term in job.get("title", "").lower() or
               search_term in job.get("company", "").lower()
        ]
    
    # Role filter
    role = filters.get("role", "Any")
    if role != "Any":
        filtered = [
            job for job in filtered
            if role.lower() in job.get("title", "").lower()
        ]
    
    # Location filter
    location = filters.get("location", "Any")
    if location != "Any":
        job_location = None
        filtered_by_location = []
        
        for job in filtered:
            job_loc = job.get("location", "").lower()
            
            # Map location filters
            if location == "Remote" and "remote" in job_loc:
                filtered_by_location.append(job)
            elif location == "Toronto" and "toronto" in job_loc:
                filtered_by_location.append(job)
            elif location == "Mississauga" and "mississauga" in job_loc:
                filtered_by_location.append(job)
            elif location == "Windsor" and "windsor" in job_loc:
                filtered_by_location.append(job)
            elif location == "KW" and ("kitchener" in job_loc or "waterloo" in job_loc or "kw" in job_loc):
                filtered_by_location.append(job)
        
        filtered = filtered_by_location
    
    # Source filter
    sources = filters.get("sources", [])
    if sources:
        filtered = [
            job for job in filtered
            if job.get("source") in sources
        ]
    
    # Add priority scores to each job
    for job in filtered:
        job["priority_score"] = calculate_priority_score(
            job,
            st.session_state.target_roles,
            st.session_state.target_companies
        )
    
    # Sort by priority score descending, then by posted_at descending
    filtered.sort(
        key=lambda x: (
            -x.get("priority_score", 1),  # Negative for descending
            x.get("posted_at", "")  # Secondary sort by posted_at
        ),
        reverse=False
    )
    
    return filtered


def refresh_jobs():
    """Fetch new jobs from APIs and update database"""
    st.session_state.refresh_needed = True


def main():
    st.title("💼 Job Hub")
    st.markdown("**Remote Job Board** - Aggregating opportunities from multiple sources")
    
    # Sidebar
    with st.sidebar:
        st.header("Actions")
        
        # Canada-wide toggle
        st.session_state.canada_wide = st.toggle(
            "🍁 Canada-wide Search",
            value=st.session_state.canada_wide,
            help="When ON, searches across Canada (Toronto, Vancouver, Calgary, Montreal, Ottawa, Waterloo, Remote Canada)"
        )
        
        st.divider()
        
        # Refresh button
        if st.button("🔄 Fetch New Jobs", use_container_width=True):
            refresh_jobs()
        
        st.divider()
        
        # Statistics
        st.subheader("Job Stats")
        counts = st.session_state.db.get_job_count()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total", counts["Total"])
            st.metric("New", counts["New"])
        with col2:
            st.metric("Saved", counts["Saved"])
            st.metric("Applied", counts["Applied"])
        
        st.divider()
        
        # Export section
        st.subheader("Export")
        
        if st.button("📥 Export to Markdown", use_container_width=True):
            if st.session_state.exporter.export_to_markdown():
                st.success("✓ Exported to job_feed.md")
            else:
                st.error("✗ Export failed")
        
        if st.button("📥 Export to CSV", use_container_width=True):
            if st.session_state.exporter.export_to_csv():
                st.success("✓ Exported to job_feed.csv")
            else:
                st.error("✗ Export failed")
        
        st.divider()
        
        # Filters section
        st.subheader("🔍 Filters")
        
        # Search text
        search_text = st.text_input(
            "Search Title/Company",
            placeholder="e.g., Data Analyst",
            help="Filter jobs by title or company name"
        )
        
        # Role dropdown
        roles = [
            "Any",
            "Data Analyst",
            "BI Analyst",
            "Reporting Analyst",
            "Business Analyst",
            "Data Scientist",
            "SQL Developer",
            "ETL Developer"
        ]
        selected_role = st.selectbox("Role", roles)
        
        # Location dropdown
        locations = ["Any", "Toronto", "Mississauga", "Windsor", "KW", "Remote"]
        selected_location = st.selectbox("Location", locations)
        
        # Source multiselect
        sources = st.multiselect(
            "Sources",
            ["Remotive", "Google Jobs", "Workday", "Adzuna Canada"],
            default=["Remotive", "Google Jobs"]
        )
        
        # Store filters in session state
        st.session_state.filters = {
            "search": search_text.lower().strip(),
            "role": selected_role,
            "location": selected_location,
            "sources": sources
        }
        
        st.divider()
        
        # Priority Scoring section
        st.subheader("⭐ Priority Settings")
        
        # Target companies
        st.caption("Target Companies (for scoring)")
        company_input = st.text_input(
            "Add company",
            placeholder="e.g., Acme Corp",
            help="Press Enter to add",
            key="company_input"
        )
        
        col_add, col_clear = st.columns([1, 1])
        with col_add:
            if st.button("Add", use_container_width=True, key="add_company"):
                if company_input.strip() and company_input not in st.session_state.target_companies:
                    st.session_state.target_companies.append(company_input.strip())
        
        with col_clear:
            if st.button("Clear All", use_container_width=True, key="clear_companies"):
                st.session_state.target_companies = []
        
        # Display target companies
        if st.session_state.target_companies:
            st.caption("Companies in list:")
            for company in st.session_state.target_companies:
                col_name, col_del = st.columns([4, 1])
                with col_name:
                    st.caption(f"• {company}")
                with col_del:
                    if st.button("✕", key=f"del_{company}", use_container_width=True):
                        st.session_state.target_companies.remove(company)
                        st.rerun()
    
    # Clear default filters on sidebar to avoid conflicts
    if "filters" not in st.session_state:
        st.session_state.filters = {
            "search": "",
            "role": "Any",
            "location": "Any",
            "sources": ["Remotive", "Google Jobs"]
        }
    
    # Main content
    if st.session_state.refresh_needed:
        with st.spinner("Fetching jobs from APIs..."):
            harvester = JobHarvester(canada_wide=st.session_state.canada_wide)
            raw_jobs = harvester.fetch_all_jobs()
            debug_info = harvester.get_debug_info()
            deduped_jobs = harvester.deduplicate_jobs(raw_jobs)
            
            added_count = st.session_state.db.add_jobs_batch(deduped_jobs)
            
            st.session_state.refresh_needed = False
            
            # Display results with debug counts
            st.success(f"✓ Added {added_count} new jobs! ({len(deduped_jobs)} total fetched)")
            
            # Show debug panel with per-source counts
            with st.expander("📊 Fetch Details"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Remotive Fetched", debug_info.get("remotive_fetched", 0))
                with col2:
                    st.metric("Google Jobs Fetched", debug_info.get("serpapi_fetched", 0))
                with col3:
                    st.metric("Workday Fetched", debug_info.get("workday_fetched", 0))
                with col4:
                    st.metric("Adzuna Fetched", debug_info.get("adzuna_fetched", 0))
                
                st.divider()
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Remotive After Filter", debug_info.get("remotive_after_filter", 0))
                with col2:
                    st.metric("Google Jobs After Filter", debug_info.get("serpapi_after_filter", 0))
                with col3:
                    st.metric("Workday After Filter", debug_info.get("workday_after_filter", 0))
                with col4:
                    st.metric("Adzuna After Filter", debug_info.get("adzuna_after_filter", 0))
                
                if debug_info.get("http_error"):
                    st.error(f"Error: {debug_info['http_error']}")
            
            st.rerun()
    
    # Tab interface
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["All Jobs", "New", "Saved", "Applied", "Follow-up", "Rejected"])
    
    with tab1:
        st.subheader("All Jobs")
        all_jobs = apply_filters(st.session_state.db.get_all_jobs(), st.session_state.filters)
        display_jobs_table(all_jobs, "all")
    
    with tab2:
        st.subheader("New Jobs")
        new_jobs = apply_filters(st.session_state.db.get_jobs_by_status("New"), st.session_state.filters)
        display_jobs_table(new_jobs, "new")
    
    with tab3:
        st.subheader("Saved Jobs")
        saved_jobs = apply_filters(st.session_state.db.get_jobs_by_status("Saved"), st.session_state.filters)
        display_jobs_table(saved_jobs, "saved")
    
    with tab4:
        st.subheader("Applied")
        applied_jobs = apply_filters(st.session_state.db.get_jobs_by_status("Applied"), st.session_state.filters)
        display_jobs_table(applied_jobs, "applied")
    
    with tab5:
        st.subheader("📅 Follow-up Needed")
        followup_jobs = get_follow_up_jobs()
        if followup_jobs:
            display_jobs_table(followup_jobs, "followup")
        else:
            st.info("No follow-ups needed right now!")
    
    with tab6:
        st.subheader("Rejected")
        rejected_jobs = apply_filters(st.session_state.db.get_jobs_by_status("Rejected"), st.session_state.filters)
        display_jobs_table(rejected_jobs, "rejected")


def get_follow_up_jobs() -> list:
    """Get Applied jobs that need follow-up, sorted by follow_up_at"""
    from datetime import datetime, timezone
    
    applied_jobs = st.session_state.db.get_jobs_by_status("Applied")
    followup_needed = []
    
    now = datetime.now(timezone.utc)
    
    for job in applied_jobs:
        follow_up_at = job.get("follow_up_at", "")
        
        if follow_up_at:
            try:
                follow_up_dt = datetime.fromisoformat(follow_up_at.replace("Z", "+00:00"))
                # Include jobs that are at or past their follow-up date
                if follow_up_dt <= now:
                    followup_needed.append((job, follow_up_dt))
            except (ValueError, AttributeError):
                pass
    
    # Sort by follow_up_at ascending (soonest first)
    followup_needed.sort(key=lambda x: x[1])
    return [job for job, _ in followup_needed]


def is_job_recent(posted_at: str) -> bool:
    """Check if job was posted within last 12 hours"""
    if not posted_at or posted_at == "Unknown":
        return False
    
    try:
        from datetime import datetime, timezone, timedelta
        
        # Try to parse ISO format
        if posted_at.endswith('Z'):
            posted_dt = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
        else:
            posted_dt = datetime.fromisoformat(posted_at)
        
        # Ensure posted_dt is timezone-aware (UTC)
        if posted_dt.tzinfo is None:
            posted_dt = posted_dt.replace(tzinfo=timezone.utc)
        else:
            posted_dt = posted_dt.astimezone(timezone.utc)
        
        now = datetime.now(timezone.utc)
        cutoff_12h = now - timedelta(hours=12)
        
        return posted_dt >= cutoff_12h
    except (ValueError, AttributeError, TypeError):
        return False


def display_jobs_table(jobs, tab_prefix="all"):
    """Display jobs in an interactive table"""
    if not jobs:
        st.info("No jobs found.")
        return
    
    # Display table header with score column
    col0, col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns(
        [0.5, 1, 1.2, 2, 1.5, 1, 1.8, 1, 1, 1.2],
        gap="small"
    )
    
    with col0:
        st.markdown("**⭐**")
    with col1:
        st.markdown("**Posted**")
    with col2:
        st.markdown("**Title**")
    with col3:
        st.markdown("**Company**")
    with col4:
        st.markdown("**Location**")
    with col5:
        st.markdown("**Source**")
    with col6:
        st.markdown("**Apply**")
    with col7:
        st.markdown("**Status**")
    with col8:
        st.markdown("")
    with col9:
        st.markdown("**Actions**")
    
    st.divider()
    
    # Display each job as a row
    for idx, job in enumerate(jobs):
        posted_age = st.session_state.db.calculate_posted_age(job.get("posted_at", ""))
        
        # Check if job is <= 12h old (hot job)
        is_hot = is_job_recent(job.get("posted_at", ""))
        
        # Get priority score
        priority_score = job.get("priority_score", 1)
        
        col0, col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns(
            [0.5, 1, 1.2, 2, 1, 0.8, 1.8, 1, 1, 1.2],
            gap="small"
        )
        
        with col0:
            # Display score with color coding
            if priority_score >= 8:
                st.markdown(f":green[**{priority_score}**]")
            elif priority_score >= 6:
                st.markdown(f":orange[**{priority_score}**]")
            else:
                st.markdown(f"{priority_score}")
        
        with col1:
            # Highlight hot jobs
            if is_hot:
                st.markdown(f":red[**{posted_age}**]")
            else:
                st.caption(posted_age)
        
        with col2:
            title_text = job["title"][:25] + "..." if len(job["title"]) > 25 else job["title"]
            if is_hot:
                st.markdown(f":red[**{title_text}**]")
            else:
                st.caption(title_text)
        
        with col3:
            company_text = job["company"][:20] + "..." if len(job["company"]) > 20 else job["company"]
            st.caption(company_text)
        
        with col4:
            location_text = job["location"][:15] + "..." if len(job["location"]) > 15 else job["location"]
            st.caption(location_text)
        
        with col5:
            st.caption(job["source"])
        
        with col6:
            apply_col, copy_col = st.columns([1.2, 1])
            with apply_col:
                st.link_button(
                    "Apply →",
                    url=job["url"],
                    use_container_width=True,
                    help=f"Open: {job['url']}"
                )
            with copy_col:
                if st.button(
                    "Copy",
                    key=f"copy_{tab_prefix}_{job['id']}",
                    use_container_width=True,
                    help="Copy URL to clipboard"
                ):
                    # Store URL in session for copying
                    st.session_state[f"clipboard_{tab_prefix}_{job['id']}"] = job["url"]
                    st.toast(f"📋 Copied: {job['url'][:50]}...", icon="✓")
        
        with col7:
            new_status = st.selectbox(
                "Status",
                ["New", "Saved", "Applied", "Rejected"],
                index=["New", "Saved", "Applied", "Rejected"].index(job["status"]),
                key=f"status_{tab_prefix}_{job['id']}",
                label_visibility="collapsed"
            )
            
            if new_status != job["status"]:
                st.session_state.db.update_job_status(job["id"], new_status)
                st.rerun()
        
        with col8:
            pass  # Spacer column
        
        with col9:
            if st.button("Delete", key=f"delete_{tab_prefix}_{job['id']}", use_container_width=True):
                st.session_state.db.delete_job(job["id"])
                st.rerun()
        
        # Notes and Follow-up section (expandable)
        with st.expander(f"📝 Notes & Follow-up ({job['title'][:20]}...)"):
            col_notes, col_followup = st.columns([2, 1])
            
            with col_notes:
                # Notes editor
                notes = st.text_area(
                    "Notes",
                    value=job.get("notes", ""),
                    placeholder="Add notes about this job...",
                    key=f"notes_input_{tab_prefix}_{job['id']}",
                    label_visibility="collapsed",
                    height=80
                )
                
                if st.button("Save Notes", key=f"save_notes_{tab_prefix}_{job['id']}", use_container_width=True):
                    st.session_state.db.update_notes(job["id"], notes)
                    st.toast("✓ Notes saved", icon="✓")
            
            with col_followup:
                st.caption("Follow-up:")
                if job.get("applied_at"):
                    st.caption(f"Applied: {job['applied_at'][:10]}")
                if job.get("follow_up_at"):
                    st.caption(f"Follow-up: {job['follow_up_at'][:10]}")
                    # Option to change follow-up date
                    if st.button("Reschedule", key=f"reschedule_{tab_prefix}_{job['id']}", use_container_width=True):
                        st.session_state[f"reschedule_{job['id']}"] = True
                        st.rerun()
                
                # If rescheduling, show date picker
                if st.session_state.get(f"reschedule_{job['id']}", False):
                    from datetime import datetime, timedelta, timezone
                    new_date = st.date_input(
                        "New follow-up date",
                        value=None,
                        key=f"followup_date_{tab_prefix}_{job['id']}"
                    )
                    if new_date:
                        new_followup = datetime.combine(new_date, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat()
                        st.session_state.db.update_follow_up_at(job["id"], new_followup)
                        st.session_state[f"reschedule_{job['id']}"] = False
                        st.toast("✓ Follow-up date updated", icon="✓")
                        st.rerun()
    
    st.divider()
    st.caption(f"Showing {len(jobs)} jobs")


if __name__ == "__main__":
    main()

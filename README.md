# Job Hub (Canada) 🇨🇦

A Streamlit job aggregator that collects the latest Data/Tech jobs across Canada and lets you track applications in one place.

## ✅ Features
- Fetch jobs from:
  - Google Jobs (SerpAPI)
  - Remotive
  - Workday (company boards)
- Canada-wide toggle (major hubs + Remote Canada)
- Filter last 48 hours (prioritize last 12 hours)
- Deduplicate jobs across sources
- Track status: New / Saved / Applied / Follow-up / Rejected
- Notes & Follow-up panel per job
- Export to CSV + Markdown

1. What it does (2–3 bullets)

2. How it works (pipeline)

3. Screenshots (2 images)

4. Run locally

5. Roadmap

## How it works
1) **Collect** jobs from multiple sources (API/search pages)
2) **Normalize** fields into one schema (title, company, location, date, link, source)
3) **De-duplicate** across sources (same job posted multiple times)
4) **Store** into SQLite (jobs + status + notes)
5) **Show** in Streamlit UI (filters, search, status tracking)


## Screenshots
![Job list](screenshots/ui-1.png)
![Tracking](screenshots/ui-2.png)



## 🧰 Setup (Windows)
```bash
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt

▶ Run
streamlit run app.py
App opens at:
http://localhost:8501

📌 Notes

No LinkedIn scraping (safe approach)

Uses SQLite locally (jobs.sqlite) for tracking





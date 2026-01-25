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



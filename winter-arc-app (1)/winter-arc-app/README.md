# ❄️ Winter Arc Tracker

Habit, diet, sleep and wake-up tracker with accounts, a database and an AI coach.
Python (Flask) + SQLite + a built-in smart coach (no API key). Every person who signs up gets their own private tracker.

## Folders
```
winter-arc-app/
├── app.py              # server: pages, login, database, /api/state, /api/coach
├── coach.py            # built-in smart coach (rules in plain Python)
├── templates/
│   ├── index.html      # the tracker (Track today, Progress, AI coach, Share)
│   └── login.html      # log in / create account
├── data/               # SQLite database is created here (winter.db)
├── requirements.txt
├── Procfile            # start command for hosts like Render / Railway
├── .env.example        # settings to copy
└── README.md
```

## Run on your computer
```bash
cd winter-arc-app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000, create an account and start tracking.
No API key is needed. The smart coach and caption writer are built into `coach.py`.

## Put it online (so anyone can open your link)
Example with Render (Railway and PythonAnywhere work the same way):
1. Push this folder to a GitHub repository.
2. Create a new **Web Service** from the repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
3. Add the environment variable `SECRET_KEY` (any long random text).
4. Add a **persistent disk** (for example mounted at `/var/data`) and set `DATA_DIR=/var/data`.
   Without a disk, free hosts erase the database on every restart.
5. Share the URL that the host gives you.

## Notes
- Passwords are stored hashed. Sessions last 90 days.
- Data is saved automatically half a second after each change.
- Back up by copying `data/winter.db`.

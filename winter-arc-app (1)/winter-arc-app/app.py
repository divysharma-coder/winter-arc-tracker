"""Winter Arc Tracker: Flask + SQLite + built-in smart coach (no API key needed)."""
import json, os, secrets, sqlite3, time
from html import escape

from flask import Flask, Response, g, jsonify, redirect, request, session
from coach import answer
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", os.path.join(BASE, "data"))
os.makedirs(DATA, exist_ok=True)
DB = os.path.join(DATA, "winter.db")


def load_secret():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = os.path.join(DATA, "secret.key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    return open(path).read().strip()


app = Flask(__name__)
app.secret_key = load_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 90,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)


# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            pw_hash TEXT NOT NULL,
            created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS states(
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            data TEXT NOT NULL,
            updated REAL NOT NULL);
        """
    )
    conn.commit()
    conn.close()


init_db()


def read(name):
    with open(os.path.join(BASE, "templates", name), encoding="utf-8") as f:
        return f.read()


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db().execute("SELECT id, username FROM users WHERE id=?", (uid,)).fetchone()


# ---------- pages ----------
@app.get("/")
def home():
    user = current_user()
    if not user:
        return redirect("/login")
    row = db().execute("SELECT data FROM states WHERE user_id=?", (user["id"],)).fetchone()
    state = row["data"] if row else "null"
    state = state.replace("</", "<\\/")
    page = (read("index.html")
            .replace("/*STATE*/null", state)
            .replace("@@USER@@", escape(user["username"])))
    return Response(page, mimetype="text/html")


def login_page(error="", status=200):
    return Response(read("login.html").replace("@@ERROR@@", escape(error)), status=status, mimetype="text/html")


@app.get("/login")
def login_form():
    return redirect("/") if current_user() else login_page()


@app.post("/login")
def login_submit():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    mode = request.form.get("mode", "login")
    if not (3 <= len(username) <= 30) or not username.replace("_", "").replace("-", "").isalnum():
        return login_page("Username must be 3 to 30 letters, numbers, - or _.", 400)
    if mode == "register":
        if len(password) < 6:
            return login_page("Password must be at least 6 characters.", 400)
        try:
            cur = db().execute(
                "INSERT INTO users(username, pw_hash, created) VALUES(?,?,?)",
                (username, generate_password_hash(password), time.time()))
            db().commit()
        except sqlite3.IntegrityError:
            return login_page("That username is taken. Pick another or log in.", 409)
        session.permanent = True
        session["uid"] = cur.lastrowid
        return redirect("/")
    row = db().execute("SELECT id, pw_hash FROM users WHERE username=?", (username,)).fetchone()
    if not row or not check_password_hash(row["pw_hash"], password):
        return login_page("Wrong username or password.", 401)
    session.permanent = True
    session["uid"] = row["id"]
    return redirect("/")


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.get("/healthz")
def health():
    return "ok"


# ---------- API ----------
@app.get("/api/state")
def get_state():
    user = current_user()
    if not user:
        return jsonify(error="login_required"), 401
    row = db().execute("SELECT data FROM states WHERE user_id=?", (user["id"],)).fetchone()
    return Response(row["data"] if row else "null", mimetype="application/json")


@app.post("/api/state")
def save_state():
    user = current_user()
    if not user:
        return jsonify(error="login_required"), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("days", {}), dict):
        return jsonify(error="bad_state"), 400
    db().execute(
        "INSERT INTO states(user_id, data, updated) VALUES(?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
        (user["id"], json.dumps(data), time.time()))
    db().commit()
    return jsonify(ok=True)


@app.post("/api/coach")
def coach():
    user = current_user()
    if not user:
        return jsonify(error="login_required"), 401
    prompt = str((request.get_json(silent=True) or {}).get("prompt", ""))[:6000]
    if not prompt.strip():
        return jsonify(error="empty_prompt"), 400
    return jsonify(text=answer(prompt))


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))

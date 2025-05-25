from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import psycopg2
import psycopg2.extras

app = Flask(__name__, static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True
CORS(app, supports_credentials=True)

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    # Create tables if they don't exist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS chats (
        chat_id UUID PRIMARY KEY,
        username TEXT NOT NULL,
        created TIMESTAMP DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        chat_id UUID NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created TIMESTAMP DEFAULT now()
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.before_first_request
def setup():
    init_db()

@app.route("/", methods=["GET"])
def root():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "User already exists"}), 400
    cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
    chat_id = str(uuid.uuid4())
    cur.execute("INSERT INTO chats (chat_id, username) VALUES (%s, %s)", (chat_id, username))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "User created successfully", "chat_id": chat_id})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if username == "Admin" and password == "SiETHOwROltu":
        session["username"] = username
        session["is_admin"] = True
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM chats WHERE username=%s", (username,))
        chats = cur.fetchall()
        if not chats:
            chat_id = str(uuid.uuid4())
            cur.execute("INSERT INTO chats (chat_id, username) VALUES (%s, %s)", (chat_id, username))
            conn.commit()
            chats = [{"chat_id": chat_id}]
        cur.close()
        conn.close()
        return jsonify({
            "message": "Login successful",
            "chats": [{"chat_id": c["chat_id"], "title": "New Chat"} for c in chats],
            "is_admin": True
        })
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Invalid credentials"}), 401
    session["username"] = username
    session["is_admin"] = False
    cur.execute("SELECT chat_id FROM chats WHERE username=%s", (username,))
    chats = cur.fetchall()
    if not chats:
        chat_id = str(uuid.uuid4())
        cur.execute("INSERT INTO chats (chat_id, username) VALUES (%s, %s)", (chat_id, username))
        conn.commit()
        chats = [{"chat_id": chat_id}]
    cur.close()
    conn.close()
    return jsonify({
        "message": "Login successful",
        "chats": [{"chat_id": c["chat_id"], "title": "New Chat"} for c in chats],
        "is_admin": False
    })

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    session.pop("is_admin", None)
    return jsonify({"message": "Logged out"})

@app.route("/new_chat", methods=["POST"])
def new_chat():
    if "username" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    username = session["username"]
    chat_id = str(uuid.uuid4())
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO chats (chat_id, username) VALUES (%s, %s)", (chat_id, username))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"chat_id": chat_id})

@app.route("/chats", methods=["GET"])
def get_chats():
    if "username" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    username = session["username"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM chats WHERE username=%s", (username,))
    chats = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({
        "chats": [{"chat_id": c["chat_id"], "title": "New Chat"} for c in chats]
    })

@app.route("/history/<chat_id>", methods=["GET"])
def get_history(chat_id):
    if "username" in session:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE chat_id=%s ORDER BY id", (chat_id,))
        history = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"history": history})
    # Anonymous user: use session
    if "anon_chat_id" in session and session["anon_chat_id"] == chat_id:
        return jsonify({"history": session.get("anon_history", [])})
    return jsonify({"history": []})

@app.route("/chat/<chat_id>", methods=["POST"])
def chat(chat_id):
    username = session.get("username")
    is_authenticated = username is not None

    # Anonymous user logic
    if not is_authenticated:
        if "anon_chat_id" not in session:
            session["anon_chat_id"] = str(uuid.uuid4())
            session["anon_history"] = []
        anon_chat_id = session["anon_chat_id"]
        if chat_id != anon_chat_id:
            return jsonify({"error": "Anonymous users can only use their own chat"}), 403
        anon_history = session.get("anon_history", [])
        if len([msg for msg in anon_history if msg["role"] == "user"]) >= 5:
            return jsonify({"error": "Message limit reached. Please sign up to continue."}), 403
        prompt = request.json.get("prompt", "")
        anon_history.append({"role": "user", "content": prompt})

        api_key = os.environ.get("GROQ_API_KEY")
        messages = [{"role": "system", "content": "You are AmberMind, a warm and insightful AI assistant. Always use Markdown formatting in your responses."}]
        for msg in anon_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-70b-8192",
                "messages": messages,
                "max_tokens": 500
            }
        )
        if response.status_code != 200:
            return jsonify({"error": "Groq API error", "details": response.text}), 500

        data = response.json()
        ai_response = data["choices"][0]["message"]["content"]
        anon_history.append({"role": "assistant", "content": ai_response})
        session["anon_history"] = anon_history
        return jsonify({
            "response": ai_response,
            "history": anon_history
        })

    # Authenticated user logic
    prompt = request.json.get("prompt", "")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (chat_id, role, content) VALUES (%s, %s, %s)", (chat_id, "user", prompt))
    # Get all history for this chat
    cur.execute("SELECT role, content FROM messages WHERE chat_id=%s ORDER BY id", (chat_id,))
    history = cur.fetchall()
    api_key = os.environ.get("GROQ_API_KEY")
    messages = [{"role": "system", "content": "You are AmberMind, a warm and insightful AI assistant. Always use Markdown formatting in your responses."}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama3-70b-8192",
            "messages": messages,
            "max_tokens": 500
        }
    )
    if response.status_code != 200:
        cur.close()
        conn.close()
        return jsonify({"error": "Groq API error", "details": response.text}), 500

    data = response.json()
    ai_response = data["choices"][0]["message"]["content"]
    cur.execute("INSERT INTO messages (chat_id, role, content) VALUES (%s, %s, %s)", (chat_id, "assistant", ai_response))
    conn.commit()
    cur.execute("SELECT role, content FROM messages WHERE chat_id=%s ORDER BY id", (chat_id,))
    history = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({
        "response": ai_response,
        "history": history
    })

@app.route("/admin", methods=["GET"])
def admin_panel():
    if session.get("is_admin"):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users")
        user_list = [row["username"] for row in cur.fetchall()]
        cur.execute("SELECT username, COUNT(*) as count FROM chats GROUP BY username")
        chat_stats = {row["username"]: row["count"] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return jsonify({"users": user_list, "chat_stats": chat_stats})
    else:
        return jsonify({"error": "Not authorized"}), 403

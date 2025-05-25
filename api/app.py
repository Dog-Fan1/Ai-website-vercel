import os
import uuid
import requests
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key")
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True
CORS(app, supports_credentials=True)

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_db()
    cur = conn.cursor()
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
    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
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
                "chats": [{"chat_id": c["chat_id"], "title": "New Chat

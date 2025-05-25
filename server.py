from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import shelve
import os
import requests
import uuid

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True
CORS(app, supports_credentials=True)

USER_DB = "users.db"
CHATS_DB = "chats.db"

def get_user(username):
    with shelve.open(USER_DB) as db:
        return db.get(username)

def save_user(username, password_hash):
    with shelve.open(USER_DB, writeback=True) as db:
        db[username] = password_hash

def get_user_chats(username):
    with shelve.open(CHATS_DB) as db:
        return db.get(username, {})

def save_user_chats(username, chats):
    with shelve.open(CHATS_DB, writeback=True) as db:
        db[username] = chats

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
    if get_user(username):
        return jsonify({"error": "User already exists"}), 400
    password_hash = generate_password_hash(password)
    save_user(username, password_hash)
    chats = {}
    chat_id = str(uuid.uuid4())
    chats[chat_id] = []
    save_user_chats(username, chats)
    return jsonify({"message": "User created successfully", "chat_id": chat_id})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # Admin check
    if username == "Admin" and password == "SiETHOwROltu":
        session["username"] = username
        session["is_admin"] = True
        chats = get_user_chats(username)
        return jsonify({
            "message": "Login successful",
            "chats": [{"chat_id": cid, "title": chats[cid][0]['content'][:30] if chats[cid] else "New Chat"} for cid in chats],
            "is_admin": True
        })

    password_hash = get_user(username)
    if not password_hash or not check_password_hash(password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401
    session["username"] = username
    session["is_admin"] = False
    chats = get_user_chats(username)
    return jsonify({
        "message": "Login successful",
        "chats": [{"chat_id": cid, "title": chats[cid][0]['content'][:30] if chats[cid] else "New Chat"} for cid in chats],
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
    chats = get_user_chats(username)
    chat_id = str(uuid.uuid4())
    chats[chat_id] = []
    save_user_chats(username, chats)
    return jsonify({"chat_id": chat_id})

@app.route("/chats", methods=["GET"])
def get_chats():
    if "username" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    username = session["username"]
    chats = get_user_chats(username)
    return jsonify({
        "chats": [{"chat_id": cid, "title": chats[cid][0]['content'][:30] if chats[cid] else "New Chat"} for cid in chats]
    })

@app.route("/history/<chat_id>", methods=["GET"])
def get_history(chat_id):
    if "username" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    username = session["username"]
    chats = get_user_chats(username)
    return jsonify({"history": chats.get(chat_id, [])})

@app.route("/chat/<chat_id>", methods=["POST"])
def chat(chat_id):
    if "username" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    username = session["username"]
    prompt = request.json.get("prompt", "")
    chats = get_user_chats(username)
    if chat_id not in chats:
        return jsonify({"error": "Chat not found"}), 404
    chats[chat_id].append({"role": "user", "content": prompt})

    # Groq Llama-3 API integration (Markdown output)
    api_key = os.environ.get("GROQ_API_KEY")
    messages = [{"role": "system", "content": "You are AmberMind, a warm and insightful AI assistant. Always use Markdown formatting in your responses."}]
    for msg in chats[chat_id]:
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

    chats[chat_id].append({"role": "assistant", "content": ai_response})
    save_user_chats(username, chats)
    return jsonify({
        "response": ai_response,
        "history": chats[chat_id]
    })

@app.route("/admin", methods=["GET"])
def admin_panel():
    if session.get("is_admin"):
        with shelve.open(USER_DB) as users, shelve.open(CHATS_DB) as chats:
            user_list = list(users.keys())
            chat_stats = {u: len(chats.get(u, {})) for u in user_list}
        return jsonify({"users": user_list, "chat_stats": chat_stats})
    else:
        return jsonify({"error": "Not authorized"}), 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

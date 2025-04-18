from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend-backend communication

# Gemini API Key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Error: GEMINI_API_KEY is missing! Set it in .env or system environment.")

# Configure Generative AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-1.5-flash-8b")

# MySQL Database Configuration
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Connect to the MySQL database
conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)

# Ensure database tables exist
def setup_database():
    with conn.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            chat_id INT NOT NULL,
            sender VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
        )
        """)
        conn.commit()

setup_database()

# Create a new chat
@app.route("/chat/new", methods=["POST"])
def new_chat():
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO chats (title) VALUES ('New Chat')")
        conn.commit()
        chat_id = cursor.lastrowid
        # Add initial bot message
        cursor.execute("INSERT INTO messages (chat_id, sender, content) VALUES (%s, %s, %s)",
                       (chat_id, "bot", "How can I help you?"))
        conn.commit()
    return jsonify({"id": chat_id, "title": "New Chat", "messages": [{"sender": "bot", "content": "How can I help you?"}]})

# Get all chats
@app.route("/chats", methods=["GET"])
def get_chats():
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, title, created_at FROM chats")
        chats = [{"id": row[0], "title": row[1], "createdAt": row[2].strftime("%Y-%m-%d %H:%M:%S")} for row in cursor.fetchall()]
    return jsonify(chats)

# Send a message in a chat
@app.route("/chat", methods=["POST"])
def send_message():
    data = request.get_json()
    chat_id = data.get("chat_id")
    sender = data.get("sender")
    content = data.get("message")
    
    if not chat_id or not sender or not content:
        return jsonify({"error": "Missing fields"}), 400

    # Insert user message into the database
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO messages (chat_id, sender, content) VALUES (%s, %s, %s)", (chat_id, sender, content))
        conn.commit()

        # Generate bot response
        bot_response = model.generate_content(content)
        bot_message = bot_response.text

        # Insert bot message into the database
        cursor.execute("INSERT INTO messages (chat_id, sender, content) VALUES (%s, %s, %s)", (chat_id, "bot", bot_message))
        conn.commit()

        # Fetch updated messages
        cursor.execute("SELECT id, sender, content, created_at FROM messages WHERE chat_id = %s", (chat_id,))
        messages = [
            {
                "id": row[0],
                "sender": row[1],
                "content": row[2],
                "created_at": row[3].strftime("%Y-%m-%d %H:%M:%S")
            }
            for row in cursor.fetchall()
        ]

    return jsonify({"chat_id": chat_id, "messages": messages})

# Delete a chat
@app.route("/chat/delete/<int:chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    with conn.cursor() as cursor:
        # Delete chat and associated messages
        cursor.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
        conn.commit()
    return jsonify({"success": True, "chat_id": chat_id})

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)

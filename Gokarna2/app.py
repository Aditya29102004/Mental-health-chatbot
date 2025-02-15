from flask import Flask, request, jsonify, render_template, redirect, url_for
import google.generativeai as genai
import os
from models import db, ChatSession, Message
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatlogs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

# Initialize the database
db.init_app(app)

# Load Google API key from environment variable for security
GOOGLE_API_KEY = "AIzaSyDCpBuZZUgMY1CKOcoeBmKR6OFq4291PfI"
if not GOOGLE_API_KEY:
    raise ValueError("No GOOGLE_API_KEY set for Gemini API")
genai.configure(api_key=GOOGLE_API_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        data = request.get_json() or {}
        user_input = data.get('message', '').strip()
        if not user_input:
            return jsonify({'error': 'No message provided'}), 400

        # Get or create a session
        session_id = data.get('session_id')
        if session_id:
            session = ChatSession.query.get(session_id)
            if not session:
                return jsonify({'error': 'Session not found'}), 404
        else:
            session = ChatSession()
            db.session.add(session)
            db.session.commit()

        # Store user's message
        user_message = Message(
            session_id=session.id,
            sender='user',
            content=user_input
        )
        db.session.add(user_message)
        db.session.commit()

        # Build conversation for the AI
        messages = Message.query.filter_by(session_id=session.id).order_by(Message.timestamp.asc()).all()
        conversation_history = []
        for msg in messages:
            role = "user" if msg.sender == "user" else "model"  # Use "model" for bot messages
            conversation_history.append({
                "role": role,  # Correct role for Gemini API
                "parts": [{"text": msg.content}]
            })

        # Initialize the model and start a chat
        model = genai.GenerativeModel('gemini-pro')  # Use 'gemini-pro' for the latest model
        chat = model.start_chat(history=conversation_history)

        # Send the new user message
        response = chat.send_message(user_input)
        bot_reply = response.text

        # Store bot response
        bot_message = Message(
            session_id=session.id,
            sender='bot',
            content=bot_reply
        )
        db.session.add(bot_message)
        db.session.commit()

        return jsonify({
            'response': bot_reply,
            'session_id': session.id
        })
    return render_template('chat.html')

@app.route('/history')
def history():
    # Fetch all sessions
    sessions = ChatSession.query.all()
    history = []
    for session in sessions:
        messages = Message.query.filter_by(session_id=session.id).order_by(Message.timestamp.asc()).all()
        session_history = {
            'session_id': session.id,
            'started_at': session.started_at.isoformat(),
            'messages': [m.to_dict() for m in messages]
        }
        history.append(session_history)
    return render_template('history.html', history=history)

if __name__ == '__main__':
    # Create tables once at startup
    with app.app_context():
        db.create_all()
    app.run(debug=True)
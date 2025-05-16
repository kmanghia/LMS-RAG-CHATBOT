from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime, timedelta
from lms_rag import send_continue_chat
from model import ChatHistory
from db_connector import mongodb
from dotenv import load_dotenv
import os
from bson import ObjectId
import json

app = Flask(__name__)
CORS(app)  # Enable CORS
socketio = SocketIO(app, cors_allowed_origins='*', ping_timeout=60)

# Load environment variables from .env file
load_dotenv()

# Hàm chuyển đổi ObjectId và datetime thành string
def convert_mongo_objects(data):
    if isinstance(data, list):
        return [convert_mongo_objects(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_mongo_objects(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data

# Hàm tạo response với chuyển đổi các đối tượng MongoDB
def create_response(data, status_code, message):
    return jsonify({
        'data': convert_mongo_objects(data),
        'statusCode': status_code,
        'message': message
    }), status_code

# Function to get chat history collection
def get_chat_history_collection():
    return mongodb.get_collection('chat_history')

def get_last_session_number(user_id):
    chat_collection = get_chat_history_collection()
    last_session = chat_collection.find({'user_id': user_id}).sort('session_number', -1).limit(1)
    last_session = list(last_session)
    if not last_session:
        return 0
    return last_session[0]['session_number']

def get_new_session_number(user_id):
    chat_collection = get_chat_history_collection()
    last_session_number = get_last_session_number(user_id)
    last_session_records = list(chat_collection.find({'user_id': user_id, 'session_number': last_session_number}))

    if not last_session_records:
        return last_session_number + 1

    last_record_time = last_session_records[-1]['created_at']
    current_time = datetime.utcnow()
    time_diff = current_time - last_record_time

    # Start a new session if there's been no activity for 30 minutes or after 15 exchanges
    if time_diff > timedelta(minutes=30) or len(last_session_records) > 15:
        return last_session_number + 1

    return last_session_number

def get_chat_history_by_session(user_id, session_number):
    chat_collection = get_chat_history_collection()
    chats = list(chat_collection.find({'user_id': user_id, 'session_number': session_number}).sort('created_at', 1))
    return [ChatHistory.from_dict(chat) for chat in chats]

@app.route('/chat', methods=['POST'])
def send_message():
    try:
        data = request.json
        user_query = data.get('content')
        user_id = data.get('userId')

        if user_query and user_id:
            chat_collection = get_chat_history_collection()
            
            # Get old session number
            last_session_number = get_last_session_number(user_id)
            # Get the new session number
            session_number = get_new_session_number(user_id)

            if session_number > last_session_number:
                # Start a new conversation
                answer = send_continue_chat([], user_query)
            else:
                # Continue existing conversation
                chat_history = get_chat_history_by_session(user_id, session_number)
                if chat_history:
                    answer = send_continue_chat(chat_history, user_query)
                else:
                    answer = send_continue_chat([], user_query)

            # Save the user query to the chat history
            user_chat = ChatHistory(
                user_id=user_id,
                content=user_query,
                is_user=True,
                session_number=session_number
            )
            chat_collection.insert_one(user_chat.to_dict())

            # Save the generated answer to the chat history
            bot_chat = ChatHistory(
                user_id=user_id,
                content=answer,
                is_user=False,
                session_number=session_number
            )
            chat_collection.insert_one(bot_chat.to_dict())

            return create_response(bot_chat.to_dict(), 200, 'Success')
        return create_response(None, 400, 'No query or userId provided')
    except Exception as e:
        print(f"Lỗi khi xử lý tin nhắn: {e}")
        return create_response(None, 500, f'Internal Server Error: {str(e)}')

@app.route('/chat/history/<user_id>', methods=['GET'])
def get_chat_history_by_user(user_id):
    try:
        print(f"Looking for chat history with user_id: {user_id}")
        
        # Không chuyển đổi user_id thành ObjectId nữa vì dữ liệu thực tế lưu dưới dạng string
        chat_collection = get_chat_history_collection()
        chat_history_records = list(chat_collection.find({'user_id': user_id}).sort('created_at', 1))
        
        print(f"Found {len(chat_history_records)} records for user {user_id}")
        
        # Group by session for easier frontend usage
        sessions = {}
        for record in chat_history_records:
            session_num = record['session_number']
            if session_num not in sessions:
                sessions[session_num] = []
            sessions[session_num].append(record)
        
        print(f"Grouped into {len(sessions.keys())} sessions")
            
        return create_response(sessions, 200, 'Success')
    except Exception as e:
        print(f"Lỗi khi lấy lịch sử chat: {e}")
        return create_response(None, 500, f'Internal Server Error: {str(e)}')

@app.route('/chat/clear/<user_id>', methods=['DELETE'])
def clear_chat_history(user_id):
    try:
        # Chuyển đổi user_id thành ObjectId nếu cần
        try:
            if not isinstance(user_id, ObjectId) and not user_id.isdigit():
                user_id = ObjectId(user_id)
        except:
            # Nếu không chuyển đổi được, giữ nguyên giá trị
            pass
            
        chat_collection = get_chat_history_collection()
        result = chat_collection.delete_many({'user_id': user_id})
        return create_response(None, 200, f'Chat history cleared for user {user_id}. Deleted {result.deleted_count} messages.')
    except Exception as e:
        print(f"Lỗi khi xóa lịch sử chat: {e}")
        return create_response(None, 500, f'Internal Server Error: {str(e)}')

# Socket.IO event handlers for realtime chat
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('message')
def handle_message(data):
    try:
        user_query = data.get('content')
        user_id = data.get('userId')
        
        if user_query and user_id:
            chat_collection = get_chat_history_collection()
            
            # Get session number
            session_number = get_new_session_number(user_id)
            
            # Save user message
            user_chat = ChatHistory(
                user_id=user_id,
                content=user_query,
                is_user=True,
                session_number=session_number
            )
            chat_collection.insert_one(user_chat.to_dict())
            
            # Get chat history for context
            chat_history = get_chat_history_by_session(user_id, session_number)
            
            # Generate response
            answer = send_continue_chat(chat_history, user_query)
            
            # Save bot response
            bot_chat = ChatHistory(
                user_id=user_id,
                content=answer,
                is_user=False,
                session_number=session_number
            )
            chat_collection.insert_one(bot_chat.to_dict())
            
            # Emit response back to client
            emit('response', convert_mongo_objects(bot_chat.to_dict()))
        else:
            emit('error', {'message': 'No query or userId provided'})
    except Exception as e:
        print(f"Socket error: {e}")
        emit('error', {'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8080) 
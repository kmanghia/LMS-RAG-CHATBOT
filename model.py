from datetime import datetime
from bson import ObjectId

class ChatHistory:
    """
    Model lưu trữ lịch sử chat của người dùng trong MongoDB
    """
    def __init__(self, user_id, content, is_user, session_number, created_at=None, _id=None):
        self.id = _id or ObjectId()
        # Chuyển đổi user_id thành ObjectId nếu nó là string
        self.user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        self.content = content
        self.is_user = is_user  # True nếu là tin nhắn từ người dùng, False nếu là từ bot
        self.created_at = created_at or datetime.utcnow()
        self.session_number = session_number  # Dùng để nhóm các cuộc hội thoại

    @staticmethod
    def from_dict(data):
        return ChatHistory(
            _id=data.get('_id'),
            user_id=data.get('user_id'),
            content=data.get('content'),
            is_user=data.get('is_user'),
            created_at=data.get('created_at'),
            session_number=data.get('session_number')
        )

    def to_dict(self):
        return {
            '_id': str(self.id) if isinstance(self.id, ObjectId) else self.id,
            'user_id': str(self.user_id) if isinstance(self.user_id, ObjectId) else self.user_id,
            'content': self.content,
            'is_user': self.is_user,
            'created_at': self.created_at,
            'session_number': self.session_number
        } 
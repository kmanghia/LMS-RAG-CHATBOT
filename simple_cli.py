#!/usr/bin/env python3
"""
Command Line Interface đơn giản cho LMS-RAG-Chatbot
"""

import sys
import os
import argparse
from lms_rag import send_continue_chat, cache

class ChatHistory:
    def __init__(self, content, is_user):
        self.content = content
        self.is_user = is_user

def clear_screen():
    """Xóa màn hình terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """In header của chatbot"""
    print("""
╔════════════════════════════════════════════════════════╗
║                    LMS-RAG-Chatbot                     ║
║                                                        ║
║  Hỏi chatbot về các khóa học, giảng viên, so sánh...   ║
║  Gõ 'exit' hoặc 'quit' để thoát                        ║
║  Gõ 'clear' để xóa lịch sử hội thoại                   ║
║  Gõ 'help' để xem trợ giúp                             ║
╚════════════════════════════════════════════════════════╝
""")

def print_help():
    """In thông tin trợ giúp"""
    print("""
Các lệnh hỗ trợ:
- exit, quit: Thoát chương trình
- clear: Xóa lịch sử hội thoại
- help: Hiển thị trợ giúp
- cache status: Kiểm tra tình trạng cache
- cache clear: Xóa toàn bộ cache

Ví dụ câu hỏi:
- Có những khóa học nào về Python?
- Liệt kê tất cả các khóa học về lập trình web
- Thông tin chi tiết về giảng viên Nguyễn Văn A
- So sánh khóa học [Python cơ bản] và [Java nâng cao]
- Khóa học nào phù hợp cho người mới bắt đầu lập trình?
""")

def handle_special_commands(command, chat_history):
    """
    Xử lý các lệnh đặc biệt
    
    Returns:
        bool: True nếu cần thoát, False nếu không
    """
    command = command.lower().strip()
    
    if command in ['exit', 'quit']:
        print("Cảm ơn bạn đã sử dụng LMS-RAG-Chatbot. Tạm biệt!")
        return True
        
    if command == 'clear':
        clear_screen()
        print_header()
        return False
        
    if command == 'help':
        print_help()
        return False
        
    if command == 'cache status':
        try:
            status = cache.check_cache_health()
            print(f"Tình trạng cache: {status}")
        except Exception as e:
            print(f"Lỗi khi kiểm tra cache: {e}")
        return False
        
    if command == 'cache clear':
        try:
            cache.clear_all()
            print("Đã xóa toàn bộ cache!")
        except Exception as e:
            print(f"Lỗi khi xóa cache: {e}")
        return False
        
    return None  # Not a special command

def main():
    """Main function cho CLI"""
    parser = argparse.ArgumentParser(description='LMS-RAG-Chatbot CLI')
    parser.add_argument('--no-clear', action='store_true', help='Không xóa màn hình khi khởi động')
    args = parser.parse_args()
    
    if not args.no_clear:
        clear_screen()
    
    print_header()
    
    chat_history = []
    
    try:
        while True:
            # Nhận input từ người dùng
            user_input = input("\n\033[94mBạn:\033[0m ")
            
            # Kiểm tra nếu là lệnh đặc biệt
            special_result = handle_special_commands(user_input, chat_history)
            if special_result is not None:
                if special_result:  # Lệnh thoát
                    break
                continue  # Lệnh khác, tiếp tục vòng lặp
            
            # Thêm tin nhắn người dùng vào lịch sử
            chat_history.append(ChatHistory(user_input, True))
            
            # Xử lý câu hỏi với error handling
            try:
                print("\n\033[92mEduBot:\033[0m ", end="", flush=True)
                response = send_continue_chat(chat_history, user_input)
                print(response)
                
                # Thêm câu trả lời vào lịch sử
                chat_history.append(ChatHistory(response, False))
            except KeyboardInterrupt:
                print("\nĐã hủy xử lý câu hỏi.")
            except Exception as e:
                error_msg = f"Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn: {str(e)}"
                print(error_msg)
                chat_history.append(ChatHistory(error_msg, False))
    
    except KeyboardInterrupt:
        print("\nCảm ơn bạn đã sử dụng LMS-RAG-Chatbot. Tạm biệt!")
    
if __name__ == "__main__":
    main() 
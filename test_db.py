"""
Script kiểm tra kết nối MongoDB và dữ liệu cho LMS-RAG-Chatbot
"""
from db_connector import mongodb, check_database_connection
from dotenv import load_dotenv
import os
import json
from bson import ObjectId

# Custom JSON encoder để xử lý ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

def print_json(data):
    """In dữ liệu JSON đẹp hơn"""
    print(json.dumps(data, indent=2, ensure_ascii=False, cls=MongoJSONEncoder))

def main():
    # Load biến môi trường từ file .env
    load_dotenv()
    
    print("\n===== KIỂM TRA KẾT NỐI MONGODB =====")
    
    # Hiển thị thông tin biến môi trường
    mongo_uri = os.getenv('MONGODB_URI', 'Không tìm thấy')
    print(f"MongoDB URI: {mongo_uri.replace(':@', ':[PASSWORD]@') if ':@' in mongo_uri else mongo_uri}")
    print(f"MongoDB DB Name: {os.getenv('MONGODB_DB_NAME', 'Không tìm thấy')}")
    
    # Kiểm tra kết nối và dữ liệu
    db_status = check_database_connection()
    print(f"\nTrạng thái kết nối: {db_status['connection_status']}")
    
    if db_status["error"]:
        print(f"LỖI: {db_status['error']}")
        
        # Đề xuất giải pháp
        if "Không tìm thấy dữ liệu" in db_status["error"]:
            print("\nĐỀ XUẤT GIẢI PHÁP:")
            print("1. Kiểm tra MongoDB đã được cài đặt và đang chạy")
            print("2. Kiểm tra kết nối MongoDB URI trong file .env")
            print("3. Đảm bảo dữ liệu đã được import vào database")
        elif "MongoDB URI không được cấu hình" in db_status["error"]:
            print("\nĐỀ XUẤT GIẢI PHÁP:")
            print("1. Tạo file .env từ file .env-example")
            print("2. Cấu hình MONGODB_URI và MONGODB_DB_NAME trong file .env")
    else:
        print("\nThông tin collections:")
        for coll, count in db_status["collections"].items():
            print(f"- {coll}: {count} records")
        
        # Thử truy vấn dữ liệu
        print("\n===== THỬ TRUY VẤN DỮ LIỆU =====")
        
        # Thử lấy khóa học
        try:
            # Không sử dụng limit để lấy tất cả khóa học
            courses = mongodb.get_courses(limit=None)
            print(f"\nĐã tìm thấy {len(courses)} khóa học")
            if courses:
                print("Tên các khóa học:")
                for i, course in enumerate(courses[:5], 1):  # Chỉ hiển thị 5 khóa học đầu tiên
                    print(f"{i}. {course.get('name', 'Không có tên')} (ID: {course.get('_id')})")
                if len(courses) > 5:
                    print(f"... và {len(courses)-5} khóa học khác")
        except Exception as e:
            print(f"Lỗi khi truy vấn khóa học: {e}")
        
        # Thử lấy giảng viên
        try:
            # Không sử dụng limit để lấy tất cả giảng viên
            mentors = mongodb.get_mentors(limit=None)
            print(f"\nĐã tìm thấy {len(mentors)} giảng viên")
            if mentors:
                print("Tên các giảng viên:")
                for i, mentor in enumerate(mentors[:5], 1):  # Chỉ hiển thị 5 giảng viên đầu tiên
                    user_info = mentor.get('userInfo', {})
                    print(f"{i}. {user_info.get('name', 'Không có tên')} (ID: {mentor.get('_id')})")
                if len(mentors) > 5:
                    print(f"... và {len(mentors)-5} giảng viên khác")
        except Exception as e:
            print(f"Lỗi khi truy vấn giảng viên: {e}")
        
        print("\nKiểm tra hoàn tất!")

if __name__ == "__main__":
    main() 
"""
Script kiểm tra kết nối MongoDB trực tiếp (không qua vector store)
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import json
from bson import ObjectId

# Custom JSON encoder để in dữ liệu MongoDB
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def print_json(data):
    """In dữ liệu JSON đẹp hơn"""
    print(json.dumps(data, indent=2, ensure_ascii=False, cls=MongoJSONEncoder))

def check_mongodb_connection():
    """Kiểm tra kết nối đến MongoDB"""
    # Load biến môi trường
    load_dotenv()
    
    # Lấy thông tin kết nối từ biến môi trường
    mongodb_uri = os.getenv('MONGODB_URI')
    db_name = os.getenv('MONGODB_DB_NAME', 'trannghia')
    
    if not mongodb_uri:
        print("Lỗi: MONGODB_URI không tìm thấy trong file .env")
        print("Vui lòng tạo file .env từ .env-example và cấu hình MONGODB_URI")
        return
    
    print(f"Kết nối đến: {mongodb_uri.replace(':@', ':[PASSWORD]@') if ':@' in mongodb_uri else mongodb_uri}")
    print(f"Database: {db_name}")
    
    try:
        # Kết nối đến MongoDB
        client = MongoClient(mongodb_uri)
        
        # Kiểm tra kết nối
        client.admin.command('ping')
        print("\n✅ Kết nối MongoDB thành công!")
        
        # Lấy database
        db = client[db_name]
        
        # Kiểm tra các collections
        collections = db.list_collection_names()
        print(f"\nDanh sách collections: {collections}")
        
        # Kiểm tra dữ liệu trong từng collection
        required_collections = ['courses', 'mentors', 'users']
        
        for collection_name in required_collections:
            if collection_name in collections:
                collection = db[collection_name]
                count = collection.count_documents({})
                print(f"\n📋 Collection '{collection_name}': {count} documents")
                
                if count > 0:
                    print(f"Mẫu dữ liệu từ '{collection_name}':")
                    samples = list(collection.find().limit(1))
                    print_json(samples[0])
                else:
                    print(f"⚠️ Collection '{collection_name}' không có dữ liệu!")
            else:
                print(f"❌ Collection '{collection_name}' không tồn tại!")
        
        # Kết luận
        if all(coll in collections for coll in required_collections):
            print("\n✅ Tất cả collections cần thiết đều tồn tại.")
            
            # Kiểm tra xem có dữ liệu trong các collections không
            has_data = all(db[coll].count_documents({}) > 0 for coll in required_collections)
            if has_data:
                print("✅ Tất cả collections có dữ liệu.")
            else:
                print("⚠️ Một số collections không có dữ liệu!")
                print("👉 Chatbot có thể không hoạt động đúng!")
        else:
            print("\n❌ Thiếu một số collections cần thiết!")
            print("👉 Vui lòng đảm bảo tất cả collections đều tồn tại và có dữ liệu.")
        
    except Exception as e:
        print(f"\n❌ Lỗi kết nối MongoDB: {e}")
        print("👉 Kiểm tra lại kết nối MongoDB và đảm bảo service đang chạy.")

if __name__ == "__main__":
    check_mongodb_connection() 
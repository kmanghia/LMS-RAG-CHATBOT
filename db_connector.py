from pymongo import MongoClient
from dotenv import load_dotenv
import os
import re
from bson import ObjectId

# Load environment variables
load_dotenv()

class MongoDBConnector:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBConnector, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.db = None
        return cls._instance
    
    def connect(self):
        """
        Kết nối đến MongoDB
        """
        if self.client is None:
            mongodb_uri = os.getenv('MONGODB_URI')
            if not mongodb_uri:
                raise ValueError("MongoDB URI không được cấu hình trong file .env")
            
            try:
                # Kết nối MongoDB không có SSL
                self.client = MongoClient(mongodb_uri)
                self.db = self.client[os.getenv('MONGODB_DB_NAME', 'trannghia')]
                print("Kết nối MongoDB thành công")
            except Exception as e:
                print(f"Lỗi kết nối MongoDB: {e}")
                raise
        
        return self.db
    
    def get_collection(self, collection_name):
        """
        Lấy collection từ database
        """
        db = self.connect()
        return db[collection_name]
    
    def get_courses(self, query=None, limit=None):
        """
        Lấy danh sách khóa học từ MongoDB
        """
        courses_collection = self.get_collection('courses')
        
        if query is None:
            query = {}
            
        # Chỉ lấy các khóa học có trạng thái active
        query['status'] = 'active'
        
        # Pipeline aggregation để lấy thông tin giảng viên
        pipeline = [
            {"$match": query},
            {"$lookup": {
                "from": "mentors",
                "localField": "mentor",
                "foreignField": "_id",
                "as": "mentorInfo"
            }},
            {"$unwind": {"path": "$mentorInfo", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {
                "from": "users",
                "localField": "mentorInfo.user",
                "foreignField": "_id",
                "as": "mentorUser"
            }},
            {"$unwind": {"path": "$mentorUser", "preserveNullAndEmptyArrays": True}}
        ]
        
        # Chỉ thêm limit vào pipeline nếu có giá trị
        if limit is not None:
            pipeline.append({"$limit": limit})
        
        courses = list(courses_collection.aggregate(pipeline))
        print(f"Đã tìm thấy {len(courses)} khóa học với trạng thái active")
        return courses
    
    def get_mentors(self, query=None, limit=None):
        """
        Lấy danh sách tất cả giảng viên từ MongoDB
        """
        mentors_collection = self.get_collection('mentors')
        
        if query is None:
            query = {}
        
        # Pipeline aggregation để lấy thông tin user
        pipeline = [
            {"$match": query},
            {"$lookup": {
                "from": "users",
                "localField": "user",
                "foreignField": "_id",
                "as": "userInfo"
            }},
            {"$unwind": {"path": "$userInfo", "preserveNullAndEmptyArrays": True}}
        ]
        
        # Chỉ thêm limit vào pipeline nếu có giá trị
        if limit is not None:
            pipeline.append({"$limit": limit})
        
        mentors = list(mentors_collection.aggregate(pipeline))
        print(f"Đã tìm thấy {len(mentors)} giảng viên")
        return mentors
    
    def get_courses_by_mentor(self, mentor_id, limit=20):
        """
        Lấy danh sách khóa học của một giảng viên cụ thể
        """
        courses_collection = self.get_collection('courses')
        
        # Chuyển đổi mentor_id thành ObjectId nếu nó là string
        if isinstance(mentor_id, str):
            try:
                mentor_id = ObjectId(mentor_id)
            except:
                # Nếu không chuyển đổi được, giữ nguyên giá trị
                pass
            
        query = {"mentor": mentor_id, "status": "active"}
        
        # Xử lý trường hợp limit=None
        if limit is None:
            courses = list(courses_collection.find(query))
        else:
            courses = list(courses_collection.find(query).limit(limit))
            
        print(f"Đã tìm thấy {len(courses)} khóa học của giảng viên {mentor_id}")
        return courses
    
    def get_courses_by_category(self, category, limit=None):
        """
        Lấy danh sách khóa học theo danh mục
        """
        courses_collection = self.get_collection('courses')
        
        # Xử lý cả trường hợp categories là chuỗi hoặc mảng
        query = {
            "$or": [
                # Trường hợp categories là chuỗi
                {"categories": {"$regex": category, "$options": "i"}},
                # Trường hợp categories là mảng và chứa phần tử khớp với category
                {"categories": {"$elemMatch": {"$regex": category, "$options": "i"}}}
            ],
            "status": "active"
        }
        
        # Pipeline aggregation để lấy thông tin giảng viên
        pipeline = [
            {"$match": query},
            {"$lookup": {
                "from": "mentors",
                "localField": "mentor",
                "foreignField": "_id",
                "as": "mentorInfo"
            }},
            {"$unwind": {"path": "$mentorInfo", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {
                "from": "users",
                "localField": "mentorInfo.user",
                "foreignField": "_id",
                "as": "mentorUser"
            }},
            {"$unwind": {"path": "$mentorUser", "preserveNullAndEmptyArrays": True}}
        ]
        
        # Chỉ thêm limit vào pipeline nếu có giá trị
        if limit is not None:
            pipeline.append({"$limit": limit})
        
        courses = list(courses_collection.aggregate(pipeline))
        print(f"Đã tìm thấy {len(courses)} khóa học thuộc danh mục '{category}'")
        for i, course in enumerate(courses):
            print(f"{i+1}. Khóa học: {course.get('name', 'Không có tên')} (ID: {course.get('_id')})")
        return courses
    
    def get_courses_by_level(self, level, limit=None):
        """
        Lấy danh sách khóa học theo cấp độ (beginner, intermediate, advanced)
        """
        courses_collection = self.get_collection('courses')
        query = {"level": level, "status": "active"}
        
        # Pipeline aggregation để lấy thông tin giảng viên
        pipeline = [
            {"$match": query},
            {"$lookup": {
                "from": "mentors",
                "localField": "mentor",
                "foreignField": "_id",
                "as": "mentorInfo"
            }},
            {"$unwind": {"path": "$mentorInfo", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {
                "from": "users",
                "localField": "mentorInfo.user",
                "foreignField": "_id",
                "as": "mentorUser"
            }},
            {"$unwind": {"path": "$mentorUser", "preserveNullAndEmptyArrays": True}}
        ]
        
        # Chỉ thêm limit vào pipeline nếu có giá trị
        if limit is not None:
            pipeline.append({"$limit": limit})
        
        courses = list(courses_collection.aggregate(pipeline))
        print(f"Đã tìm thấy {len(courses)} khóa học có cấp độ '{level}'")
        return courses
    
    def search_courses(self, keyword, limit=None):
        """
        Tìm kiếm khóa học theo từ khóa
        """
        courses_collection = self.get_collection('courses')
        
        # Tìm kiếm trong tên, mô tả, tags
        query = {
            "$or": [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
                {"tags": {"$regex": keyword, "$options": "i"}}
            ],
            "status": "active"
        }
        
        # Pipeline aggregation để lấy thông tin giảng viên
        pipeline = [
            {"$match": query},
            {"$lookup": {
                "from": "mentors",
                "localField": "mentor",
                "foreignField": "_id",
                "as": "mentorInfo"
            }},
            {"$unwind": {"path": "$mentorInfo", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {
                "from": "users",
                "localField": "mentorInfo.user",
                "foreignField": "_id",
                "as": "mentorUser"
            }},
            {"$unwind": {"path": "$mentorUser", "preserveNullAndEmptyArrays": True}}
        ]
        
        # Chỉ thêm limit vào pipeline nếu có giá trị
        if limit is not None:
            pipeline.append({"$limit": limit})
        
        courses = list(courses_collection.aggregate(pipeline))
        print(f"Đã tìm thấy {len(courses)} khóa học có từ khóa '{keyword}'")
        for i, course in enumerate(courses):
            print(f"{i+1}. Khóa học: {course.get('name', 'Không có tên')} (ID: {course.get('_id')})")
        return courses
    
    def search_mentors(self, keyword, limit=None):
        """
        Tìm kiếm giảng viên theo từ khóa
        """
        mentors_collection = self.get_collection('mentors')
        
        # Chuẩn bị từ khóa tìm kiếm
        keyword_pattern = keyword.replace(' ', '.*')
        
        # Pipeline aggregation để tìm kiếm giảng viên với nhiều tiêu chí hơn
        pipeline = [
            {"$lookup": {
                "from": "users",
                "localField": "user",
                "foreignField": "_id",
                "as": "userInfo"
            }},
            {"$unwind": {"path": "$userInfo", "preserveNullAndEmptyArrays": True}},
            {"$match": {
                "$or": [
                    {"userInfo.name": {"$regex": keyword, "$options": "i"}},
                    {"userInfo.name": {"$regex": keyword_pattern, "$options": "i"}},
                    {"bio": {"$regex": keyword, "$options": "i"}},
                    {"specialization": {"$elemMatch": {"$regex": keyword, "$options": "i"}}},
                    {"specialization": {"$regex": keyword, "$options": "i"}},
                    {"achievements": {"$elemMatch": {"$regex": keyword, "$options": "i"}}}
                ]
            }}
        ]
        
        # Chỉ thêm limit vào pipeline nếu có giá trị
        if limit is not None:
            pipeline.append({"$limit": limit})
        
        mentors = list(mentors_collection.aggregate(pipeline))
        print(f"Đã tìm thấy {len(mentors)} giảng viên có từ khóa '{keyword}'")
        
        # Log chi tiết giảng viên tìm thấy
        for i, mentor in enumerate(mentors):
            user_info = mentor.get('userInfo', {})
            print(f"{i+1}. Giảng viên: {user_info.get('name', 'Không có tên')} (ID: {mentor.get('_id')})")
        
        return mentors
    
    def close(self):
        """
        Đóng kết nối MongoDB
        """
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            print("Đã đóng kết nối MongoDB")

# Singleton instance
mongodb = MongoDBConnector() 

# Hàm kiểm tra kết nối và dữ liệu trong MongoDB
def check_database_connection():
    """
    Kiểm tra kết nối MongoDB và trạng thái dữ liệu
    
    Returns:
        dict: Thông tin về trạng thái kết nối và số lượng records trong các collections
    """
    result = {
        "connection_status": "Not connected",
        "database_info": {},
        "collections": {},
        "sample_data": {},
        "error": None
    }
    
    try:
        # Thử kết nối MongoDB
        db = mongodb.connect()
        result["connection_status"] = "Connected"
        result["database_info"] = {
            "database_name": db.name,
            "mongodb_uri": os.getenv('MONGODB_URI', '[NOT SET]').replace(":@", ":[PASSWORD]@")
        }
        
        # Kiểm tra số lượng records trong các collections
        collections_to_check = ["courses", "mentors", "users", "chat_history"]
        
        for collection_name in collections_to_check:
            try:
                collection = db[collection_name]
                count = collection.count_documents({})
                result["collections"][collection_name] = count
                
                # Lấy mẫu dữ liệu nếu có
                if count > 0:
                    sample = list(collection.find().limit(1))
                    if sample:
                        # Chuyển ObjectId thành string để có thể JSON serialize
                        sample_data = {}
                        for key, value in sample[0].items():
                            if isinstance(value, ObjectId):
                                sample_data[key] = str(value)
                            else:
                                sample_data[key] = value
                        result["sample_data"][collection_name] = sample_data
                
            except Exception as e:
                result["collections"][collection_name] = f"Error: {str(e)}"
        
        # Kiểm tra nếu không có dữ liệu
        if all(count == 0 for count in result["collections"].values() if isinstance(count, int)):
            result["error"] = "Không tìm thấy dữ liệu trong bất kỳ collection nào. Vui lòng kiểm tra kết nối MongoDB và đảm bảo dữ liệu đã được import."
    
    except Exception as e:
        result["error"] = f"Lỗi kết nối MongoDB: {str(e)}"
    
    return result

# Nếu chạy trực tiếp file này
if __name__ == "__main__":
    # Kiểm tra kết nối và dữ liệu
    db_status = check_database_connection()
    print("\n=== KIỂM TRA KẾT NỐI DATABASE ===")
    print(f"Trạng thái kết nối: {db_status['connection_status']}")
    
    if db_status["error"]:
        print(f"LỖI: {db_status['error']}")
    else:
        print("\nThông tin collections:")
        for coll, count in db_status["collections"].items():
            print(f"- {coll}: {count} records")
        
        if db_status["sample_data"]:
            print("\nDữ liệu mẫu:")
            for coll, sample in db_status["sample_data"].items():
                print(f"- {coll}: {sample}")
        
        print("\nKết nối thành công và có dữ liệu!") 
"""
Simple test script to check MongoDB connection and course search without LLM/RAG
"""
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import json
from bson import ObjectId

# Load environment variables
load_dotenv()

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super(JSONEncoder, self).default(obj)

def print_json(data):
    """Print JSON data in a readable format"""
    print(json.dumps(data, indent=2, ensure_ascii=False, cls=JSONEncoder))

def test_mongodb_connection():
    """Test direct MongoDB connection and search"""
    print("\n===== TESTING DIRECT MONGODB CONNECTION =====")
    
    try:
        # Get MongoDB connection details
        mongodb_uri = os.getenv('MONGODB_URI')
        db_name = os.getenv('MONGODB_DB_NAME', 'trannghia')
        
        if not mongodb_uri:
            print("ERROR: MongoDB URI not found in .env file")
            return
        
        print(f"Connecting to: {mongodb_uri.replace(':@', ':[PASSWORD]@') if ':@' in mongodb_uri else mongodb_uri}")
        print(f"Database: {db_name}")
        
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        
        # Check connection
        client.admin.command('ping')
        print("✅ MongoDB connection successful")
        
        # Get collections list
        collections = db.list_collection_names()
        print(f"Collections: {collections}")
        
        # Check courses collection
        courses_collection = db['courses']
        course_count = courses_collection.count_documents({})
        print(f"Total courses: {course_count}")
        
        if course_count > 0:
            print("\nSample courses:")
            for course in courses_collection.find().limit(3):
                print(f"- {course.get('name', 'No name')} (ID: {course.get('_id')})")
        
        # Test search function
        print("\n===== TESTING COURSE SEARCH =====")
        
        # Function to search courses
        def search_courses(keyword, limit=None):
            """Search for courses by keyword"""
            query = {
                "$or": [
                    {"name": {"$regex": keyword, "$options": "i"}},
                    {"description": {"$regex": keyword, "$options": "i"}},
                    {"tags": {"$regex": keyword, "$options": "i"}}
                ],
                "status": "active"
            }
            
            cursor = courses_collection.find(query)
            if limit is not None:
                cursor = cursor.limit(limit)
                
            return list(cursor)
        
        # Test various searches
        test_keywords = ["python", "web", "javascript", "beginner", "advanced"]
        
        for keyword in test_keywords:
            courses = search_courses(keyword)
            print(f"\nSearch for '{keyword}': Found {len(courses)} courses")
            
            if courses:
                for i, course in enumerate(courses[:3], 1):
                    print(f"{i}. {course.get('name', 'No name')} (ID: {course.get('_id')})")
                if len(courses) > 3:
                    print(f"... and {len(courses) - 3} more")
            else:
                print(f"No courses found for '{keyword}'")
        
        # Test getting all courses
        all_courses = courses_collection.find({"status": "active"})
        print(f"\nAll active courses: {courses_collection.count_documents({'status': 'active'})}")
        
        # Check mentors
        mentors_collection = db['mentors']
        mentor_count = mentors_collection.count_documents({})
        print(f"\nTotal mentors: {mentor_count}")
        
        if mentor_count > 0:
            print("Sample mentors:")
            for mentor in mentors_collection.find().limit(3):
                print(f"- Mentor ID: {mentor.get('_id')}")
                
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_mongodb_connection() 
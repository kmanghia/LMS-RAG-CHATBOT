"""
Script to check if there are Python courses in the MongoDB database
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import re
from bson import ObjectId
import json

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

def check_python_courses():
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
        
        # Check if connection is successful
        client.admin.command('ping')
        print("✅ MongoDB connection successful\n")
        
        # Get courses collection
        courses_collection = db['courses']
        
        # Find courses with Python in name, description, categories or tags
        python_query = {
            "$or": [
                {"name": {"$regex": "python", "$options": "i"}},
                {"description": {"$regex": "python", "$options": "i"}},
                {"categories": {"$regex": "python", "$options": "i"}},
                {"tags": {"$regex": "python", "$options": "i"}}
            ],
            "status": "active"
        }
        
        python_courses = list(courses_collection.find(python_query))
        print(f"Found {len(python_courses)} Python courses")
        
        if python_courses:
            print("\nPython courses:")
            for i, course in enumerate(python_courses, 1):
                print(f"{i}. {course.get('name', 'No name')} (ID: {course.get('_id')})")
                print(f"   Description: {course.get('description', 'No description')[:100]}...")
                
                # Check if categories is a list or string
                categories = course.get('categories', [])
                if isinstance(categories, list):
                    print(f"   Categories: {', '.join(categories)}")
                else:
                    print(f"   Categories: {categories}")
                
                # Check if tags is a list or string
                tags = course.get('tags', [])
                if isinstance(tags, list):
                    print(f"   Tags: {', '.join(tags)}")
                else:
                    print(f"   Tags: {tags}")
                print()
        else:
            print("\nNo Python courses found in the database!")
            
            # Get a list of all course names for reference
            all_courses = list(courses_collection.find({"status": "active"}))
            print(f"\nAvailable courses ({len(all_courses)}):")
            for i, course in enumerate(all_courses, 1):
                print(f"{i}. {course.get('name', 'No name')}")
        
    except Exception as e:
        print(f"ERROR connecting to MongoDB: {e}")

if __name__ == "__main__":
    check_python_courses() 
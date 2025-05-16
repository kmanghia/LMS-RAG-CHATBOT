"""
Script to test the RAG chatbot for specific queries
"""
from lms_rag import send_continue_chat, mongodb
import json
from bson import ObjectId

class CustomChatHistory:
    def __init__(self, content, is_user):
        self.content = content
        self.is_user = is_user

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super(JSONEncoder, self).default(obj)

def test_python_course_retrieval():
    """
    Test direct retrieval of Python courses from MongoDB
    """
    print("\n===== TESTING DIRECT MONGODB PYTHON COURSE RETRIEVAL =====")
    try:
        # Search for Python courses directly using MongoDB
        python_courses = mongodb.search_courses("python", limit=None)
        print(f"Direct MongoDB search found {len(python_courses)} Python courses")
        
        if python_courses:
            print("\nPython courses found:")
            for i, course in enumerate(python_courses, 1):
                print(f"{i}. {course.get('name', 'No name')} (ID: {course.get('_id')})")
                print(f"   Description: {course.get('description', 'No description')[:100]}...")
        else:
            print("No Python courses found in MongoDB!")
            
        # Now check if there are any courses containing "Python" in their description
        all_courses = mongodb.get_courses(limit=None)
        
        python_in_desc = []
        for course in all_courses:
            desc = course.get('description', '').lower()
            if 'python' in desc:
                python_in_desc.append(course)
        
        print(f"\nFound {len(python_in_desc)} courses with 'Python' in their description")
        if python_in_desc:
            for i, course in enumerate(python_in_desc, 1):
                print(f"{i}. {course.get('name', 'No name')} (ID: {course.get('_id')})")
                
    except Exception as e:
        print(f"Error testing MongoDB Python course retrieval: {e}")

def test_chat_query(query, chat_history=None):
    """
    Test a specific query using the chatbot
    """
    print(f"\n===== TESTING CHAT QUERY: '{query}' =====")
    
    if chat_history is None:
        chat_history = []
    
    response = send_continue_chat(chat_history, query)
    print(f"\nChatbot response:\n{response}\n")
    
    return response

def main():
    print("===== STARTING CHATBOT TESTS =====\n")
    
    # First test direct MongoDB Python course retrieval
    test_python_course_retrieval()
    
    # Test a Python course query
    python_query = "Liệt kê tất cả khóa học về Python"
    test_chat_query(python_query)
    
    # Test follow-up query
    history = [
        CustomChatHistory(python_query, True),
        CustomChatHistory("Here is the response for Python courses", False)
    ]
    test_chat_query("Khóa học Python nào phù hợp cho người mới bắt đầu?", history)
    
    # Test other queries
    test_chat_query("Liệt kê tất cả khóa học về Web")
    test_chat_query("Liệt kê tất cả các khóa học")
    
    print("\n===== CHATBOT TESTS COMPLETED =====")

if __name__ == "__main__":
    main() 
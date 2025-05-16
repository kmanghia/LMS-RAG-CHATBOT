from langchain_community.vectorstores import FAISS
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import create_history_aware_retriever
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os
import json
from bson import ObjectId
from db_connector import mongodb
import re
import difflib
from fuzzywuzzy import fuzz
from thefuzz import process
import unicodedata
from response_cache import cache

# Load environment variables
load_dotenv()

# Cấu hình Google Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY không được cấu hình trong file .env")

os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)

# Khởi tạo model Gemini với tham số phù hợp cho phiên bản 2.0
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.2,
    max_tokens=1500,  # Tăng token limit cho 2.0
    max_retries=3,    # Tăng số lần retry
    timeout=60       # Tăng timeout
    # Safety settings đã loại bỏ vì gây lỗi với LangChain
)

# Hàm tiền xử lý query tiếng Việt
def normalize_text(text):
    """
    Chuẩn hóa text tiếng Việt: loại bỏ dấu, chuyển thành chữ thường
    
    Args:
        text (str): Chuỗi cần chuẩn hóa
        
    Returns:
        str: Chuỗi đã chuẩn hóa
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text

def preprocess_vietnamese_query(query):
    """
    Tiền xử lý câu hỏi tiếng Việt để cải thiện hiệu quả
    
    Args:
        query (str): Chuỗi câu hỏi
        
    Returns:
        str: Chuỗi đã tiền xử lý
    """
    if not query:
        return ""
        
    # Chuẩn hóa dấu cách
    query = re.sub(r'\s+', ' ', query.strip())
    
    # Thay thế một số từ viết tắt phổ biến
    replacements = {
        "k/h": "khóa học",
        "kh": "khóa học",
        "gv": "giảng viên",
        "sv": "sinh viên",
        "đhqg": "đại học quốc gia",
        "đh": "đại học",
        "cntt": "công nghệ thông tin",
        "htn": "học trực tuyến",
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "ds": "data science",
        "ba": "business analytics",
        "ui/ux": "ui ux design",
    }
    
    for abbr, full in replacements.items():
        query = re.sub(r'\b' + re.escape(abbr) + r'\b', full, query, flags=re.IGNORECASE)
    
    return query

# Xử lý dữ liệu từ MongoDB
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super(JSONEncoder, self).default(obj)

def preprocess_mongodb_data():
    """
    Lấy dữ liệu từ MongoDB và chuyển đổi thành văn bản cho RAG
    """
    print("Đang lấy dữ liệu từ MongoDB và tiền xử lý...")
    
    # Lấy tất cả dữ liệu khóa học và giảng viên không giới hạn số lượng
    try:
        # Lấy tất cả khóa học - không giới hạn
        courses = mongodb.get_courses(limit=None)
        
        # Lấy tất cả giảng viên - không giới hạn
        mentors = mongodb.get_mentors(limit=None)
        
        print(f"Đã tìm thấy {len(courses)} khóa học và {len(mentors)} giảng viên từ MongoDB")
        
        if len(courses) == 0 and len(mentors) == 0:
            print("CẢNH BÁO: Không tìm thấy dữ liệu trong MongoDB. Vui lòng kiểm tra lại kết nối và dữ liệu.")
            return []
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu từ MongoDB: {e}")
        return []
    
    # Chuẩn bị dữ liệu để chuyển thành văn bản
    course_texts = []
    for course in courses:
        # Chuẩn bị thông tin giảng viên nếu có
        mentor_info = ""
        if 'mentorInfo' in course and course['mentorInfo']:
            mentor = course['mentorInfo']
            mentor_user = course.get('mentorUser', {})
            mentor_name = mentor_user.get('name', 'Chưa có thông tin')
            
            specializations = ", ".join(mentor.get('specialization', []))
            achievements = ", ".join(mentor.get('achievements', []))
            
            mentor_info = f"""
            Giảng viên: {mentor_name}
            Kinh nghiệm: {mentor.get('experience', 0)} năm
            Chuyên môn: {specializations}
            Thành tựu: {achievements}
            Đánh giá: {mentor.get('averageRating', 0)}/5
            """
        
        # Chuẩn bị thông tin lợi ích và yêu cầu
        benefits = ", ".join([b.get('title', '') for b in course.get('benefits', [])])
        prerequisites = ", ".join([p.get('title', '') for p in course.get('prerequisites', [])])
        
        # Chuẩn bị thông tin bài học
        lessons = []
        for lesson in course.get('courseData', []):
            lesson_text = f"""
            Bài học: {lesson.get('title', '')}
            Phần: {lesson.get('videoSection', '')}
            Mô tả: {lesson.get('description', '')}
            Thời lượng: {lesson.get('videoLength', 0)} phút
            """
            lessons.append(lesson_text)
        
        lessons_text = "\n".join(lessons)
        
        # Xử lý categories nếu là mảng
        categories = course.get('categories', '')
        if isinstance(categories, list):
            categories = ", ".join(categories)
        
        # Xử lý tags nếu là mảng
        tags = course.get('tags', '')
        if isinstance(tags, list):
            tags = ", ".join(tags)
        
        # Chuyển đổi ObjectId thành string nếu cần
        course_id = str(course.get('_id', '')) if isinstance(course.get('_id'), ObjectId) else course.get('_id', '')
        
        # Tạo văn bản đầy đủ cho khóa học
        course_text = f"""
        ID KHÓA HỌC: {course_id}
        TÊN KHÓA HỌC: {course.get('name', '')}
        MÔ TẢ: {course.get('description', '')}
        DANH MỤC: {categories}
        GIÁ: {course.get('price', 0)} VND
        TRÌNH ĐỘ: {course.get('level', '')}
        ĐÁNH GIÁ: {course.get('ratings', 0)}/5
        SỐ LƯỢT MUA: {course.get('purchased', 0)}
        TAGS: {tags}
        
        THÔNG TIN GIẢNG VIÊN:
        {mentor_info}
        
        LỢI ÍCH KHÓA HỌC:
        {benefits}
        
        YÊU CẦU TIÊN QUYẾT:
        {prerequisites}
        
        NỘI DUNG KHÓA HỌC:
        {lessons_text}
        """
        
        course_texts.append(course_text)
    
    # Chuẩn bị dữ liệu giảng viên
    mentor_texts = []
    for mentor in mentors:
        # Lấy thông tin user của giảng viên
        user_info = mentor.get('userInfo', {})
        
        # Chuyển đổi ObjectId thành string nếu cần
        mentor_id = str(mentor.get('_id', '')) if isinstance(mentor.get('_id'), ObjectId) else mentor.get('_id', '')
        
        # Lấy TẤT CẢ các khóa học của giảng viên
        mentor_courses = mongodb.get_courses_by_mentor(mentor.get('_id'), limit=None)
        courses_text = ""
        
        if mentor_courses:
            courses_text = "DANH SÁCH TẤT CẢ CÁC KHÓA HỌC:\n"
            for idx, course in enumerate(mentor_courses, 1):
                course_id = str(course.get('_id', '')) if isinstance(course.get('_id'), ObjectId) else course.get('_id', '')
                price = course.get('price', 0)
                level = course.get('level', 'Chưa xác định')
                rating = course.get('ratings', 0)
                
                courses_text += f"""
                {idx}. ID: {course_id}
                   Tên: [{course.get('name', '')}]
                   Trình độ: {level}
                   Giá: {price} VND
                   Đánh giá: {rating}/5 sao
                """
        else:
            courses_text = "DANH SÁCH KHÓA HỌC: Hiện chưa có khóa học nào."
        
        # Tạo văn bản đầy đủ cho giảng viên
        mentor_text = f"""
        ID GIẢNG VIÊN: {mentor_id}
        TÊN GIẢNG VIÊN: {user_info.get('name', '')}
        EMAIL: {user_info.get('email', '')}
        GIỚI THIỆU: {mentor.get('bio', '')}
        CHUYÊN MÔN: {', '.join(mentor.get('specialization', []))}
        KINH NGHIỆM: {mentor.get('experience', 0)} năm
        THÀNH TỰU: {', '.join(mentor.get('achievements', []))}
        ĐÁNH GIÁ: {mentor.get('averageRating', 0)}/5
        
        {courses_text}
        """
        
        mentor_texts.append(mentor_text)
    
    # Kết hợp tất cả văn bản
    all_texts = course_texts + mentor_texts
    
    return all_texts

# Tạo FAISS vector database
def build_vector_store():
    """
    Xây dựng FAISS vector store từ dữ liệu MongoDB
    """
    # Lấy dữ liệu từ MongoDB
    print("Bắt đầu lấy dữ liệu từ MongoDB...")
    texts = preprocess_mongodb_data()
    
    # Kiểm tra xem có dữ liệu không
    if not texts:
        print("CẢNH BÁO: Không có dữ liệu để xây dựng vector store!")
        print("Vui lòng kiểm tra kết nối MongoDB và đảm bảo dữ liệu đã được import.")
        # Trả về vector store trống nếu không có dữ liệu
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        return FAISS.from_texts(["Không có dữ liệu"], embeddings)
    
    print(f"Đã lấy được {len(texts)} văn bản để xây dựng vector store")
    
    # In ra một vài mẫu dữ liệu để kiểm tra
    if len(texts) > 0:
        print("\nMẫu dữ liệu đầu tiên:")
        print(texts[0][:500] + "...\n")  # Chỉ hiển thị 500 ký tự đầu tiên
    
    # CHIẾN LƯỢC CẢI TIẾN: Tạo các chunks chồng lấn với nhiều kích thước khác nhau
    
    # 1. Chunks nhỏ để tìm kiếm chính xác
    text_splitter_small = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ".", " "],
        chunk_size=800,
        chunk_overlap=200,
        is_separator_regex=False,
    )
    
    # 2. Chunks trung bình để cân bằng
    text_splitter_medium = RecursiveCharacterTextSplitter(
        separators=["\n\n\n", "\n\n", "\n", ".", " "],
        chunk_size=1500,
        chunk_overlap=300,
        is_separator_regex=False,
    )
    
    # 3. Chunks lớn để giữ context
    text_splitter_large = RecursiveCharacterTextSplitter(
        separators=["\n\n\n", "\n\n", "\n", ".", " "],
        chunk_size=2500,
        chunk_overlap=400,
        is_separator_regex=False,
    )
    
    # Tạo chunks với cả ba chiến lược
    text_chunks = []
    metadata_chunks = []
    
    try:
        for text in texts:
            # Thêm metadata vào từng chunk để truy xuất dễ dàng hơn
            # Trích xuất ID khóa học hoặc giảng viên từ văn bản
            id_match = re.search(r'ID (KHÓA HỌC|GIẢNG VIÊN): ([^\n]+)', text)
            entity_id = id_match.group(2) if id_match else "unknown"
            
            # Xác định loại entity (khóa học hoặc giảng viên)
            entity_type = "course" if "ID KHÓA HỌC" in text else "mentor"
            
            # Trích xuất tên
            name_match = re.search(r'TÊN (KHÓA HỌC|GIẢNG VIÊN): ([^\n]+)', text)
            entity_name = name_match.group(2) if name_match else "Không có tên"
            
            # Chunks nhỏ
            chunks_small = text_splitter_small.split_text(text)
            for chunk in chunks_small:
                text_chunks.append(chunk)
                metadata_chunks.append({
                    "id": entity_id,
                    "type": entity_type,
                    "name": entity_name,
                    "size": "small"
                })
            
            # Chunks trung bình
            chunks_medium = text_splitter_medium.split_text(text)
            for chunk in chunks_medium:
                text_chunks.append(chunk)
                metadata_chunks.append({
                    "id": entity_id,
                    "type": entity_type,
                    "name": entity_name,
                    "size": "medium"
                })
            
            # Chunks lớn
            chunks_large = text_splitter_large.split_text(text)
            for chunk in chunks_large:
                text_chunks.append(chunk)
                metadata_chunks.append({
                    "id": entity_id,
                    "type": entity_type, 
                    "name": entity_name,
                    "size": "large"
                })
        
        print(f"Đã tạo {len(text_chunks)} đoạn văn bản từ dữ liệu MongoDB")
        
        if len(text_chunks) == 0:
            print("CẢNH BÁO: Không có chunks sau khi tách văn bản!")
            return None
        
        # In ra một vài mẫu chunks để kiểm tra
        if len(text_chunks) > 0:
            print("\nMẫu chunk đầu tiên:")
            print(text_chunks[0][:300] + "...\n")  # Chỉ hiển thị 300 ký tự đầu tiên
        
        # Sử dụng mô hình embedding đa ngôn ngữ tốt cho tiếng Việt
        print("Bắt đầu tạo embeddings...")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        print("Bắt đầu xây dựng FAISS vector store...")
        
        # Tạo vector store với metadata
        vector_store = FAISS.from_texts(
            text_chunks, 
            embeddings, 
            metadatas=metadata_chunks
        )
        
        # Kiểm tra vector store đã được tạo thành công chưa
        print(f"Vector store đã được tạo với {len(text_chunks)} chunks")
        
        return vector_store
    except Exception as e:
        print(f"LỖI khi xây dựng vector store: {e}")
        import traceback
        traceback.print_exc()
        return None

# Đọc file prompt
def load_prompt_template(file_path='prompt_templates/lms_prompt.txt'):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        # Prompt mặc định nếu file không tồn tại
        return """
        Bạn là một trợ lý chatbot thông minh của hệ thống LMS (Learning Management System).
        Nhiệm vụ của bạn là tư vấn và trả lời các câu hỏi về khóa học và giảng viên.
        Hãy sử dụng thông tin từ các tài liệu được cung cấp để trả lời câu hỏi của người dùng.
        
        Hãy trả lời ngắn gọn, súc tích và thân thiện. Nếu không có thông tin, hãy thừa nhận và đề xuất người dùng liên hệ trực tiếp với hỗ trợ viên.
        
        Khi giới thiệu khóa học, hãy đề cập: tên khóa học, giá tiền, trình độ, đánh giá và tên giảng viên.
        
        Khi giới thiệu giảng viên, hãy đề cập: tên, chuyên môn, kinh nghiệm, và các khóa học tiêu biểu.
        
        Khi người dùng muốn tìm khóa học theo chủ đề, hãy liệt kê TẤT CẢ các khóa học phù hợp với chủ đề đó.
        Liệt kê đầy đủ thông tin về từng khóa học, và đảm bảo cung cấp đúng ID của tất cả các khóa học.
        
        Tài liệu: {context}
        """

# Khởi tạo vector store một lần
print("Đang khởi tạo vector store từ dữ liệu MongoDB...")
vector_store = build_vector_store()

# Kiểm tra vector store đã được tạo thành công chưa
if vector_store is None:
    print("CẢNH BÁO: Không thể tạo vector store! Chatbot sẽ không hoạt động đúng.")
    # Tạo một vector store đơn giản với một văn bản rỗng để tránh lỗi
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vector_store = FAISS.from_texts(["Không có dữ liệu khóa học hoặc giảng viên."], embeddings)

# CẢI TIẾN: Cấu hình retriever với chiến lược kết hợp và filter dynamic
def get_retriever(query=None):
    """
    Tạo retriever với filter tùy chỉnh dựa trên query
    """
    filter_metadata = None
    
    # Xác định filter dựa trên loại truy vấn
    if query:
        query_lower = query.lower()
        if "khóa học" in query_lower:
            filter_metadata = {"type": "course"}
        elif "giảng viên" in query_lower or "giáo viên" in query_lower or "giáo sư" in query_lower:
            filter_metadata = {"type": "mentor"}
    
    # Cấu hình retriever với filter tương ứng
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            'k': 20,                    # Lấy 20 kết quả tốt nhất
            'score_threshold': 0.25,    # Giảm ngưỡng để bao gồm nhiều kết quả hơn
            'filter': filter_metadata,   # Áp dụng filter nếu có
            'fetch_k': 50               # Tìm kiếm sơ bộ 50 documents trước khi lọc
        }
    )

# Sử dụng retriever mặc định ban đầu (sẽ được thay thế trong các hàm call)
retriever = get_retriever()

# Load prompt template
prompt_template = load_prompt_template()

# Tạo context aware retriever chain
contextualize_q_system_prompt = """
Dựa vào lịch sử cuộc hội thoại giữa chatbot và người dùng 
(tin nhắn của chatbot có tiền tố [bot] và tin nhắn của người dùng có tiền tố [user]),
và căn cứ vào câu hỏi mới nhất của người dùng, 
hãy tạo ra một câu hỏi độc lập và đầy đủ ngữ cảnh.

ĐẶC BIỆT LƯU Ý:
1. Hiểu ngữ nghĩa tiếng Việt đa dạng và xử lý nhiều cách diễn đạt khác nhau:
   - "Có khóa học về X không?" = "Hãy liệt kê tất cả các khóa học liên quan đến X"
   - "Cho tôi biết về khóa X" = "Hãy cung cấp thông tin chi tiết về khóa học X"
   - "Ai dạy khóa X?" = "Ai là giảng viên của khóa học X và liệt kê TẤT CẢ các khóa học của giảng viên đó"
   - "Các khóa của giảng viên X" = "Liệt kê TẤT CẢ các khóa học do giảng viên X phụ trách"

2. Nếu người dùng hỏi "Có khóa học về X không?" hoặc "Khóa học về X?", hãy LUÔN chuyển thành câu hỏi rõ ràng "Hãy liệt kê tất cả các khóa học liên quan đến X".

3. Nếu người dùng hỏi thông tin về một giảng viên hoặc giảng viên của khóa học, hãy làm rõ rằng họ cần biết TẤT CẢ các khóa học của giảng viên đó.

4. Câu hỏi này phải có thể được hiểu mà không cần đọc lịch sử hội thoại trước đó.

5. Nếu người dùng hỏi về một khóa học cụ thể đã được đề cập trước đó, hãy đảm bảo bao gồm tên và ID của khóa học trong câu hỏi.

6. Nếu người dùng tham chiếu đến "khóa học này" hoặc "giảng viên này", hãy thay thế bằng tên cụ thể.

KHÔNG trả lời câu hỏi, chỉ chuyển đổi nó thành câu hỏi độc lập và đầy đủ ngữ cảnh.
Viết câu hỏi bằng tiếng Việt.
"""

contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

# Initialize the RAG chain
history_aware_retriever = create_history_aware_retriever(
    llm, retriever, contextualize_q_prompt
)

question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

# Add this after the rag_chain initialization
def safe_mongo_query(collection, query=None, limit=None, sort=None, sort_field=None, sort_order=1):
    """
    Thực hiện truy vấn MongoDB với error handling an toàn
    
    Args:
        collection: Collection MongoDB
        query: Query object (dict)
        limit: Số lượng kết quả tối đa
        sort: Dict cấu hình sort
        sort_field: Trường dùng để sort
        sort_order: Thứ tự sort (1: tăng dần, -1: giảm dần)
        
    Returns:
        list: Danh sách kết quả, trả về list rỗng nếu có lỗi
    """
    try:
        if collection is None:
            print("Lỗi: Collection MongoDB là None")
            return []
            
        # Xây dựng query
        find_query = {} if query is None else query
        
        # Cấu hình sort nếu có
        if sort:
            cursor = collection.find(find_query).sort(sort)
        elif sort_field:
            cursor = collection.find(find_query).sort(sort_field, sort_order)
        else:
            cursor = collection.find(find_query)
            
        # Áp dụng limit nếu có
        if limit is not None and limit > 0:
            cursor = cursor.limit(limit)
            
        # Convert cursor thành list
        results = list(cursor)
        return results
    except Exception as e:
        print(f"Lỗi khi truy vấn MongoDB: {e}")
        return []

def extract_mentor_name(query):
    """
    Trích xuất tên giảng viên từ câu hỏi với độ chính xác cao hơn
    """
    try:
        # Chuẩn hóa query (loại bỏ dấu, chuyển thành chữ thường)
        query_lower = query.lower()
        query_normalized = normalize_text(query)
        
        # Các mẫu regex mới để trích xuất tên giảng viên
        mentor_name_patterns = [
            r'thông tin về giảng viên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s|$|\?|\.)',
            r'thông tin giảng viên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s|$|\?|\.)',
            r'giảng viên tên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s|$|\?|\.)',
            r'giáo viên tên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s|$|\?|\.)',
            r'giảng viên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s+là ai|\s+như thế nào|\s+thế nào|\s+ra sao|\?|\.)',
            r'giáo viên\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s+là ai|\s+như thế nào|\s+thế nào|\s+ra sao|\?|\.)',
            r'thầy\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s|$|\?|\.)',
            r'cô\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?=\s|$|\?|\.)',
        ]
        
        # Tìm kiếm theo mẫu regex
        mentor_name = None
        for pattern in mentor_name_patterns:
            match = re.search(pattern, query_lower)
            if match:
                mentor_name = match.group(1).strip()
                break
        
        # Không tìm thấy theo pattern regex, thử tìm theo từ khóa
        if not mentor_name:
            # Kiểm tra nếu query chứa từ khóa "giảng viên" hoặc "giáo viên"
            keywords = ["giảng viên", "giáo viên", "mentor", "teacher", "thầy", "cô"]
            if any(keyword in query_lower for keyword in keywords):
                # Loại bỏ các từ khóa giảng viên/giáo viên và các từ khóa phổ biến khác
                filters = ["thông tin", "giảng viên", "giáo viên", "mentor", "teacher", 
                          "tên", "là ai", "như thế nào", "thế nào", "ra sao", "về", 
                          "của", "thầy", "cô", "chuyên ngành", "chuyên môn", "kinh nghiệm"]
                
                # Tạo danh sách các từ sau khi lọc
                words = query_lower.split()
                filtered_words = [word for word in words if word not in filters]
                
                # Nếu còn từ nào sau khi lọc, đó có thể là tên
                if filtered_words:
                    # Tìm các từ liên tiếp có thể là tên người (không phải số, không chứa các ký tự đặc biệt)
                    potential_names = []
                    current_name = []
                    
                    for word in filtered_words:
                        if re.match(r'^[A-ZÀ-Ỹa-zà-ỹ]+$', word):
                            current_name.append(word)
                        elif current_name:
                            potential_names.append(" ".join(current_name))
                            current_name = []
                    
                    if current_name:  # Thêm nhóm cuối nếu có
                        potential_names.append(" ".join(current_name))
                    
                    # Nếu tìm thấy tên tiềm năng, lấy tên dài nhất
                    if potential_names:
                        mentor_name = max(potential_names, key=len)
        
        # Nếu vẫn không tìm thấy, thử một cách tiếp cận khác với fuzzy matching
        if not mentor_name:
            # Lấy tối đa 10 giảng viên để so sánh
            mentors_collection = mongodb.get_collection('mentors')
            if mentors_collection:
                try:
                    mentors = safe_mongo_query(mentors_collection, {}, limit=10)
                    
                    # Thử tìm tên giảng viên trong câu hỏi dựa trên fuzzy matching
                    max_ratio = 0
                    best_match = None
                    
                    for mentor in mentors:
                        if 'full_name' in mentor and mentor['full_name']:
                            mentor_fullname = mentor['full_name'].lower()
                            mentor_normalized = normalize_text(mentor_fullname)
                            
                            # Thử so khớp tên đầy đủ
                            ratio = fuzz.partial_ratio(mentor_normalized, query_normalized)
                            if ratio > max_ratio and ratio > 70:  # Ngưỡng 70% match
                                max_ratio = ratio
                                best_match = mentor_fullname
                            
                            # Thử so khớp với từng phần của tên (họ, tên đệm, tên)
                            name_parts = mentor_fullname.split()
                            for part in name_parts:
                                if len(part) > 2:  # Chỉ so sánh với các phần có ít nhất 3 ký tự
                                    part_normalized = normalize_text(part)
                                    ratio = fuzz.partial_ratio(part_normalized, query_normalized)
                                    if ratio > max_ratio and ratio > 80:  # Ngưỡng cao hơn cho phần tên
                                        max_ratio = ratio
                                        best_match = mentor_fullname
                    
                    if best_match:
                        mentor_name = best_match
                except Exception as e:
                    print(f"Lỗi khi tìm kiếm fuzzy matching cho tên giảng viên: {e}")
        
        if mentor_name:
            print(f"Tìm thấy tên giảng viên: {mentor_name}")
        else:
            print("Không tìm thấy tên giảng viên trong câu hỏi")
        
        return mentor_name
    except Exception as e:
        print(f"Lỗi khi trích xuất tên giảng viên: {e}")
        return None

# Cải tiến 2: Semantic Question Understanding
def classify_query_intent(query):
    """
    Phân loại ý định của câu hỏi để xử lý tốt hơn
    """
    query_lower = query.lower()
    
    # Định nghĩa các pattern cho từng loại intent
    intent_patterns = {
        'course_search': [
            r'khóa học', r'khoá học', r'course', r'các khóa', 
            r'liệt kê.*khóa', r'có khóa', r'tìm khóa',
            r'khóa học về', r'học về', r'học online',
            r'danh sách.*khóa', r'thông tin.*khóa'
        ],
        'course_detail': [
            r'chi tiết.*khóa học', r'thông tin chi tiết.*khóa', 
            r'nội dung.*khóa', r'bài học.*khóa',
            r'có những gì.*khóa', r'khóa học.*gồm',
            r'\[(.*?)\]', r'"(.*?)"', r'\'(.*?)\'',  # Khóa học trong ngoặc
            r'khóa học mã số'
        ],
        'mentor_search': [
            r'giảng viên', r'giáo viên', r'mentor', r'teacher',
            r'người dạy', r'ai dạy', r'người hướng dẫn'
        ],
        'mentor_by_name': [
            r'giảng viên tên', r'giáo viên tên',
            r'thông tin.*giảng viên', r'thông tin.*giáo viên',
            r'giảng viên.*là ai', r'thầy', r'cô'
        ],
        'mentor_by_specialization': [
            r'giảng viên.*chuyên', r'giáo viên.*chuyên',
            r'giảng viên.*expert', r'chuyên gia về',
            r'giảng viên.*về', r'ai.*chuyên.*về'
        ],
        'course_comparison': [
            r'so sánh.*khóa', r'khóa nào tốt hơn',
            r'khóa.*hay hơn', r'nên chọn khóa',
            r'khác nhau.*khóa', r'đâu tốt hơn',
            r'.*và.*khác gì nhau'
        ],
        'price_question': [
            r'giá.*khóa', r'học phí', r'chi phí', 
            r'bao nhiêu tiền', r'mất bao nhiêu'
        ],
        'rating_question': [
            r'đánh giá', r'rating', r'review',
            r'feedback', r'nhận xét', r'tốt không'
        ]
    }
    
    # Ngưỡng điểm tối thiểu để xác định intent
    MIN_INTENT_SCORE = 1
    
    # Điểm số cho mỗi intent (để xác định độ tin cậy)
    intent_scores = {intent: 0 for intent in intent_patterns}
    
    # Tính điểm cho mỗi intent dựa trên số lượng pattern khớp
    for intent, patterns in intent_patterns.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                # Tăng điểm cho intent này
                intent_scores[intent] += 1
                
                # Bonus points cho một số điều kiện đặc biệt
                if intent == 'course_comparison' and re.search(r'so sánh.*khóa', query_lower):
                    intent_scores[intent] += 2  # Boost cho so sánh rõ ràng
                
                if intent == 'mentor_by_name' and re.search(r'giảng viên tên', query_lower):
                    intent_scores[intent] += 2  # Boost cho tìm giảng viên theo tên rõ ràng
                    
                if intent == 'course_detail' and any(re.search(pattern, query_lower) for pattern in [r'\[(.*?)\]', r'"(.*?)"', r'\'(.*?)\'']):
                    intent_scores[intent] += 2  # Boost cho chi tiết khóa học cụ thể
    
    # Xác định tất cả intent có điểm số > ngưỡng tối thiểu
    matched_intents = [intent for intent, score in intent_scores.items() if score >= MIN_INTENT_SCORE]
    
    # Sắp xếp intent theo điểm số
    sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Xác định intent chính (có điểm cao nhất và vượt ngưỡng)
    primary_intent = sorted_intents[0][0] if sorted_intents and sorted_intents[0][1] >= MIN_INTENT_SCORE else None
    
    # Xử lý các trường hợp xung đột
    if len(matched_intents) > 1:
        # Nếu có sự chênh lệch không đáng kể giữa hai intent hàng đầu, xem xét ưu tiên
        top_score = sorted_intents[0][1]
        second_score = sorted_intents[1][1]
        
        if top_score - second_score <= 1:  # Điểm chênh lệch nhỏ
            # Ưu tiên theo thứ tự
            priority_order = [
                'course_comparison',  # Ưu tiên cao nhất cho so sánh
                'course_detail',       # Sau đó đến chi tiết khóa học
                'mentor_by_name',      # Tiếp theo là tìm giảng viên theo tên
                'mentor_by_specialization', 
                'price_question', 
                'rating_question',
                'mentor_search',
                'course_search'        # Ưu tiên thấp nhất
            ]
            
            # Tìm intent có ưu tiên cao nhất trong các intent matched
            for intent in priority_order:
                if intent in matched_intents:
                    primary_intent = intent
                    break
    
    # Nếu không tìm thấy intent cụ thể, mặc định là course_search
    if not primary_intent:
        primary_intent = 'course_search'  # Default intent
    
    # Xác định các intent phụ (có điểm > ngưỡng và không phải intent chính)
    secondary_intents = [intent for intent in matched_intents if intent != primary_intent]
    
    # Độ tin cậy của intent chính (tỷ lệ phần trăm)
    primary_confidence = 0
    if primary_intent in intent_scores and sum(intent_scores.values()) > 0:
        primary_confidence = (intent_scores[primary_intent] / sum(intent_scores.values())) * 100
    
    print(f"Điểm số intent: {intent_scores}")
    print(f"Phân loại intent câu hỏi: {primary_intent} (độ tin cậy: {primary_confidence:.1f}%), Tất cả intent: {matched_intents}")
    
    return {
        'primary_intent': primary_intent,
        'all_intents': matched_intents,
        'secondary_intents': secondary_intents,
        'intent_scores': intent_scores,
        'confidence': primary_confidence
    }

def send_continue_chat(chat_history, query):
    """
    Xử lý tin nhắn và trả về kết quả từ LLM
    
    Args:
        chat_history: Mảng các đối tượng ChatHistory
        query: Chuỗi câu hỏi từ người dùng
        
    Returns:
        Chuỗi câu trả lời từ LLM
    """
    history = []

    for chat in chat_history:
        chat_query = chat.content
        if chat.is_user:
            history.append(HumanMessage(content=chat_query))
        else:
            history.append(AIMessage(content=chat_query))

    try:
        print(f"Xử lý câu hỏi gốc: '{query}'")
        
        # Kiểm tra xem query có trống không
        if not query or len(query.strip()) == 0:
            return "Xin chào, tôi là EduBot, trợ lý chatbot của hệ thống quản lý học tập. Bạn có thể hỏi tôi về các khóa học hoặc giảng viên."
        
        # Kiểm tra cache trước khi xử lý query
        cached_response = cache.get(query)
        if cached_response:
            print("Sử dụng kết quả từ cache")
            return cached_response
            
        # Tiền xử lý query tiếng Việt để cải thiện hiểu ngữ nghĩa
        processed_query = preprocess_vietnamese_query(query)

        # QUAN TRỌNG: Tạo cache key từ processed_query để đảm bảo nhất quán
        cache_key = processed_query

        # Cải tiến: Phân loại intent của câu hỏi trước khi xử lý
        intent_info = classify_query_intent(processed_query)
        print(f"Intent chính: {intent_info['primary_intent']}")
        print(f"Tất cả intent: {intent_info['all_intents']}")
        
        # Xử lý dựa trên intent chính
        primary_intent = intent_info['primary_intent']

        # Xử lý so sánh khóa học
        if primary_intent == 'course_comparison':
            print("Phát hiện yêu cầu so sánh khóa học")
            
            # Trích xuất tên các khóa học để so sánh
            comparison_patterns = [
                r'so sánh\s+(?:giữa\s+)?(?:khóa học\s+)?[\[\"\']?(.*?)[\]\"\']?\s+(?:và|với|or|and)\s+[\[\"\']?(.*?)[\]\"\']?(?=\s|$|\?|\.)',
                r'(?:khóa học\s+)?[\[\"\']?(.*?)[\]\"\']?\s+(?:và|với|or|and)\s+[\[\"\']?(.*?)[\]\"\']?(?=\s|$|\?|\.)(?:.*?)(?:khác nhau|giống nhau|nên chọn)',
                r'(?:nên\s+chọn|tốt\s+hơn)\s+(?:khóa học\s+)?[\[\"\']?(.*?)[\]\"\']?\s+(?:hay|hoặc|or|hay\s+là)\s+[\[\"\']?(.*?)[\]\"\']?(?=\s|$|\?|\.)'
            ]
            
            course_names = []
            for pattern in comparison_patterns:
                matches = re.findall(pattern, processed_query)
                if matches:
                    # Flatten kết quả tìm được (có thể là tuple hoặc string)
                    if isinstance(matches[0], tuple):
                        course_names.extend([course.strip() for course in matches[0] if course.strip()])
                    else:
                        course_names.extend([course.strip() for course in matches if course.strip()])
                    break
            
            # Nếu không tìm thấy bằng regex pattern, thử dùng cách đơn giản hơn
            if not course_names:
                # Tìm kiếm các từ khóa trong ngoặc hoặc ngoặc kép
                bracket_patterns = [r'\[(.*?)\]', r'"(.*?)"', r"'(.*?)'"]
                for pattern in bracket_patterns:
                    matches = re.findall(pattern, processed_query)
                    if matches:
                        course_names.extend([m.strip() for m in matches if m.strip()])
            
            print(f"Tên khóa học trích xuất được: {course_names}")
            
            # Cải tiến: Xử lý trường hợp không tìm thấy tên khóa học nào
            if not course_names:
                # Tạo prompt để LLM trích xuất tên khóa học
                extract_prompt = f"""
                Hãy trích xuất tên các khóa học mà người dùng muốn so sánh từ câu hỏi sau:
                "{processed_query}"
                
                Trả về dưới dạng danh sách các tên khóa học, mỗi tên trên một dòng.
                """
                try:
                    extract_response = llm.invoke(extract_prompt)
                    extracted_text = extract_response.content
                    # Tách các dòng và loại bỏ dấu gạch đầu dòng nếu có
                    extracted_lines = [line.strip().lstrip('- ') for line in extracted_text.split('\n') if line.strip()]
                    # Lọc các dòng có nội dung
                    course_names = [line for line in extracted_lines if len(line) > 2 and not line.startswith("Không")]
                    print(f"Tên khóa học trích xuất bằng LLM: {course_names}")
                except Exception as e:
                    print(f"Lỗi khi dùng LLM trích xuất tên khóa học: {e}")
                    # Thử phương pháp thay thế nếu LLM fails
                    potential_course_words = []
                    words = processed_query.split()
                    skip_words = ["khóa", "học", "so", "sánh", "với", "và", "hay", "hơn", "tốt", "course"]
                    potential_course_words = [w for w in words if len(w) > 3 and w.lower() not in skip_words]
                    
                    if len(potential_course_words) >= 2:
                        course_names = potential_course_words[:2]  # Lấy 2 từ đầu tiên có thể là tên khóa học
                        print(f"Tên khóa học trích xuất thủ công khi LLM fails: {course_names}")
            
            if course_names and len(course_names) >= 2:
                print(f"So sánh các khóa học: {course_names}")
                
                # Lấy thông tin từ MongoDB
                courses_collection = mongodb.get_collection('courses')
                compared_courses = []
                
                for course_name in course_names:
                    # Tìm kiếm khóa học dựa trên tên
                    course_query = {"name": {"$regex": course_name, "$options": "i"}, "status": "active"}
                    courses = safe_mongo_query(courses_collection, course_query, limit=2)
                    
                    if courses:
                        compared_courses.extend(courses)
                    else:
                        # Thử tìm kiếm với các từ khóa từ tên khóa học
                        keywords = course_name.split()
                        if len(keywords) > 1:  # Nếu có nhiều từ khóa
                            broader_query = {"$and": [{"name": {"$regex": keyword, "$options": "i"}} for keyword in keywords if len(keyword) > 2]}
                            broader_courses = safe_mongo_query(courses_collection, broader_query, limit=2)
                            if broader_courses:
                                compared_courses.extend(broader_courses)
                
                # Xử lý trường hợp không có đủ khóa học để so sánh
                if len(compared_courses) < 2:
                    # Tìm kiếm thêm với fuzzy matching
                    all_courses = safe_mongo_query(courses_collection, {"status": "active"}, limit=20)
                    
                    for course_name in course_names:
                        # Chuẩn hóa tên khóa học cần tìm
                        normalized_name = normalize_text(course_name.lower())
                        
                        # Tìm các khóa học tương tự
                        potential_matches = []
                        for course in all_courses:
                            if course.get('name'):
                                similarity = fuzz.ratio(normalized_name, normalize_text(course['name'].lower()))
                                if similarity > 60:  # Ngưỡng tương đồng 60%
                                    potential_matches.append((course, similarity))
                        
                        # Sắp xếp và lấy khóa học tốt nhất
                        potential_matches.sort(key=lambda x: x[1], reverse=True)
                        if potential_matches and potential_matches[0][0] not in compared_courses:
                            compared_courses.append(potential_matches[0][0])
                
                if len(compared_courses) >= 2:
                    # Tạo văn bản so sánh
                    comparison_text = "Thông tin chi tiết để so sánh các khóa học:\n\n"
                    
                    for i, course in enumerate(compared_courses, 1):
                        # Lấy thông tin giảng viên
                        mentor_id = course.get('mentor')
                        mentor_name = "Không xác định"
                        mentor_experience = 0
                        mentor_rating = 0
                        
                        if mentor_id:
                            mentors_collection = mongodb.get_collection('mentors')
                            mentor = mentors_collection.find_one({"_id": mentor_id})
                            if mentor:
                                users_collection = mongodb.get_collection('users')
                                user = users_collection.find_one({"_id": mentor.get('user')})
                                if user:
                                    mentor_name = user.get('name', 'Không xác định')
                                    mentor_experience = mentor.get('experience', 0)
                                    mentor_rating = mentor.get('averageRating', 0)
                        
                        # Thêm thông tin khóa học vào văn bản so sánh
                        comparison_text += f"Khóa học {i}: [{course.get('name', 'Không có tên')}]\n"
                        comparison_text += f"ID: {course.get('_id')}\n"
                        comparison_text += f"Mô tả: {course.get('description', 'Không có mô tả')}\n"
                        comparison_text += f"Giá: {course.get('price', 0)} VND\n"
                        comparison_text += f"Giảng viên: {mentor_name}\n"
                        comparison_text += f"   Kinh nghiệm giảng viên: {mentor_experience} năm\n"
                        comparison_text += f"   Đánh giá giảng viên: {mentor_rating}/5\n"
                        comparison_text += f"Trình độ khóa học: {course.get('level', 'Không xác định')}\n"
                        comparison_text += f"Đánh giá khóa học: {course.get('ratings', 0)}/5\n"
                        comparison_text += f"Số học viên: {course.get('purchased', 0)}\n\n"
                        
                        # Thêm thông tin về bài học
                        course_data = course.get('courseData', [])
                        if course_data:
                            comparison_text += f"Số bài học: {len(course_data)}\n"
                            comparison_text += f"Một số bài học:\n"
                            for j, lesson in enumerate(course_data[:3], 1):  # Chỉ hiện 3 bài học đầu tiên
                                comparison_text += f"- {lesson.get('title', '')} ({lesson.get('videoLength', 0)} phút)\n"
                            if len(course_data) > 3:
                                comparison_text += f"... và {len(course_data) - 3} bài học khác\n"
                        
                        # Thêm thông tin về lợi ích và yêu cầu
                        benefits = course.get('benefits', [])
                        prerequisites = course.get('prerequisites', [])
                        
                        if benefits:
                            comparison_text += "\nLợi ích khóa học:\n"
                            for benefit in benefits[:3]:  # Chỉ hiện 3 lợi ích đầu tiên
                                comparison_text += f"- {benefit.get('title', '')}\n"
                            if len(benefits) > 3:
                                comparison_text += f"... và {len(benefits) - 3} lợi ích khác\n"
                        
                        if prerequisites:
                            comparison_text += "\nYêu cầu tiên quyết:\n"
                            for prereq in prerequisites[:3]:  # Chỉ hiện 3 yêu cầu đầu tiên
                                comparison_text += f"- {prereq.get('title', '')}\n"
                            if len(prerequisites) > 3:
                                comparison_text += f"... và {len(prerequisites) - 3} yêu cầu khác\n"
                        
                        comparison_text += "---\n\n"
                    
                    # Tạo prompt yêu cầu LLM so sánh
                    prompt = f"""
                    Người dùng hỏi: "{processed_query}"
                    
                    Hãy so sánh chi tiết các khóa học dựa trên thông tin sau:
                    
                    {comparison_text}
                    
                    So sánh về:
                    1. Nội dung và mục tiêu học tập
                    2. Trình độ và đối tượng phù hợp
                    3. Giá cả và giá trị
                    4. Giảng viên và chất lượng giảng dạy
                    5. Đánh giá và phản hồi
                    
                    Cuối cùng, đưa ra lời khuyên về việc nên chọn khóa học nào phù hợp với từng đối tượng hoặc nhu cầu cụ thể.
                    """
                    
                    try:
                        response = llm.invoke(prompt)
                        result = response.content
                        # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                        cache.set(query, result)  # Cache với query gốc
                        if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                            cache.set(processed_query, result)  # Cache với processed_query
                        return result
                    except Exception as e:
                        print(f"Lỗi khi gọi LLM để so sánh khóa học: {e}")
                        # Tạo phản hồi thủ công khi LLM fails
                        fallback_response = f"""
                        Tôi đã tìm thấy các khóa học mà bạn muốn so sánh:
                        
                        {comparison_text}
                        
                        Tuy nhiên, tôi đang gặp sự cố kỹ thuật khi phân tích chi tiết. 
                        Dựa vào thông tin trên, bạn có thể xem xét các yếu tố như giá cả, nội dung, giảng viên 
                        và đánh giá để lựa chọn khóa học phù hợp nhất với nhu cầu của bạn.
                        Bạn có thể liên hệ với bộ phận hỗ trợ để được tư vấn thêm.
                        """
                        return fallback_response
                else:
                    # Xử lý trường hợp không tìm đủ khóa học để so sánh
                    not_found_prompt = f"""
                    Người dùng muốn so sánh các khóa học: {', '.join(course_names)}
                    Nhưng không tìm thấy đủ khóa học để so sánh. Chỉ tìm thấy {len(compared_courses)} khóa học.
                    
                    Hãy trả lời một cách lịch sự, giải thích rằng không thể tìm thấy đầy đủ thông tin để so sánh các khóa học được yêu cầu.
                    Gợi ý người dùng thử tìm kiếm với tên khóa học chính xác hơn hoặc xem danh sách các khóa học hiện có.
                    """
                    response = llm.invoke(not_found_prompt)
                    result = response.content
                    # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                    cache.set(query, result)  # Cache với query gốc
                    if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                        cache.set(processed_query, result)  # Cache với processed_query
                    return result

        # CASE 1: Tìm kiếm khóa học cụ thể theo tên
        if "thông tin chi tiết về khóa học" in processed_query.lower():
            print("Phát hiện tìm kiếm khóa học cụ thể")
            
            # Trích xuất tên khóa học
            course_name_patterns = [
                r'thông tin chi tiết về khóa học (.*?)(?=\s|$)',
                r'khóa học (.*?)(?=\s|$)',
                r'\[(.*?)\]',
                r'"(.*?)"',
                r'\'(.*?)\''
            ]
            
            course_name = None
            for pattern in course_name_patterns:
                matches = re.findall(pattern, processed_query)
                if matches:
                    course_name = matches[0].strip()
                    break
            
            if course_name:
                print(f"Tìm kiếm khóa học với tên: '{course_name}'")
                
                # Tìm kiếm trong MongoDB theo tên khóa học
                query_obj = {
                    "name": {"$regex": course_name, "$options": "i"},
                    "status": "active"
                }
                
                courses_collection = mongodb.get_collection('courses')
                if not courses_collection:
                    print("Lỗi: Không thể lấy collection courses từ MongoDB")
                    specific_course = []
                else:
                    try:
                        specific_course = list(courses_collection.find(query_obj))
                    except Exception as e:
                        print(f"Lỗi khi truy vấn MongoDB: {e}")
                        specific_course = []
                
                if specific_course:
                    print(f"Tìm thấy {len(specific_course)} khóa học có tên phù hợp")
                    
                    # Lấy thông tin chi tiết cho mỗi khóa học tìm thấy
                    courses_text = "Thông tin chi tiết về khóa học bạn quan tâm:\n\n"
                    
                    for i, course in enumerate(specific_course, 1):
                        # Lấy thông tin giảng viên
                        mentor_id = course.get('mentor')
                        mentor_info = None
                        if mentor_id:
                            mentors_collection = mongodb.get_collection('mentors')
                            mentor = mentors_collection.find_one({"_id": mentor_id})
                            if mentor:
                                users_collection = mongodb.get_collection('users')
                                user = users_collection.find_one({"_id": mentor.get('user')})
                                if user:
                                    mentor_info = {
                                        "name": user.get('name', 'Không xác định'),
                                        "specialization": mentor.get('specialization', []),
                                        "experience": mentor.get('experience', 0),
                                        "averageRating": mentor.get('averageRating', 0)
                                    }
                        
                        # Tạo văn bản chi tiết về khóa học
                        courses_text += f"{i}. Tên khóa học: [{course.get('name', 'Không có tên')}]\n"
                        courses_text += f"   ID: {course.get('_id')}\n"
                        courses_text += f"   Mô tả: {course.get('description', 'Không có mô tả')}\n"
                        courses_text += f"   Giá: {course.get('price', 0)} VND\n"
                        
                        if mentor_info:
                            courses_text += f"   Giảng viên: {mentor_info['name']}\n"
                            courses_text += f"   Chuyên môn giảng viên: {', '.join(mentor_info['specialization'])}\n"
                            courses_text += f"   Kinh nghiệm giảng viên: {mentor_info['experience']} năm\n"
                            courses_text += f"   Đánh giá giảng viên: {mentor_info['averageRating']}/5\n"
                        else:
                            courses_text += f"   Giảng viên: Không có thông tin\n"
                        
                        courses_text += f"   Trình độ: {course.get('level', 'Không xác định')}\n"
                        courses_text += f"   Đánh giá: {course.get('ratings', 0)}/5\n"
                        
                        # Thêm thông tin về bài học
                        course_data = course.get('courseData', [])
                        if course_data:
                            courses_text += f"   Số bài học: {len(course_data)}\n"
                            courses_text += f"   Nội dung chi tiết:\n"
                            for j, lesson in enumerate(course_data[:5], 1):  # Chỉ hiển thị 5 bài học đầu tiên
                                courses_text += f"     {j}. {lesson.get('title', 'Không có tiêu đề')} "
                                courses_text += f"({lesson.get('videoLength', 0)} phút)\n"
                            
                            if len(course_data) > 5:
                                courses_text += f"     ... và {len(course_data) - 5} bài học khác\n"
                        
                        courses_text += "\n"
                    
                    # Tạo câu trả lời từ thông tin chi tiết
                    prompt = f"""
                    Hãy trả lời câu hỏi của người dùng: "{processed_query}" dựa trên thông tin sau:
                    
                    {courses_text}
                    
                    Trả lời đầy đủ, chi tiết, và tổ chức thông tin rõ ràng dễ đọc.
                    Sử dụng các thông tin chi tiết và tạo câu trả lời tự nhiên, thân thiện.
                    """
                    
                    response = llm.invoke(prompt)
                    result = response.content
                    # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                    cache.set(query, result)  # Cache với query gốc
                    if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                        cache.set(processed_query, result)  # Cache với processed_query
                    return result
                else:
                    # Không tìm thấy khóa học cụ thể, thử tìm kiếm tương tự
                    similar_courses = mongodb.search_courses(course_name, limit=5)
                    if similar_courses:
                        courses_text = f"Không tìm thấy khóa học có tên chính xác '{course_name}', nhưng có các khóa học tương tự:\n\n"
                        
                        for i, course in enumerate(similar_courses, 1):
                            mentor_name = "Không xác định"
                            if 'mentorUser' in course and course['mentorUser']:
                                mentor_name = course['mentorUser'].get('name', 'Không xác định')
                            
                            courses_text += f"{i}. Tên khóa học: [{course.get('name', 'Không có tên')}]\n"
                            courses_text += f"   ID: {course.get('_id')}\n"
                            courses_text += f"   Mô tả: {course.get('description', 'Không có mô tả')[:150]}...\n"
                            courses_text += f"   Giá: {course.get('price', 0)} VND\n"
                            courses_text += f"   Giảng viên: {mentor_name}\n"
                            courses_text += f"   Trình độ: {course.get('level', 'Không xác định')}\n\n"
                        
                        prompt = f"""
                        Người dùng muốn tìm thông tin về khóa học '{course_name}', nhưng không tìm thấy khóa học chính xác.
                        Dưới đây là các khóa học tương tự:
                        
                        {courses_text}
                        
                        Hãy trả lời người dùng một cách thân thiện, giải thích rằng không tìm thấy khóa học họ yêu cầu, 
                        nhưng giới thiệu các khóa học tương tự. Đề xuất họ có thể tìm kiếm với từ khóa khác hoặc xem danh sách tất cả các khóa học.
                        """
                        
                        response = llm.invoke(prompt)
                        result = response.content
                        # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                        cache.set(query, result)  # Cache với query gốc
                        if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                            cache.set(processed_query, result)  # Cache với processed_query
                        return result
        
        # CASE 1.5: Tìm kiếm giảng viên theo tên
        elif (("thông tin về giảng viên" in processed_query.lower()) or 
              ("giảng viên tên" in processed_query.lower()) or 
              ("thông tin giảng viên" in processed_query.lower()) or
              (re.search(r'giảng viên (?!có)(\w+)', processed_query.lower())) or
              (re.search(r'giáo viên (?!có)(\w+)', processed_query.lower()))):
            
            print("Phát hiện tìm kiếm giảng viên theo tên")
            
            # Sử dụng hàm cải tiến để trích xuất tên giảng viên
            mentor_name = extract_mentor_name(processed_query)
            
            if mentor_name:
                print(f"Tìm kiếm giảng viên với tên: '{mentor_name}'")
                
                # Tìm kiếm trong MongoDB
                mentors_collection = mongodb.get_collection('mentors')
                users_collection = mongodb.get_collection('users')
                
                # Tìm người dùng với tên phù hợp
                users = list(users_collection.find({"name": {"$regex": mentor_name, "$options": "i"}}))
                user_ids = [user['_id'] for user in users]
                
                # Tìm giảng viên có user_id thuộc danh sách trên
                mentors = []
                if user_ids:
                    mentors = list(mentors_collection.find({"user": {"$in": user_ids}}))
                
                # Nếu không tìm thấy kết quả chính xác, thử tìm kiếm fuzzy
                if not mentors:
                    print("Không tìm thấy kết quả chính xác, thử tìm kiếm với fuzzy matching")
                    all_users = list(users_collection.find({}))
                    potential_matches = []
                    
                    for user in all_users:
                        user_name = user.get('name', '')
                        if user_name:
                            # Chuẩn hóa tên người dùng và tên tìm kiếm
                            normalized_user_name = normalize_text(user_name.lower())
                            normalized_mentor_name = normalize_text(mentor_name.lower())
                            
                            # Tính độ tương đồng
                            similarity_ratio = fuzz.ratio(normalized_user_name, normalized_mentor_name)
                            if similarity_ratio > 60:  # Ngưỡng tương đồng 60%
                                potential_matches.append((user, similarity_ratio))
                    
                    # Sắp xếp theo độ tương đồng giảm dần
                    potential_matches.sort(key=lambda x: x[1], reverse=True)
                    
                    # Lấy 5 kết quả tốt nhất
                    top_matches = potential_matches[:5]
                    
                    if top_matches:
                        print(f"Tìm thấy {len(top_matches)} kết quả fuzzy matching")
                        user_ids = [match[0]['_id'] for match in top_matches]
                        mentors = list(mentors_collection.find({"user": {"$in": user_ids}}))
                
                if mentors:
                    print(f"Tìm thấy {len(mentors)} giảng viên có tên phù hợp")
                    
                    # Lấy thông tin chi tiết
                    mentors_text = "Thông tin chi tiết về giảng viên bạn quan tâm:\n\n"
                    
                    for i, mentor in enumerate(mentors, 1):
                        # Lấy thông tin user
                        user_id = mentor.get('user')
                        user = users_collection.find_one({"_id": user_id}) if user_id else None
                        user_name = user.get('name', 'Không xác định') if user else 'Không xác định'
                        
                        # Định dạng thông tin chuyên môn và thành tựu
                        specializations = ", ".join(mentor.get('specialization', []))
                        achievements = ", ".join(mentor.get('achievements', []))
                        
                        # Lấy TẤT CẢ các khóa học của giảng viên
                        mentor_courses = mongodb.get_courses_by_mentor(mentor.get('_id'), limit=None)
                        courses_text = ""
                        
                        if mentor_courses:
                            courses_text = "\n\nDANH SÁCH TẤT CẢ KHÓA HỌC CỦA GIẢNG VIÊN:\n"
                            for idx, course in enumerate(mentor_courses, 1):
                                courses_text += f"{idx}. [{course.get('name', 'Không có tên')}]\n"
                                courses_text += f"   Giá: {course.get('price', 0)} VND\n"
                                courses_text += f"   Trình độ: {course.get('level', 'Chưa xác định')}\n"
                                courses_text += f"   Đánh giá: {course.get('ratings', 0)}/5 sao\n\n"
                        else:
                            courses_text = "\n\nGiảng viên này chưa có khóa học nào."
                        
                        # Thêm thông tin giảng viên vào văn bản
                        mentors_text += f"{i}. Tên giảng viên: {user_name}\n"
                        mentors_text += f"   Kinh nghiệm: {mentor.get('experience', 0)} năm\n"
                        mentors_text += f"   Chuyên môn: {specializations}\n"
                        mentors_text += f"   Thành tựu: {achievements}\n"
                        mentors_text += f"   Đánh giá: {mentor.get('averageRating', 0)}/5 sao\n"
                        mentors_text += courses_text
                        mentors_text += "\n---\n"
                    
                    # Tạo prompt để LLM trả lời
                    prompt = f"""
                    Hãy trả lời câu hỏi của người dùng: "{processed_query}" dựa trên thông tin sau:
                    
                    {mentors_text}
                    
                    Trả lời đầy đủ, chi tiết về thông tin của giảng viên và TẤT CẢ các khóa học của họ.
                    Đối với danh sách khóa học, hãy đảm bảo liệt kê đầy đủ tên khóa học với đúng ID và thông tin quan trọng.
                    """
                    
                    response = llm.invoke(prompt)
                    result = response.content
                    # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                    cache.set(query, result)  # Cache với query gốc
                    if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                        cache.set(processed_query, result)  # Cache với processed_query
                    return result
                else:
                    # Không tìm thấy giảng viên, thử gợi ý các giảng viên khác
                    random_mentors = list(mentors_collection.find().limit(5))
                    
                    if random_mentors:
                        mentors_text = f"Không tìm thấy giảng viên có tên '{mentor_name}'. Dưới đây là một số giảng viên khác trong hệ thống:\n\n"
                        
                        for i, mentor in enumerate(random_mentors, 1):
                            # Lấy thông tin người dùng
                            user_id = mentor.get('user')
                            user = users_collection.find_one({"_id": user_id}) if user_id else None
                            user_name = user.get('name', 'Không xác định') if user else 'Không xác định'
                            
                            mentors_text += f"{i}. Tên giảng viên: {user_name}\n"
                            mentors_text += f"   Chuyên môn: {', '.join(mentor.get('specialization', []))}\n"
                            mentors_text += f"   Kinh nghiệm: {mentor.get('experience', 0)} năm\n\n"
                        
                        prompt = f"""
                        Người dùng muốn tìm thông tin về giảng viên tên '{mentor_name}', nhưng không tìm thấy giảng viên này.
                        Dưới đây là một số giảng viên khác trong hệ thống:
                        
                        {mentors_text}
                        
                        Hãy trả lời người dùng một cách thân thiện, giải thích rằng không tìm thấy giảng viên họ yêu cầu, 
                        nhưng giới thiệu một số giảng viên khác. Đề xuất họ có thể tìm kiếm với từ khóa khác hoặc xem danh sách tất cả các giảng viên.
                        """
                        
                        response = llm.invoke(prompt)
                        result = response.content
                        # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                        cache.set(query, result)  # Cache với query gốc
                        if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                            cache.set(processed_query, result)  # Cache với processed_query
                        return result
        
        # CASE 2: Tìm kiếm giảng viên theo chuyên môn hoặc kinh nghiệm
        elif ("tìm kiếm giảng viên có" in processed_query.lower()) or (("giảng viên" in processed_query.lower() or "giáo viên" in processed_query.lower()) and ("chuyên môn" in processed_query.lower() or "kinh nghiệm" in processed_query.lower())):
            print("Phát hiện tìm kiếm giảng viên theo chuyên môn hoặc kinh nghiệm")
            
            # Trích xuất thông tin tìm kiếm
            specialization_match = re.search(r'chuyên môn\s+(\w+|\w+\s+\w+)', processed_query.lower())
            experience_match = re.search(r'kinh nghiệm\s+(\d+)', processed_query.lower())
            
            specialization = None
            experience = None
            
            if specialization_match:
                specialization = specialization_match.group(1).strip()
                print(f"Tìm kiếm giảng viên có chuyên môn: {specialization}")
            
            if experience_match:
                experience = int(experience_match.group(1))
                print(f"Tìm kiếm giảng viên có kinh nghiệm: {experience} năm")
            
            # Tìm kiếm trong MongoDB
            mentors_collection = mongodb.get_collection('mentors')
            users_collection = mongodb.get_collection('users')
            
            query = {}
            
            if specialization:
                query["specialization"] = {"$regex": specialization, "$options": "i"}
            
            if experience:
                query["experience"] = {"$gte": experience}
            
            # Thực hiện tìm kiếm
            mentors = list(mentors_collection.find(query))
            
            if mentors:
                print(f"Tìm thấy {len(mentors)} giảng viên phù hợp")
                
                # Lấy thông tin chi tiết
                mentors_text = "Danh sách giảng viên phù hợp với yêu cầu của bạn:\n\n"
                
                for i, mentor in enumerate(mentors, 1):
                    # Lấy thông tin người dùng
                    user_id = mentor.get('user')
                    user = users_collection.find_one({"_id": user_id}) if user_id else None
                    user_name = user.get('name', 'Không xác định') if user else 'Không xác định'
                    
                    mentors_text += f"{i}. Tên giảng viên: {user_name}\n"
                    mentors_text += f"   ID: {mentor.get('_id')}\n"
                    mentors_text += f"   Chuyên môn: {', '.join(mentor.get('specialization', []))}\n"
                    mentors_text += f"   Kinh nghiệm: {mentor.get('experience', 0)} năm\n"
                    mentors_text += f"   Đánh giá: {mentor.get('averageRating', 0)}/5\n"
                    
                    # Lấy thông tin khóa học
                    mentor_courses = mongodb.get_courses_by_mentor(mentor.get('_id'), limit=None)
                    if mentor_courses:
                        mentors_text += f"   Danh sách khóa học ({len(mentor_courses)}):\n"
                        for j, course in enumerate(mentor_courses[:3], 1):
                            mentors_text += f"     {j}. [{course.get('name', 'Không có tên')}]\n"
                        
                        if len(mentor_courses) > 3:
                            mentors_text += f"     ... và {len(mentor_courses) - 3} khóa học khác\n"
                    else:
                        mentors_text += "   Hiện chưa có khóa học nào.\n"
                    
                    mentors_text += "\n"
                
                # Tạo câu trả lời
                prompt = f"""
                Hãy trả lời câu hỏi của người dùng: "{processed_query}" dựa trên thông tin sau:
                
                {mentors_text}
                
                Trả lời đầy đủ, rõ ràng và cung cấp thông tin chi tiết về các giảng viên.
                Nếu người dùng hỏi về chuyên môn {specialization if specialization else ''}, hãy nhấn mạnh vào phần chuyên môn của giảng viên.
                Nếu người dùng hỏi về kinh nghiệm {experience if experience else ''} năm, hãy nhấn mạnh vào phần kinh nghiệm.
                """
                
                response = llm.invoke(prompt)
                result = response.content
                # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                cache.set(query, result)  # Cache với query gốc
                if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                    cache.set(processed_query, result)  # Cache với processed_query
                return result
            else:
                # Không tìm thấy giảng viên phù hợp
                all_mentors = list(mentors_collection.find().limit(5))
                
                if all_mentors:
                    mentors_text = f"Không tìm thấy giảng viên phù hợp với yêu cầu của bạn, nhưng đây là một số giảng viên khác:\n\n"
                    
                    for i, mentor in enumerate(all_mentors, 1):
                        # Lấy thông tin người dùng
                        user_id = mentor.get('user')
                        user = users_collection.find_one({"_id": user_id}) if user_id else None
                        user_name = user.get('name', 'Không xác định') if user else 'Không xác định'
                        
                        mentors_text += f"{i}. Tên giảng viên: {user_name}\n"
                        mentors_text += f"   Chuyên môn: {', '.join(mentor.get('specialization', []))}\n"
                        mentors_text += f"   Kinh nghiệm: {mentor.get('experience', 0)} năm\n\n"
                    
                    prompt = f"""
                    Người dùng muốn tìm giảng viên {f'có chuyên môn {specialization}' if specialization else ''}
                    {f'có kinh nghiệm {experience} năm' if experience else ''}, nhưng không tìm thấy.
                    
                    Dưới đây là một số giảng viên khác:
                    
                    {mentors_text}
                    
                    Hãy trả lời người dùng một cách thân thiện, giải thích rằng không tìm thấy giảng viên phù hợp với yêu cầu của họ,
                    nhưng giới thiệu các giảng viên khác. Đề xuất họ có thể tìm kiếm với tiêu chí khác.
                    """
                    
                    response = llm.invoke(prompt)
                    result = response.content
                    # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                    cache.set(query, result)  # Cache với query gốc
                    if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                        cache.set(processed_query, result)  # Cache với processed_query
                    return result
        
        # Tiếp tục với các trường hợp khác từ code hiện tại
        # Kiểm tra nếu đây là truy vấn về khóa học
        if "khóa học" in processed_query.lower():
            print("Phát hiện truy vấn về khóa học - thực hiện tìm kiếm kết hợp")
            
            # Tạo context-aware retriever với retriever đã lọc
            context_retriever = create_history_aware_retriever(
                llm, get_retriever(processed_query), contextualize_q_prompt
            )
            
            # Tạo question answering chain với retriever đã lọc
            qa_chain = create_stuff_documents_chain(llm, qa_prompt)
            context_aware_rag_chain = create_retrieval_chain(context_retriever, qa_chain)
            
            # Chiến lược 1: Thử sử dụng RAG trước
            response = context_aware_rag_chain.invoke({"input": processed_query, "chat_history": history})
            documents = response.get('documents', [])
            print(f"RAG search: Đã tìm thấy {len(documents)} tài liệu liên quan")
            
            # Nếu RAG không tìm thấy đủ tài liệu, sử dụng tìm kiếm trực tiếp MongoDB
            if len(documents) < 2:
                print("Không đủ kết quả từ RAG, thực hiện tìm kiếm MongoDB trực tiếp")
                
                # Trích xuất từ khóa chính để tìm kiếm
                search_terms = extract_search_terms(processed_query)
                
                all_courses = []
                for term in search_terms:
                    # Tìm kiếm trực tiếp trong MongoDB
                    print(f"Tìm kiếm khóa học với từ khóa: '{term}'")
                    courses = mongodb.search_courses(term, limit=None)
                    
                    # Thêm các khóa học mới vào danh sách
                    for course in courses:
                        course_id = str(course.get('_id', ''))
                        # Kiểm tra xem khóa học đã tồn tại trong danh sách chưa
                        if not any(str(c.get('_id', '')) == course_id for c in all_courses):
                            all_courses.append(course)
                
                print(f"Tìm kiếm MongoDB: Đã tìm thấy {len(all_courses)} khóa học")
                
                if all_courses:
                    # Tạo văn bản mô tả các khóa học
                    courses_text = "Dưới đây là các khóa học có liên quan trong hệ thống:\n\n"
                    
                    for i, course in enumerate(all_courses, 1):
                        mentor_name = "Không xác định"
                        if 'mentorUser' in course and course['mentorUser']:
                            mentor_name = course['mentorUser'].get('name', 'Không xác định')
                        
                        courses_text += f"{i}. Tên khóa học: [{course.get('name', 'Không có tên')}]\n"
                        courses_text += f"   ID: {course.get('_id')}\n"
                        courses_text += f"   Mô tả: {course.get('description', 'Không có mô tả')[:150]}...\n"
                        courses_text += f"   Giá: {course.get('price', 0)} VND\n"
                        courses_text += f"   Giảng viên: {mentor_name}\n"
                        courses_text += f"   Trình độ: {course.get('level', 'Không xác định')}\n"
                        courses_text += f"   Đánh giá: {course.get('ratings', 0)}/5\n\n"
                    
                    # Kết hợp kết quả từ RAG (nếu có) với kết quả từ MongoDB
                    combined_context = ""
                    if documents:
                        combined_context = "Thông tin từ vector search:\n"
                        combined_context += "\n".join([doc.page_content for doc in documents[:3]])
                        combined_context += "\n\nThông tin từ tìm kiếm trực tiếp:\n"
                    
                    combined_context += courses_text
                    
                    # Chuyển trực tiếp dữ liệu cho LLM để trả lời
                    prompt = f"""
                    Hãy trả lời câu hỏi của người dùng: "{processed_query}" dựa trên thông tin sau:
                    
                    {combined_context}
                    
                    Trả lời đầy đủ, rõ ràng và cung cấp thông tin chi tiết về từng khóa học.
                    Đảm bảo liệt kê đầy đủ tất cả các khóa học có trong dữ liệu.
                    """
                    
                    direct_response = llm.invoke(prompt)
                    result = direct_response.content
                    # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                    cache.set(query, result)  # Cache với query gốc
                    if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                        cache.set(processed_query, result)  # Cache với processed_query
                    return result

            answer = response["answer"]
            
            # Xử lý trường hợp không tìm thấy thông tin
            if "xin lỗi" in answer.lower() and ("không tìm thấy" in answer.lower() or "chưa có dữ liệu" in answer.lower()):
                print("Phát hiện câu trả lời 'không tìm thấy', thử tìm kiếm lại...")
                
                # Trích xuất từ khóa chính để tìm kiếm
                search_terms = extract_search_terms(processed_query)
                
                # Tìm kiếm trực tiếp trong MongoDB
                all_courses = []
                for term in search_terms:
                    print(f"Tìm kiếm trực tiếp với từ khóa: '{term}'")
                    courses = mongodb.search_courses(term, limit=None)
                    
                    # Thêm các khóa học mới vào danh sách
                    for course in courses:
                        course_id = str(course.get('_id', ''))
                        if not any(str(c.get('_id', '')) == course_id for c in all_courses):
                            all_courses.append(course)
                
                if all_courses:
                    print(f"Tìm thấy {len(all_courses)} khóa học từ MongoDB")
                    
                    # Tạo văn bản mô tả các khóa học
                    courses_text = "Dưới đây là các khóa học có liên quan trong hệ thống:\n\n"
                    
                    for i, course in enumerate(all_courses, 1):
                        mentor_name = "Không xác định"
                        if 'mentorUser' in course and course['mentorUser']:
                            mentor_name = course['mentorUser'].get('name', 'Không xác định')
                        
                        courses_text += f"{i}. Tên khóa học: [{course.get('name', 'Không có tên')}]\n"
                        courses_text += f"   ID: {course.get('_id')}\n"
                        courses_text += f"   Mô tả: {course.get('description', 'Không có mô tả')[:150]}...\n"
                        courses_text += f"   Giá: {course.get('price', 0)} VND\n"
                        courses_text += f"   Giảng viên: {mentor_name}\n"
                        courses_text += f"   Trình độ: {course.get('level', 'Không xác định')}\n"
                        courses_text += f"   Đánh giá: {course.get('ratings', 0)}/5\n\n"
                    
                    # Chuyển trực tiếp dữ liệu cho LLM để trả lời
                    prompt = f"""
                    Hãy trả lời câu hỏi của người dùng: "{processed_query}" dựa trên thông tin sau:
                    
                    {courses_text}
                    
                    Trả lời đầy đủ, rõ ràng và cung cấp thông tin chi tiết về từng khóa học.
                    Đảm bảo liệt kê đầy đủ tất cả các khóa học có trong dữ liệu.
                    """
                    
                    direct_response = llm.invoke(prompt)
                    result = direct_response.content
                    # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                    cache.set(query, result)  # Cache với query gốc
                    if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                        cache.set(processed_query, result)  # Cache với processed_query
                    return result
            
            return answer
        else:
            # Thử truy vấn với RAG bình thường cho các câu hỏi không liên quan đến khóa học
            try:
                response = rag_chain.invoke({"input": processed_query, "chat_history": history})
                result = response.get("answer", "")
                # Lưu kết quả vào cache - sử dụng query gốc và processed_query
                cache.set(query, result)  # Cache với query gốc
                if query != processed_query:  # Nếu query đã được xử lý khác với query gốc
                    cache.set(processed_query, result)  # Cache với processed_query
                return result
            except Exception as e:
                print(f"Lỗi khi gọi LLM trong RAG: {e}")
                fallback_response = """
                Xin lỗi, tôi đang gặp sự cố kỹ thuật và không thể trả lời câu hỏi của bạn ngay lúc này.
                Vui lòng thử lại sau hoặc liên hệ với bộ phận hỗ trợ để được giúp đỡ.
                """
                return fallback_response
    
    except Exception as e:
        print(f"Lỗi khi xử lý tin nhắn: {e}")
        return "Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn. Vui lòng thử lại sau."

def extract_search_terms(query):
    """
    Trích xuất các từ khóa tìm kiếm từ câu truy vấn
    """
    query = query.lower()
    
    # Loại bỏ các cụm từ phổ biến không liên quan đến nội dung
    for phrase in ['liệt kê', 'tất cả', 'khóa học', 'về', 'các', 'có', 'không', 'cho tôi', 'xem']:
        query = query.replace(phrase, ' ')
    
    # Tách query thành các từ riêng biệt và loại bỏ từ ngừng
    words = query.split()
    words = [w for w in words if len(w) > 2 and w not in ['của', 'với', 'và', 'hay', 'là', 'tôi', 'bạn']]
    
    # Thêm các cụm từ dài hơn để tăng độ chính xác
    terms = words.copy()
    
    # Thêm cụm từ có 2 từ liên tiếp
    for i in range(len(words) - 1):
        terms.append(f"{words[i]} {words[i+1]}")
    
    # Loại bỏ trùng lặp và từ quá ngắn
    terms = list(set([term.strip() for term in terms if len(term.strip()) > 2]))
    
    # Đảm bảo các từ khóa quan trọng luôn có trong danh sách tìm kiếm
    important_terms = ['python', 'java', 'javascript', 'web', 'mobile', 'android', 'ios', 
                      'ai', 'ml', 'machine learning', 'react', 'angular', 'vue', 'node']
    
    for term in important_terms:
        if term in query and term not in terms:
            terms.append(term)
    
    # Loại bỏ các từ khóa quá chung chung
    terms = [t for t in terms if len(t) > 2]
    
    print(f"Các từ khóa tìm kiếm: {terms}")
    return terms

# Test function
if __name__ == "__main__":
    # Kiểm tra tình trạng của cache
    try:
        cache_status = cache.check_cache_health() 
        print(f"Tình trạng cache: {cache_status}")
    except Exception as e:
        print(f"Lỗi khi kiểm tra cache: {e}")
    
    # Test query cơ bản với retry nếu LLM bị lỗi
    test_query = "Có khóa học nào về lập trình web không?"
    print(f"Câu hỏi: {test_query}")
    
    max_retries = 2
    retries = 0
    result = None
    
    while retries <= max_retries:
        try:
            result = send_continue_chat([], test_query)
            print(f"Trả lời: {result}")
            break
        except Exception as e:
            print(f"Lỗi khi xử lý query (lần thử {retries+1}/{max_retries+1}): {e}")
            retries += 1
            if retries > max_retries:
                result = "Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn sau nhiều lần thử. Vui lòng thử lại sau."
                print(f"Trả lời sau khi hết lượt retry: {result}")
    
    if result:
        # Test câu hỏi tiếp theo với lịch sử hội thoại
        test_query2 = "Khóa học đó có những bài học nào?"
        print(f"Câu hỏi tiếp theo: {test_query2}")
        
        chat_history = [
            type('obj', (object,), {'content': test_query, 'is_user': True}),
            type('obj', (object,), {'content': result, 'is_user': False})
        ]
        
        try:
            result2 = send_continue_chat(chat_history, test_query2)
            print(f"Trả lời: {result2}")
        except Exception as e:
            print(f"Lỗi khi xử lý câu hỏi tiếp theo: {e}")
            print("Trả lời: Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn.")
    
    # Kiểm tra cache sau khi test
    try:
        cache_status = cache.check_cache_health()
        print(f"Tình trạng cache sau khi test: {cache_status}")
    except Exception as e:
        print(f"Lỗi khi kiểm tra cache sau test: {e}")
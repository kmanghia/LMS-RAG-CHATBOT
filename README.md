# LMS RAG Chatbot

Chatbot thông minh tích hợp RAG (Retrieval Augmented Generation) cho hệ thống quản lý học tập (LMS), giúp tư vấn khóa học và thông tin giảng viên từ dữ liệu MongoDB.

## Tổng quan hệ thống

LMS-RAG-Chatbot là hệ thống AI tiên tiến kết hợp giữa các mô hình ngôn ngữ lớn (LLM) và kỹ thuật RAG để cung cấp phản hồi chính xác và liền mạch về các khóa học và giảng viên. Hệ thống truy xuất thông tin từ cơ sở dữ liệu MongoDB, xử lý ngữ cảnh hội thoại, và tạo ra phản hồi cá nhân hóa.

### Kiến trúc hệ thống

- **Vector Database Layer**: Sử dụng FAISS để lưu trữ và tìm kiếm vector embeddings
- **Context Manager**: Xử lý và duy trì ngữ cảnh hội thoại xuyên suốt
- **RAG Engine**: Kết hợp dữ liệu lấy được và chỉ dẫn prompt để tạo phản hồi
- **Cache Layer**: Lưu trữ các phản hồi phổ biến để cải thiện hiệu suất
- **MongoDB Connector**: Kết nối trực tiếp với cơ sở dữ liệu để truy vấn thông tin

## Tính năng chi tiết

### Tư vấn khóa học thông minh
- Tìm kiếm khóa học dựa trên nhiều tiêu chí (chủ đề, trình độ, giá cả, ...)
- Phân tích nhu cầu người dùng qua xử lý ngôn ngữ tự nhiên (NLP)
- Đề xuất khóa học phù hợp với trình độ và mục tiêu của người dùng
- So sánh chi tiết giữa các khóa học để giúp người dùng lựa chọn

### Hỗ trợ thông tin giảng viên
- Cung cấp tiểu sử chi tiết và chuyên môn của giảng viên
- Liệt kê đầy đủ các khóa học của từng giảng viên
- Tìm kiếm giảng viên theo chuyên môn hoặc kinh nghiệm
- Đánh giá và phản hồi từ học viên về giảng viên

### Xử lý hội thoại tiên tiến
- Duy trì ngữ cảnh qua nhiều lượt hội thoại liên tiếp
- Hiểu đúng các câu hỏi tiếp nối hoặc tham chiếu đến thông tin trước đó
- Phân tích intent (ý định) của người dùng để định hướng phản hồi
- Hỗ trợ các biểu hiện ngôn ngữ đa dạng và xử lý lỗi chính tả

### Tối ưu hóa hiệu suất
- Bộ nhớ đệm (cache) cho các truy vấn phổ biến
- Xử lý song song các quá trình tìm kiếm và tạo phản hồi
- Quản lý tài nguyên LLM thông minh để giảm chi phí API
- Tự động dọn dẹp và bảo trì hệ thống cache

## Yêu cầu hệ thống

- Python 3.8 hoặc cao hơn
- MongoDB 4.4 hoặc cao hơn
- Tối thiểu 4GB RAM
- Ổ cứng: ít nhất 1GB để lưu trữ vector database và cache
- Google Gemini API key

## Cài đặt và Chạy

### Sử dụng Docker (Khuyến nghị)

1. Clone repository này:
```
git clone <repository-url>
cd LMS-RAG-Chatbot
```

2. Tạo file `.env` từ `.env-example`:
```
cp .env-example .env
```

3. Cập nhật thông tin trong file `.env`:
```
# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# MongoDB Connection
MONGODB_URI=mongodb://localhost:27017/lms_db
MONGODB_DB_NAME=lms_db

# Flask Settings
FLASK_ENV=development
DEBUG=True
PORT=8080
```

4. Chạy với Docker Compose:
```
docker-compose up --build
```

Chatbot sẽ chạy tại http://localhost:8080

### Cài đặt thủ công

1. Clone repository
```
git clone <repository-url>
cd LMS-RAG-Chatbot
```

2. Tạo môi trường ảo Python:
```
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Cài đặt các thư viện:
```
pip install -r requirements.txt
```

4. Tạo file `.env` từ `.env-example` và cập nhật thông tin

5. Chạy ứng dụng:
```
python run.py
```

### Sử dụng Command Line Interface

Hệ thống cung cấp một giao diện dòng lệnh đơn giản để tương tác với chatbot:

```
python simple_cli.py
```

Các lệnh CLI hỗ trợ:
- `exit`, `quit`: Thoát chương trình
- `clear`: Xóa lịch sử hội thoại
- `help`: Hiển thị trợ giúp
- `cache status`: Kiểm tra tình trạng cache
- `cache clear`: Xóa toàn bộ cache

## API Endpoints

### Chat API

- **POST /chat**
  - Gửi tin nhắn và nhận phản hồi từ chatbot
  - Body: `{ "content": "Tin nhắn người dùng", "userId": 123 }`
  - Response: `{ "data": { "content": "Phản hồi từ chatbot", ... }, "statusCode": 200, "message": "Success" }`

- **GET /chat/history/:userId**
  - Lấy lịch sử chat của một người dùng
  - Response: `{ "data": { "session_1": [...], "session_2": [...] }, "statusCode": 200, "message": "Success" }`

- **DELETE /chat/clear/:userId**
  - Xóa lịch sử chat của một người dùng
  - Response: `{ "statusCode": 200, "message": "Chat history cleared for user {userId}" }`

### Quản lý Cache API (Mới)

- **GET /admin/cache/status**
  - Xem tình trạng và thống kê cache
  - Response: `{ "data": { "total_entries": 100, "valid_entries": 98, ... }, "statusCode": 200, "message": "Success" }`

- **POST /admin/cache/clear**
  - Xóa toàn bộ cache
  - Response: `{ "statusCode": 200, "message": "Cache cleared successfully" }`

## Cấu trúc dự án chi tiết

```
LMS-RAG-Chatbot/
├── app.py                    # Flask server
├── lms_rag.py                # RAG system chính
│   ├── Vector store
│   ├── LLM integration
│   ├── Intent classification
│   └── Retrieval logic
├── db_connector.py           # Kết nối MongoDB
├── response_cache.py         # Hệ thống cache
├── model.py                  # MongoDB models
├── run.py                    # Entrypoint
├── simple_cli.py             # Command line interface
├── requirements.txt          # Dependencies
├── Dockerfile                # Docker config
├── docker-compose.yml        # Docker Compose config
├── .env-example              # Biến môi trường mẫu
├── IMPROVEMENTS.md           # Tài liệu cải tiến
├── prompt_templates/         # Templates cho LLM
│   └── lms_prompt.txt        # Prompt chính
└── response_cache/           # Thư mục lưu trữ cache


## Tùy chỉnh nâng cao

### Tùy chỉnh Prompt

Bạn có thể tùy chỉnh cách chatbot phản hồi bằng cách sửa đổi file `prompt_templates/lms_prompt.txt`.

Các phần quan trọng trong prompt:
- Hướng dẫn chung về hành vi chatbot
- Cách định dạng trả lời cho từng loại câu hỏi
- Xử lý các trường hợp khi không tìm thấy thông tin
- Chiến lược so sánh khóa học

### Tùy chỉnh cài đặt Vector Search

Mở file `lms_rag.py` và điều chỉnh các tham số sau:
- Kích thước chunk văn bản (`chunk_size`)
- Số lượng kết quả tìm kiếm (`search_kwargs.k`)
- Ngưỡng điểm số tương đồng (`search_kwargs.score_threshold`)

### Tùy chỉnh bộ nhớ cache

Mở file `response_cache.py` và điều chỉnh:
- Thời gian cache hết hạn (`max_age_hours`)
- Khoảng thời gian dọn dẹp tự động (`cleanup_interval_minutes`)

## Xử lý sự cố

### Vấn đề kết nối MongoDB
- Kiểm tra chuỗi kết nối trong file `.env`
- Đảm bảo MongoDB đang chạy và có thể truy cập
- Kiểm tra quyền truy cập database

### Lỗi API Gemini
- Xác minh API key còn hiệu lực
- Kiểm tra giới hạn rate limit của API
- Đảm bảo kết nối internet ổn định

### Cache không hoạt động
- Kiểm tra quyền ghi vào thư mục `response_cache/`
- Chạy lệnh `cache status` từ CLI để kiểm tra tình trạng
- Thử xóa cache với lệnh `cache clear`

### Vấn đề với Docker
- Đảm bảo Docker và Docker Compose đã được cài đặt
- Kiểm tra logs: `docker-compose logs`
- Làm mới container: `docker-compose down && docker-compose up --build`

## Ví dụ truy vấn

Chatbot hỗ trợ nhiều loại câu hỏi khác nhau:

### Tìm kiếm khóa học
- "Có những khóa học nào về Python?"
- "Liệt kê tất cả các khóa học về web development"
- "Khóa học nào phù hợp cho người mới học lập trình?"

### Thông tin giảng viên
- "Thông tin về giảng viên Nguyễn Văn A"
- "Giảng viên nào có chuyên môn về Machine Learning?"
- "Ai dạy khóa học Python nâng cao?"

### So sánh khóa học
- "So sánh khóa học Python cơ bản và Python nâng cao"
- "Khóa học Java và C# khác nhau như thế nào?"
- "Nên chọn khóa học React hay Angular?"

### Câu hỏi về giá và đánh giá
- "Khóa học Machine Learning có giá bao nhiêu?"
- "Đánh giá về khóa học Web Development thế nào?"

## Đóng góp

Đóng góp và gợi ý cải thiện luôn được hoan nghênh! Vui lòng tuân theo các bước sau:

1. Fork repository
2. Tạo branch mới (`git checkout -b feature/amazing-feature`)
3. Commit thay đổi của bạn (`git commit -m 'Add some amazing feature'`)
4. Push lên branch (`git push origin feature/amazing-feature`)
5. Mở Pull Request

## Bản quyền và giấy phép

© 2023 LMS-RAG-Chatbot Team. Tất cả các quyền được bảo lưu.

## Liên hệ và hỗ trợ

Nếu bạn cần hỗ trợ hoặc có câu hỏi, vui lòng liên hệ qua:
- Email: nghiangua111@gmail.com
- GitHub Issues: Mở issue mới trong repository 
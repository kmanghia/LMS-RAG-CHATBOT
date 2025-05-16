# Cải tiến cho LMS-RAG-Chatbot

Tài liệu này trình bày các cải tiến được thực hiện cho hệ thống LMS-RAG-Chatbot nhằm nâng cao khả năng, hiệu suất và trải nghiệm người dùng.

## 1. Nâng cao nhận diện tên giảng viên

### Tính năng đã triển khai:
- **Cải thiện mẫu Regex**: Bổ sung các mẫu regex tinh vi hơn để trích xuất tên giảng viên từ câu hỏi của người dùng
- **Chuẩn hóa & xử lý dấu**: Thêm hỗ trợ cho văn bản tiếng Việt có dấu và không dấu
- **Fuzzy Matching**: Triển khai so khớp chuỗi mờ để xử lý lỗi đánh máy, tên một phần và biến thể chính tả
- **Trích xuất tên nhận biết ngữ cảnh**: Trích xuất tên dựa trên ngữ cảnh xung quanh

### Lợi ích:
- Độ chính xác cao hơn trong nhận diện giảng viên
- Xử lý tên tiếng Việt mạnh mẽ hơn
- Khả năng chấp nhận đầu vào người dùng đa dạng hơn
- Xử lý được tên không đầy đủ và bị viết sai

## 2. Hiểu câu hỏi theo ngữ nghĩa

### Tính năng đã triển khai:
- **Phân loại ý định (Intent)**: Bổ sung hệ thống phân loại intent toàn diện
- **Danh mục câu hỏi**: Nhận diện các loại câu hỏi khác nhau (chi tiết khóa học, truy vấn giảng viên, so sánh)
- **Xử lý theo thứ tự ưu tiên**: Xử lý intent theo thứ tự độ cụ thể
- **Phát hiện nhiều intent**: Có thể nhận diện nhiều intent trong một câu hỏi

### Lợi ích:
- Tạo phản hồi chính xác hơn
- Xử lý tốt hơn các câu hỏi phức tạp
- Cải thiện định tuyến đến bộ xử lý phản hồi phù hợp
- Hỗ trợ luồng hội thoại tự nhiên hơn

### Các loại intent được hỗ trợ:
- `course_search`: Tìm kiếm khóa học tổng quát
- `course_detail`: Thông tin khóa học cụ thể
- `mentor_search`: Tìm kiếm giảng viên tổng quát
- `mentor_by_name`: Tìm kiếm giảng viên cụ thể theo tên
- `mentor_by_specialization`: Tìm kiếm giảng viên theo chuyên môn
- `course_comparison`: So sánh nhiều khóa học
- `price_question`: Câu hỏi về giá
- `rating_question`: Câu hỏi về đánh giá và nhận xét

## 3. Chức năng so sánh khóa học

### Tính năng đã triển khai:
- **Phân tích nhiều khóa học**: So sánh chi tiết của hai hoặc nhiều khóa học
- **So sánh toàn diện**: Phân tích nội dung, giá cả, độ khó và chất lượng giảng viên
- **Logic đề xuất**: Cung cấp đề xuất khóa học dựa trên ngữ cảnh
- **Pattern Matching**: Cải thiện khả năng phát hiện các câu hỏi so sánh

### Lợi ích:
- Giúp người dùng đưa ra quyết định sáng suốt
- Cung cấp so sánh đối chiếu các tính năng khóa học
- Làm nổi bật những khác biệt không rõ ràng
- Đưa ra đề xuất cá nhân hóa dựa trên tiêu chí so sánh

## 4. Bộ nhớ đệm phản hồi

### Tính năng đã triển khai:
- **Tiện ích cache**: Tạo hệ thống lưu trữ cache phản hồi chuyên dụng (`response_cache.py`)
- **Hết hạn theo thời gian**: Các mục cache tự động hết hạn sau một khoảng thời gian có thể cấu hình
- **MD5 Hashing**: Băm truy vấn hiệu quả để tạo khóa cache
- **Dọn dẹp cache**: Tự động xóa các mục cache hết hạn

### Lợi ích:
- Phản hồi nhanh hơn đáng kể cho các truy vấn phổ biến
- Giảm lượng gọi API đến dịch vụ LLM
- Chi phí vận hành thấp hơn
- Xử lý tốt hơn trong thời điểm lưu lượng cao

## 5. Cài đặt và sử dụng tính năng mới

### Các phụ thuộc:
Bổ sung các phụ thuộc mới vào `requirements.txt`:
- `fuzzywuzzy` và `python-Levenshtein`: Dùng cho so khớp chuỗi mờ
- `thefuzz`: Tiện ích so khớp mờ bổ sung

### Thiết lập:
```bash
# Cài đặt các phụ thuộc mới
pip install -r requirements.txt

# Tạo thư mục cache (tùy chọn - sẽ tự động tạo nếu chưa tồn tại)
mkdir response_cache
```

### Sử dụng các tính năng mới:
- Tất cả tính năng tự động hoạt động, không cần cấu hình thêm
- Cài đặt cache có thể điều chỉnh trong `response_cache.py`
- Ngưỡng phân loại intent có thể điều chỉnh trong hàm `classify_query_intent()`

## 6. Lộ trình cải tiến tương lai

### Cải tiến ngắn hạn:
- **Học tùy chỉnh người dùng**: Điều chỉnh phản hồi dựa trên lịch sử tương tác
- **Mở rộng thư viện intent**: Bổ sung thêm các danh mục intent chuyên biệt
- **Tối ưu hóa hiệu suất**: Tối ưu hóa tìm kiếm vector với xử lý theo lô

### Mục tiêu trung hạn:
- **Hỗ trợ đa ngôn ngữ**: Mở rộng ngoài tiếng Việt
- **Bộ nhớ hội thoại**: Triển khai theo dõi trạng thái hội thoại mạnh mẽ hơn
- **Phân tích nâng cao**: Bổ sung phân tích sử dụng và theo dõi các truy vấn phổ biến nhất

### Tầm nhìn dài hạn:
- **Công cụ cá nhân hóa**: Cung cấp đề xuất khóa học cá nhân hóa hoàn toàn
- **Hỗ trợ đa phương tiện**: Bổ sung hỗ trợ nội dung khóa học hình ảnh và video
- **Lập hồ sơ người dùng nâng cao**: Khớp người dùng với các khóa học lý tưởng dựa trên phong cách học tập

---

# Cải tiến cho LMS-RAG-Chatbot

## 1. Cải tiến nhận diện tên giảng viên

Hệ thống đã được cải tiến để nhận diện tên giảng viên chính xác hơn, với các tính năng:

- **Nhận diện tên tiếng Việt** cả có dấu và không dấu thông qua hàm `normalize_text` và biểu thức regex nâng cao
- **Fuzzy matching** cho phép tìm kiếm gần đúng tên giảng viên với độ tương đồng cấu hình được
- **Sử dụng thông tin ngữ cảnh** để xác định tên giảng viên dựa trên vị trí từ trong câu hỏi
- **Kết hợp nhiều phương pháp nhận diện** để tăng độ chính xác, bao gồm:
  - Pattern matching với regex
  - Tách và phân tích cấu trúc câu
  - So khớp với cơ sở dữ liệu giảng viên
  - Tiền xử lý và chuẩn hóa tên

## 2. Cải tiến hiểu câu hỏi theo ngữ nghĩa

Đã phân loại câu hỏi dựa trên ý định (intent) để xử lý thông minh hơn:

- **Hệ thống phân loại intent** với các nhóm chính:
  - `course_search`: Tìm kiếm khóa học
  - `course_detail`: Thông tin chi tiết khóa học
  - `mentor_search`: Tìm kiếm giảng viên
  - `mentor_by_name`: Tìm giảng viên theo tên
  - `mentor_by_specialization`: Tìm giảng viên theo chuyên môn
  - `course_comparison`: So sánh khóa học
  - `price_question`: Câu hỏi về giá
  - `rating_question`: Câu hỏi về đánh giá

- **Xử lý theo độ tin cậy của intent** với ngưỡng tối thiểu có thể cấu hình
- **Xử lý ưu tiên intent** khi có nhiều intent được phát hiện
- **Phát hiện nhiều intent** trong cùng một câu hỏi

## 3. Cải tiến chức năng so sánh khóa học

So sánh khóa học bằng cách:

- **Trích xuất tên khóa học** từ câu hỏi với nhiều pattern khác nhau
- **Hỗ trợ fuzzy matching** cho tên khóa học không khớp chính xác
- **LLM-assisted extraction** khi không tìm thấy tên khóa học bằng regex
- **So sánh nhiều tiêu chí** như:
  - Thời lượng khóa học
  - Nội dung và chủ đề
  - Mức độ khó
  - Giá, đánh giá và phản hồi
  - Đối tượng phù hợp
- **Xử lý thông minh khi không tìm thấy đủ khóa học** để so sánh

## 4. Cải tiến Cache hệ thống

Tối ưu hóa hiệu suất với caching:

- **MD5 hashing** cho query để tạo cache key
- **Thời gian sống (TTL) của cache** có thể cấu hình
- **Dọn dẹp cache tự động** bằng thread background chạy theo định kỳ
- **Kiểm tra và xóa cache hết hạn** khi truy cập
- **Cache nhiều phiên bản của câu hỏi** (gốc và đã xử lý)
- **Lưu trữ an toàn** với xử lý ngoại lệ
- **API đơn giản** với các phương thức `get()`, `set()`, và `clear_all()`
- **Atomic file operations** để đảm bảo tính toàn vẹn dữ liệu cache
- **Tự động kiểm tra và sửa chữa** cache bằng phương thức `check_cache_health()`

## 5. Cải tiến xử lý lỗi

Cải thiện tính ổn định của hệ thống:

- **Bảo vệ khỏi MongoDB null results** với hàm `safe_mongo_query`
- **Xử lý trường hợp kết nối MongoDB bị mất** hoặc collection không tồn tại
- **Xử lý lỗi trong luồng bất đồng bộ** của thread dọn dẹp cache
- **Đảm bảo truy cập thread-safe** cho cache với RLock
- **Xử lý lỗi cho JSON serialization** với MongoDB ObjectId
- **Kiểm tra query rỗng** và các trường hợp đầu vào không hợp lệ
- **Xử lý lỗi LLM API** với thử lại và fallback responses
- **Error boundary** trong các hàm quan trọng như `extract_mentor_name` và `send_continue_chat`

## 6. Cải tiến tiền xử lý tiếng Việt

Nâng cao xử lý ngôn ngữ tiếng Việt:

- **Chuẩn hóa văn bản tiếng Việt** bỏ dấu cho so khớp không phân biệt dấu
- **Xử lý các từ viết tắt phổ biến** (ví dụ: "k/h" thành "khóa học")
- **Chuẩn hóa khoảng trắng** giữa các từ
- **Chuyển đổi tất cả thành chữ thường** để đảm bảo so khớp không phân biệt hoa thường

## 7. Cải tiến tài liệu hướng dẫn

Tài liệu được cải thiện để làm rõ các tính năng và hướng dẫn:

- **Văn bản giải thích trong code** với docstrings và comments
- **Ví dụ sử dụng** trong prompt template
- **Hướng dẫn format câu hỏi** để có kết quả tốt nhất
- **Giải thích chi tiết các format so sánh khóa học** và trích xuất thông tin

## 8. Cải tiến Command Line Interface

Thêm giao diện dòng lệnh mới và cải thiện trải nghiệm người dùng:

- **Simple CLI Interface** với giao diện thân thiện qua `simple_cli.py`
- **Xử lý lệnh đặc biệt** như clear, help, cache status và cache clear
- **Error handling** cho tất cả các tương tác với chatbot
- **Hiển thị trực quan** với màu sắc khác nhau cho người dùng và chatbot
- **Hỗ trợ các phím tắt** như Ctrl+C để dừng xử lý câu hỏi hoặc thoát
- **Lịch sử hội thoại liền mạch** với lưu trữ tự động
- **Hướng dẫn sử dụng trong ứng dụng** với menu trợ giúp 
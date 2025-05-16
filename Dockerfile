FROM python:3.9-slim

WORKDIR /app

# Cài đặt các gói cần thiết
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Sao chép requirements.txt
COPY requirements.txt .

# Cài đặt thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn
COPY . .

# Tạo thư mục prompt_templates nếu chưa tồn tại
RUN mkdir -p prompt_templates

# Mở cổng cho Flask server
EXPOSE 8080

# Chạy ứng dụng
CMD ["python", "run.py"] 
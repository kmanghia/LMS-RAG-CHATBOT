"""
Response Cache Utility - Lưu trữ và truy xuất cache cho câu trả lời
Cải tiến hiệu suất cho LMS-RAG-Chatbot
"""

import os
import json
import hashlib
import threading
import time
from datetime import datetime, timedelta

class ResponseCache:
    """
    Cache lưu trữ các câu trả lời để tối ưu hiệu suất cho các truy vấn phổ biến
    """
    def __init__(self, cache_dir="response_cache", max_age_hours=24, cleanup_interval_minutes=30):
        self.cache_dir = cache_dir
        self.max_age_hours = max_age_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        
        # Tạo thư mục cache nếu chưa tồn tại
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        self.cleanup_old_entries()
        
        # Khởi động thread dọn dẹp tự động
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """
        Khởi động thread dọn dẹp cache định kỳ
        """
        def cleanup_task():
            while True:
                # Đợi theo khoảng thời gian được cấu hình
                time.sleep(self.cleanup_interval_minutes * 60)
                try:
                    self.cleanup_old_entries()
                except Exception as e:
                    print(f"Lỗi trong thread dọn dẹp cache: {e}")
        
        # Tạo và khởi động thread với daemon=True để tránh chặn chương trình khi tắt
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        print(f"Đã khởi động thread dọn dẹp cache tự động (chạy mỗi {self.cleanup_interval_minutes} phút)")
    
    def _get_cache_key(self, query):
        """
        Tạo key cache từ query
        """
        # Chuẩn hóa query
        normalized_query = query.lower().strip()
        # Tạo hash từ query
        return hashlib.md5(normalized_query.encode('utf-8')).hexdigest()
    
    def _get_cache_file_path(self, cache_key):
        """
        Tạo đường dẫn file cache từ cache key
        """
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get(self, query):
        """
        Lấy kết quả từ cache cho một query
        
        Returns:
            None nếu không có cache hoặc cache đã hết hạn
            str nếu có kết quả cache hợp lệ
        """
        if not query:
            return None
            
        try:
            cache_key = self._get_cache_key(query)
            cache_file = self._get_cache_file_path(cache_key)
            
            if not os.path.exists(cache_file):
                return None
            
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Lỗi định dạng file cache: {e}")
                try:
                    # Xóa file cache lỗi
                    os.remove(cache_file)
                except Exception:
                    pass
                return None
            
            # Kiểm tra thời gian tạo cache
            try:
                created_time = datetime.fromisoformat(cache_data.get('created_time', '2000-01-01'))
            except (ValueError, TypeError) as e:
                print(f"Lỗi khi parse thời gian: {e}")
                return None
            
            if datetime.now() - created_time > timedelta(hours=self.max_age_hours):
                # Cache đã hết hạn
                try:
                    os.remove(cache_file)  # Xóa luôn file hết hạn
                except:
                    pass
                return None
            
            print(f"Đã tìm thấy kết quả cache cho query: '{query[:30]}...'")
            return cache_data.get('response')
            
        except Exception as e:
            print(f"Lỗi khi đọc cache: {e}")
            return None
    
    def set(self, query, response):
        """
        Lưu kết quả vào cache
        """
        if not query or not response:
            return
            
        try:
            cache_key = self._get_cache_key(query)
            cache_file = self._get_cache_file_path(cache_key)
            
            # Đảm bảo thư mục cache tồn tại
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
            
            cache_data = {
                'query': query,
                'response': response,
                'created_time': datetime.now().isoformat()
            }
            
            # Sử dụng atomic write để tránh file corruption
            temp_file = cache_file + '.tmp'
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                # Atomic rename để đảm bảo file integrity
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                os.rename(temp_file, cache_file)
                print(f"Đã lưu kết quả vào cache cho query: '{query[:30]}...'")
            except Exception as e:
                print(f"Lỗi khi lưu cache tạm thời: {e}")
                # Dọn dẹp file tạm nếu có lỗi
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
        except Exception as e:
            print(f"Lỗi khi lưu cache: {e}")
    
    def cleanup_old_entries(self):
        """
        Xóa các cache entries đã hết hạn
        """
        try:
            now = datetime.now()
            files_removed = 0
            clean_errors = 0
            
            # Đảm bảo thư mục cache tồn tại
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
                return
            
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            try:
                                cache_data = json.load(f)
                                
                                try:
                                    created_time = datetime.fromisoformat(cache_data.get('created_time', '2000-01-01'))
                                    if now - created_time > timedelta(hours=self.max_age_hours):
                                        os.remove(file_path)
                                        files_removed += 1
                                except (ValueError, TypeError):
                                    # Thời gian không hợp lệ, xóa file
                                    os.remove(file_path)
                                    files_removed += 1
                            except json.JSONDecodeError:
                                # File JSON không hợp lệ, xóa
                                os.remove(file_path)
                                files_removed += 1
                    except Exception as e:
                        # Lỗi khi đọc hoặc xóa file
                        clean_errors += 1
                        print(f"Lỗi khi dọn dẹp file cache {filename}: {e}")
            
            if files_removed > 0:
                print(f"Đã xóa {files_removed} cache entries hết hạn")
            if clean_errors > 0:
                print(f"Có {clean_errors} lỗi khi dọn dẹp cache")
                
        except Exception as e:
            print(f"Lỗi khi dọn dẹp cache: {e}")
    
    def clear_all(self):
        """
        Xóa tất cả các mục cache
        """
        try:
            files_removed = 0
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, filename))
                    files_removed += 1
            
            print(f"Đã xóa tất cả {files_removed} cache entries")
        except Exception as e:
            print(f"Lỗi khi xóa toàn bộ cache: {e}")

    def check_cache_health(self):
        """
        Kiểm tra tình trạng của thư mục cache và sửa chữa nếu cần
        
        Returns:
            dict: Thông tin về tình trạng cache
        """
        try:
            # Đảm bảo thư mục cache tồn tại
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
                print(f"Đã tạo mới thư mục cache: {self.cache_dir}")
                return {"status": "created", "entries": 0}
            
            entries = 0
            valid_entries = 0
            invalid_entries = 0
            
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    entries += 1
                    file_path = os.path.join(self.cache_dir, filename)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            try:
                                json.load(f)
                                valid_entries += 1
                            except json.JSONDecodeError:
                                invalid_entries += 1
                                # Xóa các file không hợp lệ
                                os.remove(file_path)
                    except Exception:
                        invalid_entries += 1
                        try:
                            os.remove(file_path)
                        except:
                            pass
                        
            return {
                "status": "healthy" if invalid_entries == 0 else "repaired",
                "total_entries": entries,
                "valid_entries": valid_entries,
                "invalid_entries": invalid_entries
            }
        except Exception as e:
            print(f"Lỗi khi kiểm tra tình trạng cache: {e}")
            return {"status": "error", "message": str(e)}

# Instance mặc định
cache = ResponseCache(
    cache_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "response_cache"),
    max_age_hours=24,  # 24 giờ
    cleanup_interval_minutes=30  # 30 phút
) 
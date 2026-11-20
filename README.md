# Voice Retrieval Web Application (MMDBMS)

Ứng dụng Web hoàn chỉnh phục vụ lưu trữ và tìm kiếm giọng nói phụ nữ theo nội dung (Query-by-Example).  
Đề tài Bài tập lớn môn **Hệ Cơ Sở Dữ Liệu Đa Phương Tiện (MMDBMS)** - Học viện Công nghệ Bưu chính Viễn thông (PTIT).

Thư mục `Web/` này được đóng gói độc lập hoàn toàn (Self-Contained Repository), tích hợp sẵn toàn bộ mã nguồn Backend/Frontend, dịch vụ AI trích xuất đặc trưng và file sao lưu CSDL PostgreSQL (`voice_multimedia_db_backup.sql`), giúp bạn có thể clone/chạy trơn tru trên bất kỳ máy tính nào.

---

## 1. Kiến trúc Hệ thống

Ứng dụng được thiết kế theo mô hình Full-stack phân tầng:
* **Backend:** Flask REST API kết nối trực tiếp với Hệ quản trị CSDL **PostgreSQL** và mô hình học sâu **ECAPA-TDNN** (`speechbrain/spkrec-ecapa-voxceleb`) + **Librosa**.
* **Frontend:** Single Page Application (SPA) xây dựng trên nền **Tailwind CSS**, **Chart.js** và **HTML5 Web Audio API**.
* **Database Engine:** PostgreSQL quản trị 1,000 files giọng nữ, mảng vector nhúng `REAL[192]` và thực thi trực tiếp hàm `cosine_similarity_192()` trong nhân CSDL.

---

## 2. Cấu trúc Thư mục Độc lập (Self-Contained)

```text
Web/
├── .gitignore                          # Cấu hình bỏ qua tệp cache và upload tạm
├── README.md                           # Tài liệu hướng dẫn cài đặt & vận hành
├── requirements.txt                    # Danh mục thư viện Python phụ thuộc
├── start.bat                           # Script khởi động 1-click trên Windows
├── app.py                              # Flask Web Server & REST API endpoints
├── database/                           # Quản trị Cơ sở dữ liệu PostgreSQL
│   ├── __init__.py
│   ├── postgres_db_manager.py          # Data Access Object (DAO) kết nối CSDL
│   ├── setup_postgres_database.py      # Script 1-Click phục hồi CSDL tự động
│   └── voice_multimedia_db_backup.sql  # Toàn bộ cấu trúc & 1000 bản ghi CSDL (4.6 MB)
├── services/                           # Dịch vụ AI & Trích xuất đặc trưng
│   ├── __init__.py
│   ├── feature_extractor.py            # Trích xuất 29D Librosa & 192D ECAPA-TDNN
│   └── search_engine.py                # Thuật toán tìm kiếm 2 pha (Cosine + Euclid)
├── templates/
│   └── index.html                      # Giao diện chính Single Page Application
├── static/
│   ├── css/
│   │   └── style.css                   # Glassmorphism & Cyberpunk Theme
│   └── js/
│       └── app.js                      # AJAX, Waveform preview, Chart.js
└── uploads/                            # Thư mục chứa audio tạm người dùng upload
```

---

## 3. Hướng dẫn Cài đặt & Chạy trên Máy Mới

### Bước 1: Chuẩn bị môi trường Python & PostgreSQL
1. Cài đặt **Python 3.10 - 3.12** (Khuyến nghị 3.12).
2. Cài đặt **PostgreSQL** (bản 14 trở lên, đã kiểm thử trên PostgreSQL 18).
   * Mặc định tài khoản: user `postgres`, mật khẩu `123456`, port `5432`.
   * *(Nếu tài khoản của bạn khác, có thể chỉnh trong `database/postgres_db_manager.py` và `database/setup_postgres_database.py`)*.

### Bước 2: Cài đặt thư viện Python
Mở Terminal tại thư mục `Web/` và chạy:
```bash
pip install -r requirements.txt
```

### Bước 3: Cấu hình thông số hệ thống (`config.json`)
Trong thư mục `Web/` đã có sẵn file `config.json`. Mở file này để chỉnh sửa đường dẫn và thông tin CSDL theo máy của bạn:
```json
{
  "audio_dir": "D:/path/to/your/1000_audio_files",
  "pg_host": "localhost",
  "pg_port": 5432,
  "pg_user": "postgres",
  "pg_password": "your_postgres_password",
  "pg_database": "voice_multimedia_db"
}
```
* **`audio_dir`**: Đường dẫn tới thư mục chứa 1,000 file âm thanh `.wav` trên máy tính đó.
* **`pg_password`**: Mật khẩu tài khoản PostgreSQL trên máy tính đó (mặc định: `123456`).

### Bước 4: Phục hồi Cơ sở dữ liệu PostgreSQL (Chỉ làm 1 lần)
Chạy script phục hồi tự động có sẵn trong thư mục `database/`:
```bash
python database/setup_postgres_database.py
```
*(Script sẽ tự động đọc cấu hình tài khoản từ `config.json`, tạo database `voice_multimedia_db` và nạp toàn bộ 1,000 files, các bảng đặc trưng 29D, vector 192D cùng hàm Cosine Similarity).*

### Bước 5: Khởi động Web Server
Chạy lệnh:
```bash
python app.py
```
*(Hoặc trên Windows chỉ cần nhấp đúp vào file `start.bat`). Hệ thống sẽ tự động nạp đường dẫn âm thanh và kết nối CSDL từ `config.json`.*

### Bước 6: Trải nghiệm
Mở trình duyệt Web tại: **`http://localhost:5000`**

---

## 4. Các Tính Năng Đã Hoàn Thiện

1. **Tìm kiếm âm thanh tương đồng (Query-by-Example):**
   * Kéo thả hoặc duyệt tệp âm thanh đầu vào (`.wav`, `.mp3`).
   * Thử nghiệm nhanh 1-click bằng các tệp âm thanh mẫu có sẵn trong kho.
   * Lọc nâng cao: Giới hạn Top K (3, 5, 10), Lọc theo dải cao độ F0 (Hz).
   * Hiển thị bảng xếp hạng Top 5 kèm huy hiệu thứ hạng, điểm tương đồng Cosine, khoảng cách Euclid, so sánh độ lệch cao độ và lời giải thích tự nhiên.
   * Trình phát âm thanh (Audio Player) tích hợp sẵn cho phép nghe ngay lập tức file gốc và các file kết quả để so sánh đối chiếu.
   * Biểu đồ cột (Chart.js) trực quan hóa so sánh $F0$ và Trọng tâm phổ giữa Query và Top 5.

2. **Khám phá Cơ sở dữ liệu (Database Explorer):**
   * Duyệt toàn bộ 1,000 files trong PostgreSQL.
   * Tìm kiếm tức thời theo tên file, phân trang mượt mà.
   * Nghe thử trực tiếp bất kỳ tệp nào trong kho CSDL.

3. **Thống kê & Phân tích (Analytics):**
   * Biểu đồ phân bố cao độ $F0$ của 1,000 giọng nữ.
   * Biểu đồ phân bố thời lượng ghi âm.
   * Báo cáo dung lượng và trạng thái CSDL PostgreSQL.

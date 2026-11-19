# Voice Retrieval Web Application (MMDBMS)

Ứng dụng Web hoàn chỉnh phục vụ lưu trữ và tìm kiếm giọng nói phụ nữ theo nội dung (Query-by-Example).
Đề tài Bài tập lớn môn **Hệ Cơ Sở Dữ Liệu Đa Phương Tiện (MMDBMS)** - Học viện Công nghệ Bưu chính Viễn thông (PTIT).

---

## 1. Kiến trúc Hệ thống

Ứng dụng được thiết kế theo mô hình Full-stack phân tầng:
* **Backend:** Flask REST API kết nối trực tiếp với Hệ quản trị CSDL **PostgreSQL 18** và mô hình học sâu **ECAPA-TDNN** (`speechbrain/spkrec-ecapa-voxceleb`) + **Librosa**.
* **Frontend:** Single Page Application (SPA) xây dựng trên nền **Tailwind CSS**, **Chart.js** và **HTML5 Web Audio API / MediaRecorder**.
* **Database Engine:** PostgreSQL 18 quản trị 1,000 files giọng nữ, mảng vector nhúng `REAL[192]` và thực thi trực tiếp hàm `cosine_similarity_192()` trong nhân CSDL.

---

## 2. Các Tính Năng Chính

1. **Tìm kiếm âm thanh tương đồng (Query-by-Example):**
   * Kéo thả hoặc duyệt tệp âm thanh đầu vào (`.wav`, `.mp3`, `.m4a`).
   * Thử nghiệm nhanh 1-click bằng các tệp âm thanh mẫu có sẵn trong kho.
   * Lọc nâng cao: Giới hạn Top K (3, 5, 10), Lọc theo dải cao độ F0 (Hz).
   * Hiển thị bảng xếp hạng Top 5 kèm huy hiệu thứ hạng, điểm tương đồng Cosine, khoảng cách Euclid, so sánh độ lệch cao độ và lời giải thích tự nhiên.
   * Trình phát âm thanh (Audio Player) tích hợp sẵn cho phép nghe ngay lập tức file gốc và 5 file kết quả để so sánh đối chiếu.
   * Biểu đồ cột (Chart.js) trực quan hóa so sánh $F0$ và Trọng tâm phổ giữa Query và Top 5.

2. **Khám phá Cơ sở dữ liệu (Database Explorer):**
   * Duyệt toàn bộ 1,000 files trong PostgreSQL.
   * Tìm kiếm tức thời theo tên file, phân trang mượt mà.
   * Nghe thử trực tiếp bất kỳ tệp nào trong kho CSDL.

3. **Thống kê & Phân tích (Analytics):**
   * Biểu đồ phân bố cao độ $F0$ của 1,000 giọng nữ.
   * Biểu đồ phân bố thời lượng ghi âm.
   * Báo cáo dung lượng và trạng thái CSDL PostgreSQL.

---

## 3. Cài đặt và Khởi chạy

### Bước 1: Kích hoạt môi trường Python 3.12
Đảm bảo bạn đang sử dụng Python 3.12 (đã cài đặt `flask`, `flask-cors`, `psycopg2`, `librosa`, `torch`, `speechbrain`).

### Bước 2: Chạy ứng dụng
Mở Terminal tại thư mục `Web/` và gõ:
```bash
python app.py
```
*(Hoặc click đúp chuột vào file `start.bat` trên Windows).*

### Bước 3: Mở trình duyệt
Truy cập địa chỉ: **`http://localhost:5000`**

---

## 4. Cấu trúc Thư mục

```text
Web/
├── .gitignore               # Cấu hình bỏ qua tệp tạm và uploads
├── README.md                # Tài liệu hướng dẫn
├── requirements.txt         # Danh mục thư viện phụ thuộc
├── start.bat                # Script khởi động 1-click trên Windows
├── app.py                   # Flask Backend API Server
├── templates/
│   └── index.html           # Giao diện chính Single Page Application
├── static/
│   ├── css/
│   │   └── style.css        # Giao diện Dark mode, hiệu ứng Glassmorphism
│   └── js/
│       └── app.js           # Xử lý logic AJAX, Audio Recorder, Charts
└── uploads/                 # Thư mục chứa các tệp âm thanh người dùng tải lên
```

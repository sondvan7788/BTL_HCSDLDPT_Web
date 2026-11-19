# -*- coding: utf-8 -*-
"""
Web App Backend - Voice Retrieval System (Flask Server)
======================================================
Cung cấp REST API cho hệ thống tìm kiếm giọng nói phụ nữ:
- Tìm kiếm theo file upload hoặc ghi âm trực tiếp
- Tìm kiếm nhanh bằng file mẫu có sẵn trong kho
- Stream file âm thanh WAV trực tiếp cho trình phát web
- Thống kê phân tích CSDL PostgreSQL
"""
import os
import sys
import time
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

# Thiết lập đường dẫn tới thư mục gốc và thư mục DacTrung
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
DACTRUNG_DIR = PROJECT_ROOT / "DacTrung"
AUDIO_DIR = PROJECT_ROOT / "ChuanHoa"
UPLOAD_DIR = CURRENT_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

for p in [str(PROJECT_ROOT), str(DACTRUNG_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from postgres_db_manager import PostgresDatabaseManager
from search_engine import VoiceSearchEngine

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Khởi tạo Database Manager và Search Engine
print("="*60)
print("Đang khởi động Voice Retrieval Web App Backend...")
db_manager = PostgresDatabaseManager()
search_engine = VoiceSearchEngine(db_manager=db_manager)
print("-> Backend đã kết nối thành công tới PostgreSQL 18!")
print("="*60)

@app.route("/")
def index():
    """Trang chủ ứng dụng Web."""
    return render_template("index.html")

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Lấy số liệu thống kê tổng quan của cơ sở dữ liệu."""
    try:
        stats = db_manager.get_database_stats()
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/samples", methods=["GET"])
def get_samples():
    """Lấy danh sách 12 file mẫu từ kho dữ liệu để người dùng thử nghiệm nhanh."""
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                SELECT a.file_id, a.file_name, a.duration_s, f.pitch_f0_mean, f.spectral_centroid_mean
                FROM audio_files a
                JOIN acoustic_features_29d f ON a.file_id = f.file_id
                ORDER BY a.file_id ASC
                LIMIT 12;
                """)
                rows = cur.fetchall()
        
        samples = []
        for r in rows:
            samples.append({
                "file_id": r["file_id"],
                "file_name": r["file_name"],
                "duration_s": round(r["duration_s"], 2),
                "pitch_f0_mean": round(r["pitch_f0_mean"], 1),
                "spectral_centroid_mean": round(r["spectral_centroid_mean"], 1),
                "audio_url": f"/api/audio/{r['file_name']}"
            })
        return jsonify({"success": True, "samples": samples})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/search", methods=["POST"])
def search_audio():
    """
    API tìm kiếm giọng nói tương đồng (Query-by-Example).
    Chấp nhận:
    1. Upload file âm thanh (multipart/form-data: file)
    2. Hoặc chọn 1 file mẫu có sẵn (JSON / Form-data: sample_name)
    """
    try:
        top_k = int(request.form.get("top_k", 5))
        f0_min = request.form.get("f0_min", None)
        f0_max = request.form.get("f0_max", None)
        f0_filter = None
        if f0_min and f0_max:
            f0_filter = (float(f0_min), float(f0_max))

        temp_audio_path = None
        is_uploaded = False

        # Trường hợp 1: Người dùng upload file mới hoặc gửi audio từ micro
        if "file" in request.files and request.files["file"].filename != "":
            audio_file = request.files["file"]
            ext = Path(audio_file.filename).suffix or ".wav"
            unique_name = f"query_{uuid.uuid4().hex[:8]}{ext}"
            temp_audio_path = UPLOAD_DIR / unique_name
            audio_file.save(str(temp_audio_path))
            is_uploaded = True
            query_audio_url = f"/api/audio/upload/{unique_name}"

        # Trường hợp 2: Người dùng chọn 1 file mẫu có sẵn trong kho
        elif "sample_name" in request.form and request.form["sample_name"]:
            sample_name = request.form["sample_name"].strip()
            temp_audio_path = AUDIO_DIR / sample_name
            if not temp_audio_path.exists():
                return jsonify({"success": False, "error": f"Không tìm thấy file mẫu: {sample_name}"}), 404
            query_audio_url = f"/api/audio/{sample_name}"
        else:
            return jsonify({"success": False, "error": "Vui lòng tải lên file âm thanh hoặc chọn file mẫu!"}), 400

        # Thực thi tìm kiếm bằng VoiceSearchEngine
        search_result = search_engine.search(temp_audio_path, top_k=top_k, f0_filter=f0_filter)
        
        # Bổ sung link nghe âm thanh cho query và kết quả
        search_result["query_info"]["audio_url"] = query_audio_url
        for r in search_result["top_results"]:
            r["audio_url"] = f"/api/audio/{r['file_name']}"

        return jsonify({"success": True, "data": search_result})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/audio/<filename>", methods=["GET"])
def stream_dataset_audio(filename):
    """Phát file âm thanh từ kho dữ liệu ChuanHoa/."""
    return send_from_directory(str(AUDIO_DIR), filename, mimetype="audio/wav")

@app.route("/api/audio/upload/<filename>", methods=["GET"])
def stream_upload_audio(filename):
    """Phát file âm thanh do người dùng vừa tải lên."""
    return send_from_directory(str(UPLOAD_DIR), filename)

@app.route("/api/database/list", methods=["GET"])
def list_database():
    """Phân trang danh sách 1,000 files trong PostgreSQL."""
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 20))
        offset = (page - 1) * limit
        search = request.args.get("search", "").strip()

        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                where_clause = ""
                params = []
                if search:
                    where_clause = "WHERE a.file_name ILIKE %s"
                    params.append(f"%{search}%")

                cur.execute(f"SELECT COUNT(*) FROM audio_files a {where_clause};", tuple(params))
                total = cur.fetchone()["count"]

                query = f"""
                SELECT a.file_id, a.file_name, a.duration_s, a.voiced_pct,
                       f.pitch_f0_mean, f.spectral_centroid_mean, f.zero_crossing_rate_mean
                FROM audio_files a
                JOIN acoustic_features_29d f ON a.file_id = f.file_id
                {where_clause}
                ORDER BY a.file_id ASC
                LIMIT %s OFFSET %s;
                """
                params.extend([limit, offset])
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        items = []
        for r in rows:
            items.append({
                "file_id": r["file_id"],
                "file_name": r["file_name"],
                "duration_s": round(r["duration_s"], 2),
                "voiced_pct": round(r["voiced_pct"], 2),
                "pitch_f0_mean": round(r["pitch_f0_mean"], 2),
                "spectral_centroid_mean": round(r["spectral_centroid_mean"], 1),
                "audio_url": f"/api/audio/{r['file_name']}"
            })

        return jsonify({
            "success": True,
            "total": total,
            "page": page,
            "limit": limit,
            "items": items
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/database/chart_data", methods=["GET"])
def get_chart_data():
    """Lấy dữ liệu biểu đồ phân bố cho tab Thống kê."""
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pitch_f0_mean, spectral_centroid_mean, duration_s FROM audio_files a JOIN acoustic_features_29d f ON a.file_id = f.file_id;")
                rows = cur.fetchall()

        f0_vals = [r["pitch_f0_mean"] for r in rows]
        dur_vals = [r["duration_s"] for r in rows]

        return jsonify({
            "success": True,
            "f0_distribution": {
                "bins": ["100-150", "150-180", "180-210", "210-240", "240-270", "270-350"],
                "counts": [
                    len([x for x in f0_vals if 100 <= x < 150]),
                    len([x for x in f0_vals if 150 <= x < 180]),
                    len([x for x in f0_vals if 180 <= x < 210]),
                    len([x for x in f0_vals if 210 <= x < 240]),
                    len([x for x in f0_vals if 240 <= x < 270]),
                    len([x for x in f0_vals if 270 <= x <= 350])
                ]
            },
            "duration_distribution": {
                "bins": ["5.0-6.0s", "6.0-7.0s", "7.0-8.0s", "8.0-10.0s", ">10.0s"],
                "counts": [
                    len([x for x in dur_vals if 5.0 <= x < 6.0]),
                    len([x for x in dur_vals if 6.0 <= x < 7.0]),
                    len([x for x in dur_vals if 7.0 <= x < 8.0]),
                    len([x for x in dur_vals if 8.0 <= x < 10.0]),
                    len([x for x in dur_vals if x >= 10.0])
                ]
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n-> Web Server khởi chạy tại: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

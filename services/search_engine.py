# -*- coding: utf-8 -*-
"""
search_engine.py
================
Hệ thống Tìm kiếm Giọng nói Tương đồng (Content-Based Audio Retrieval - CBAR)
Hiện thực hóa trọn vẹn Phần 4 theo kiến trúc Phối hợp 2 Pha (Two-phase Hybrid Matching):
- Đầu vào: 1 file âm thanh bất kỳ (.wav, .mp3) của giọng nữ (đã có hoặc chưa có trong CSDL).
- Đầu ra: Top 5 files âm thanh có giọng nói tương đồng nhất, xếp theo thứ tự giảm dần,
  kèm theo toàn bộ giá trị đặc trưng trung gian và phân tích đối chiếu âm học vật lý.
"""
import time
import sys
from pathlib import Path
import numpy as np

# Đảm bảo đường dẫn module luôn nhận diện được database và services
CURRENT_DIR = Path(__file__).resolve().parent
WEB_ROOT = CURRENT_DIR.parent
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

try:
    from database.postgres_db_manager import PostgresDatabaseManager
    from services.feature_extractor import FeatureExtractor
except ImportError:
    from postgres_db_manager import PostgresDatabaseManager
    from feature_extractor import FeatureExtractor

class VoiceSearchEngine:
    def __init__(self, db_manager=None, extractor=None):
        self.db = db_manager if db_manager is not None else PostgresDatabaseManager()
        self.extractor = extractor if extractor is not None else FeatureExtractor()
        
        # Nạp trước tham số chuẩn hóa (mu, sigma) từ PostgreSQL để tối ưu tốc độ
        print("Đang khởi tạo VoiceSearchEngine & nạp cấu hình từ PostgreSQL...")
        self.feature_names, self.mu, self.sigma = self.db.get_scaler_params()
        print("-> VoiceSearchEngine đã sẵn sàng phục vụ tìm kiếm!")

    def search(self, query_audio_path, top_k=5, f0_filter=None):
        """
        Thực hiện tìm kiếm Top-K giọng nói tương đồng nhất cho 1 file audio truy vấn.
        
        Tham số:
            query_audio_path : đường dẫn tệp âm thanh truy vấn (.wav, .mp3)
            top_k            : số lượng kết quả trả về (mặc định 5)
            f0_filter        : tuple (f0_min, f0_max) để lọc theo dải cao độ nếu muốn
            
        Trả về:
            dict chứa:
            - query_info   : metadata và các vector trung gian của file query
            - top_results  : danh sách Top K kết quả kèm độ đo Cosine và Euclid
            - latency      : thời gian thực thi từng giai đoạn (mili-giây)
        """
        t_total_start = time.time()
        query_path = Path(query_audio_path)
        if not query_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file truy vấn tại: {query_path}")

        # ====================================================================
        # BƯỚC 1 & 2: TIỀN XỬ LÝ & TRÍCH XUẤT ĐẶC TRƯNG TRỰC TUYẾN (ONLINE)
        # ====================================================================
        t_extract_start = time.time()
        extract_res = self.extractor.extract_file(
            audio_path=query_path,
            scaler_mu=self.mu,
            scaler_sigma=self.sigma
        )
        t_extract = (time.time() - t_extract_start) * 1000  # ms

        query_meta = extract_res["metadata"]
        raw_29d = extract_res["raw_29d"]
        z_29d = extract_res["z_29d"]
        emb_192d = extract_res["emb_192d"]

        # ====================================================================
        # BƯỚC 3 (PHA 1): TÌM KIẾM & XẾP HẠNG SINH TRẮC HỌC SÂU TRÊN POSTGRESQL
        # ====================================================================
        t_sql_start = time.time()
        if f0_filter is not None:
            f0_min, f0_max = f0_filter
            candidates = self.db.search_hybrid(emb_192d, f0_min=f0_min, f0_max=f0_max, k=top_k)
        else:
            candidates = self.db.search_top_k(emb_192d, k=top_k)
        t_sql = (time.time() - t_sql_start) * 1000  # ms

        # ====================================================================
        # BƯỚC 4 (PHA 2): ĐỐI CHIẾU THUỘC TÍNH ÂM HỌC VẬT LÝ & GIẢI THÍCH (29D)
        # ====================================================================
        top_results = []
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                for rank, cand in enumerate(candidates, 1):
                    file_id = cand["file_id"]
                    
                    # Lấy vector Z-Score 29D của ứng viên từ PostgreSQL để tính khoảng cách Euclid
                    cur.execute("SELECT * FROM acoustic_features_zscore_29d WHERE file_id = %s;", (file_id,))
                    z_row = cur.fetchone()
                    cand_z29 = np.array([z_row[k] for k in z_row.keys() if k.startswith("z_")], dtype=np.float32)

                    # Khoảng cách Euclid trên 29 thuộc tính Z-Score
                    d_euclid = float(np.linalg.norm(z_29d - cand_z29))
                    sim_acoustic = float(1.0 / (1.0 + d_euclid))

                    # Độ chênh lệch các thuộc tính âm học vật lý chính
                    delta_f0 = float(cand["pitch_f0_mean"] - query_meta["f0_mean"])
                    delta_centroid = float(cand["spectral_centroid_mean"] - query_meta["spectral_centroid"])

                    # Phân tích mức độ tương đồng
                    cos_sim = float(cand["similarity"])
                    if cos_sim >= 0.999:
                        explanation = "Trùng khớp danh tính tuyệt đối (Chính tệp âm thanh gốc)."
                    elif cos_sim >= 0.70:
                        explanation = f"Độ tương đồng sinh trắc học rất cao. Cao độ F0 lệch {abs(delta_f0):.1f} Hz."
                    elif cos_sim >= 0.60:
                        explanation = f"Tương đồng âm sắc tốt. Cao độ F0 lệch {abs(delta_f0):.1f} Hz, trọng tâm phổ lệch {abs(delta_centroid):.1f} Hz."
                    else:
                        explanation = f"Độ tương đồng mức trung bình khá (dải F0 tương thích)."

                    top_results.append({
                        "rank": rank,
                        "file_id": cand["file_id"],
                        "file_name": cand["file_name"],
                        "file_path": cand["file_path"],
                        "duration_s": round(cand["duration_s"], 2),
                        "voiced_pct": round(cand["voiced_pct"], 2),
                        "cosine_similarity": round(cos_sim, 4),
                        "similarity_score_pct": round(cos_sim * 100.0, 2),
                        "euclidean_distance_29d": round(d_euclid, 4),
                        "acoustic_similarity": round(sim_acoustic, 4),
                        "pitch_f0_mean": round(cand["pitch_f0_mean"], 1),
                        "spectral_centroid_mean": round(cand["spectral_centroid_mean"], 1),
                        "delta_f0_hz": round(delta_f0, 1),
                        "delta_centroid_hz": round(delta_centroid, 1),
                        "explanation": explanation
                    })

        t_total = (time.time() - t_total_start) * 1000  # ms

        return {
            "query_info": {
                "file_name": query_path.name,
                "duration_s": round(query_meta["duration_s"], 2),
                "voiced_pct": round(query_meta["voiced_pct"], 2),
                "f0_mean": round(query_meta["f0_mean"], 1),
                "spectral_centroid": round(query_meta["spectral_centroid"], 1),
                "raw_29d": [round(float(v), 4) for v in raw_29d],
                "z_29d": [round(float(v), 4) for v in z_29d],
                "emb_192d_preview": [round(float(v), 4) for v in emb_192d[:10]], # 10 chiều đầu
                "feature_names": self.feature_names
            },
            "top_results": top_results,
            "latency": {
                "extract_online_ms": round(t_extract, 2),
                "sql_retrieval_ms": round(t_sql, 2),
                "total_pipeline_ms": round(t_total, 2)
            }
        }

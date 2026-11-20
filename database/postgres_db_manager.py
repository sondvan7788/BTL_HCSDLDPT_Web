# -*- coding: utf-8 -*-
"""
postgres_db_manager.py
======================
Lớp Quản trị CSDL PostgreSQL (Data Access Object - DAO)
Cung cấp các API truy vấn, trích xuất dữ liệu và tìm kiếm tương đồng Top-K thuần SQL
trực tiếp trong PostgreSQL Database Engine.
"""
import os
import json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np

class PostgresDatabaseManager:
    def __init__(self, host=None, port=None, user=None, password=None, dbname=None):
        # Đọc cấu hình từ config.json nếu có
        cfg = {}
        config_path = Path(__file__).resolve().parent.parent / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass

        self.conn_params = {
            "host": host or cfg.get("pg_host") or os.environ.get("PGHOST", "localhost"),
            "port": int(port or cfg.get("pg_port") or os.environ.get("PGPORT", 5432)),
            "user": user or cfg.get("pg_user") or os.environ.get("PGUSER", "postgres"),
            "password": password or cfg.get("pg_password") or os.environ.get("PGPASSWORD", "123456"),
            "dbname": dbname or cfg.get("pg_database") or os.environ.get("PGDATABASE", "voice_multimedia_db")
        }

    def get_connection(self):
        """Khởi tạo kết nối tới PostgreSQL với con trỏ trả về Dictionary."""
        return psycopg2.connect(**self.conn_params, cursor_factory=RealDictCursor)

    def get_database_stats(self):
        """Thống kê tổng quan cơ sở dữ liệu trên PostgreSQL."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total FROM audio_files;")
                num_files = cur.fetchone()["total"]

                cur.execute("SELECT AVG(duration_s) AS avg_d, MIN(duration_s) AS min_d, MAX(duration_s) AS max_d FROM audio_files;")
                d_row = cur.fetchone()

                cur.execute("SELECT AVG(pitch_f0_mean) AS avg_f, MIN(pitch_f0_mean) AS min_f, MAX(pitch_f0_mean) AS max_f FROM acoustic_features_29d;")
                f_row = cur.fetchone()

                cur.execute("SELECT pg_size_pretty(pg_database_size('voice_multimedia_db')) AS db_size;")
                db_size = cur.fetchone()["db_size"]

        return {
            "engine": "PostgreSQL 18",
            "database_name": self.conn_params["dbname"],
            "num_files": num_files,
            "duration": {"avg": round(d_row["avg_d"], 2), "min": round(d_row["min_d"], 2), "max": round(d_row["max_d"], 2)},
            "pitch_f0": {"avg": round(f_row["avg_f"], 2), "min": round(f_row["min_f"], 2), "max": round(f_row["max_f"], 2)},
            "database_size": db_size
        }

    def get_scaler_params(self):
        """Lấy bộ tham số mu và sigma để chuẩn hóa vector truy vấn mới."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT feature_name, mean_val, std_val FROM scaler_params;")
                rows = cur.fetchall()

        feature_names = [r["feature_name"] for r in rows]
        mu = np.array([r["mean_val"] for r in rows], dtype=np.float32)
        sigma = np.array([r["std_val"] for r in rows], dtype=np.float32)
        return feature_names, mu, sigma

    def search_top_k(self, query_emb, k=5):
        """
        Thực hiện tìm kiếm Top-K giọng nói tương đồng nhất THUẦN SQL trong PostgreSQL.
        Độ phức tạp được xử lý trực tiếp bởi Database Engine.
        """
        emb_list = [float(x) for x in query_emb]

        query_sql = """
        SELECT a.file_id, a.file_name, a.file_path, a.duration_s, a.voiced_pct,
               f.pitch_f0_mean, f.spectral_centroid_mean,
               cosine_similarity_192(e.embedding_array, %s) AS similarity
        FROM audio_files a
        JOIN acoustic_features_29d f ON a.file_id = f.file_id
        JOIN ecapa_features_192d e ON a.file_id = e.file_id
        ORDER BY similarity DESC
        LIMIT %s;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_sql, (emb_list, k))
                results = cur.fetchall()

        return [dict(r) for r in results]

    def search_hybrid(self, query_emb, f0_min=None, f0_max=None, k=5):
        """
        Truy vấn kết hợp (Hybrid Query): Lọc theo phạm vi đặc tính vật lý âm học (B-Tree Index)
        kết hợp xếp hạng tương đồng sinh trắc học sâu (Cosine Similarity).
        """
        emb_list = [float(x) for x in query_emb]
        clauses = []
        params = [emb_list]

        if f0_min is not None:
            clauses.append("f.pitch_f0_mean >= %s")
            params.append(f0_min)
        if f0_max is not None:
            clauses.append("f.pitch_f0_mean <= %s")
            params.append(f0_max)

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(k)

        query_sql = f"""
        SELECT a.file_id, a.file_name, a.duration_s,
               f.pitch_f0_mean, f.spectral_centroid_mean,
               cosine_similarity_192(e.embedding_array, %s) AS similarity
        FROM audio_files a
        JOIN acoustic_features_29d f ON a.file_id = f.file_id
        JOIN ecapa_features_192d e ON a.file_id = e.file_id
        {where_sql}
        ORDER BY similarity DESC
        LIMIT %s;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_sql, tuple(params))
                results = cur.fetchall()

        return [dict(r) for r in results]

    def get_audio_detail(self, file_name_or_id):
        """Lấy toàn bộ thông tin chi tiết một file âm thanh."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if isinstance(file_name_or_id, int):
                    cond = "a.file_id = %s"
                else:
                    cond = "a.file_name = %s"

                query = f"""
                SELECT a.*, f.*, e.embedding_array
                FROM audio_files a
                JOIN acoustic_features_29d f ON a.file_id = f.file_id
                JOIN ecapa_features_192d e ON a.file_id = e.file_id
                WHERE {cond};
                """
                cur.execute(query, (file_name_or_id,))
                row = cur.fetchone()
                return dict(row) if row else None

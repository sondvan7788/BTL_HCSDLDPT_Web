# -*- coding: utf-8 -*-
"""
setup_postgres_database.py
==========================
Khởi tạo và Phục hồi Hệ Cơ sở Dữ liệu Đa phương tiện PostgreSQL (voice_multimedia_db)
Hỗ trợ phục hồi nhanh 1-Click từ file backup `voice_multimedia_db_backup.sql`
hoặc khởi tạo mới hoàn toàn trên máy mới.
"""
import os
import sys
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path

# Cấu hình kết nối PostgreSQL
PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "postgres"
PG_PASS = "123456"
DB_NAME = "voice_multimedia_db"

CURRENT_DIR = Path(__file__).resolve().parent
BACKUP_SQL_PATH = CURRENT_DIR / "voice_multimedia_db_backup.sql"

def create_database_if_not_exists():
    """Tạo database mới nếu chưa tồn tại trên PostgreSQL server."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}';")
        exists = cur.fetchone()
        if not exists:
            print(f"[*] Đang tạo cơ sở dữ liệu '{DB_NAME}' trên PostgreSQL...")
            cur.execute(f"CREATE DATABASE {DB_NAME};")
            print(f"[+] Đã tạo thành công database '{DB_NAME}'!")
        else:
            print(f"[*] Database '{DB_NAME}' đã tồn tại sẵn trên PostgreSQL.")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[-] Lỗi khi kết nối hoặc tạo database: {e}")
        return False

def restore_backup():
    """Phục hồi toàn bộ CSDL từ file SQL backup."""
    if not BACKUP_SQL_PATH.exists():
        print(f"[-] Không tìm thấy file backup tại: {BACKUP_SQL_PATH}")
        return False

    print(f"[*] Đang nạp dữ liệu từ: {BACKUP_SQL_PATH.name}...")
    
    # Cách 1: Sử dụng psql CLI nếu có
    cmd = f'psql -h {PG_HOST} -p {PG_PORT} -U {PG_USER} -d {DB_NAME} -f "{BACKUP_SQL_PATH}"'
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASS

    try:
        res = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)
        if res.returncode == 0 or "CREATE TABLE" in res.stderr or "INSERT" in res.stdout:
            print("[+] Phục hồi dữ liệu qua psql CLI thành công!")
            return True
    except Exception:
        pass

    # Cách 2: Thực thi trực tiếp qua psycopg2
    try:
        print("[*] Đang thực thi nạp SQL qua psycopg2...")
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=DB_NAME
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        with open(BACKUP_SQL_PATH, "r", encoding="utf-8") as f:
            sql_content = f.read()

        cur.execute(sql_content)
        cur.close()
        conn.close()
        print("[+] Phục hồi dữ liệu qua psycopg2 hoàn tất thành công!")
        return True
    except Exception as e:
        print(f"[-] Lỗi khi phục hồi SQL: {e}")
        return False

def verify_database():
    """Kiểm tra số lượng bản ghi sau khi phục hồi."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=DB_NAME
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audio_files;")
        count_files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM acoustic_features_29d;")
        count_29d = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ecapa_features_192d;")
        count_192d = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM scaler_params;")
        count_scaler = cur.fetchone()[0]
        cur.close()
        conn.close()

        print("="*60)
        print("KẾT QUẢ KIỂM TRA CSDL (VOICE_MULTIMEDIA_DB):")
        print(f"  - audio_files:                {count_files} bản ghi")
        print(f"  - acoustic_features_29d:      {count_29d} bản ghi")
        print(f"  - ecapa_features_192d:        {count_192d} bản ghi")
        print(f"  - scaler_params:              {count_scaler} tham số")
        print("="*60)
        if count_files >= 1000 and count_scaler >= 29:
            print("[SUCCESS] CSDL đã được thiết lập đầy đủ và sẵn sàng 100%!")
            return True
        else:
            print("[WARNING] CSDL có thể chưa đủ 1,000 file hoặc thiếu tham số scaler.")
            return False
    except Exception as e:
        print(f"[-] Lỗi kiểm tra database: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("THIẾT LẬP VÀ PHỤC HỒI POSTGRESQL DATABASE CHO WEB APP")
    print("="*60)
    create_database_if_not_exists()
    restore_backup()
    verify_database()

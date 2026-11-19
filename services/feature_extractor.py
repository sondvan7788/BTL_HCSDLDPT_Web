# -*- coding: utf-8 -*-
"""
feature_extractor.py
====================
Module trích xuất đặc trưng âm thanh độc lập (Hỗ trợ Online & Offline)
Dùng để trích xuất 2 bộ đặc trưng (29 chiều âm học & 192 chiều ECAPA-TDNN)
cho bất kỳ file âm thanh nào được đưa vào hệ thống (Query-by-Example).
"""
import os
import sys
from pathlib import Path
import numpy as np
import librosa
import torch
import torch.nn.functional as F

# Cấu hình tham số trích xuất âm học (chuẩn đồng bộ với toàn hệ thống)
SR = 16000
N_FFT = 512
FRAME_LEN = 400       # 25 ms
HOP = 160             # 10 ms
N_MELS = 40
N_MFCC = 12
USE_PREEMPHASIS = True
PREEMPH = 0.97
F0_MIN, F0_MAX = 75.0, 500.0
YIN_FRAME = 1024
ROLLOFF_PCT = 0.85

FEATURE_NAMES = (
    [f"mfcc_mean_{i}" for i in range(1, N_MFCC + 1)]
    + [f"mfcc_std_{i}" for i in range(1, N_MFCC + 1)]
    + ["pitch_f0_mean", "pitch_f0_std", "spectral_centroid_mean",
       "spectral_rolloff_mean", "zero_crossing_rate_mean"]
)

class FeatureExtractor:
    def __init__(self, ecapa_model_dir=None, device="cpu"):
        self.device = device
        self.ecapa_model = None
        
        # Xác định đường dẫn thư mục checkpoint ECAPA-TDNN
        current_dir = Path(__file__).resolve().parent
        web_root = current_dir.parent
        project_root = web_root.parent
        
        if ecapa_model_dir is None:
            candidates = [
                web_root / "pretrained_models" / "spkrec-ecapa-voxceleb",
                project_root / "pretrained_models" / "spkrec-ecapa-voxceleb",
                Path("pretrained_models/spkrec-ecapa-voxceleb")
            ]
            for c in candidates:
                if (c / "embedding_model.ckpt").exists():
                    self.ecapa_model_dir = c
                    break
            else:
                # Nếu chưa có sẵn checkpoint local, SpeechBrain sẽ tự tải về thư mục này
                self.ecapa_model_dir = web_root / "pretrained_models" / "spkrec-ecapa-voxceleb"
        else:
            self.ecapa_model_dir = Path(ecapa_model_dir)

    def _init_ecapa_model(self):
        """Khởi tạo và nạp mô hình ECAPA-TDNN vào bộ nhớ (chỉ nạp 1 lần duy nhất)."""
        if self.ecapa_model is not None:
            return

        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError:
            from speechbrain.pretrained import EncoderClassifier

        savedir_str = str(self.ecapa_model_dir).replace("\\", "/")
        kwargs = dict(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=savedir_str,
            run_opts={"device": self.device},
        )
        try:
            from speechbrain.utils.fetching import LocalStrategy
            self.ecapa_model = EncoderClassifier.from_hparams(local_strategy=LocalStrategy.COPY, **kwargs)
        except (ImportError, TypeError):
            self.ecapa_model = EncoderClassifier.from_hparams(**kwargs)

    def load_audio(self, audio_path, peak_norm=False):
        """Đọc và chuẩn hóa âm thanh về 16kHz Mono."""
        y, _ = librosa.load(str(audio_path), sr=SR, mono=True)
        if peak_norm:
            p = np.max(np.abs(y))
            if p > 0:
                y = y / p
        return y

    def extract_29d(self, y, default_f0_mean=197.6, default_f0_std=25.0):
        """
        Trích xuất 29 chiều đặc trưng âm học vật lý từ tín hiệu âm thanh 16kHz.
        """
        # 1. MFCCs: 12 hệ số mean + 12 hệ số std (bỏ c0)
        y_mfcc = librosa.effects.preemphasis(y, coef=PREEMPH) if USE_PREEMPHASIS else y
        mfcc = librosa.feature.mfcc(
            y=y_mfcc, sr=SR, n_mfcc=N_MFCC + 1, n_fft=N_FFT, hop_length=HOP,
            win_length=FRAME_LEN, window="hamming", n_mels=N_MELS, htk=True,
        )[1:N_MFCC + 1]
        mfcc_mean = mfcc.mean(axis=1)
        mfcc_std = mfcc.std(axis=1)

        # 2. F0 bằng pYIN
        f0, voiced_flag, _ = librosa.pyin(
            y, fmin=F0_MIN, fmax=F0_MAX, sr=SR, frame_length=YIN_FRAME, hop_length=HOP,
        )
        voiced = voiced_flag & ~np.isnan(f0)
        if voiced.any():
            f0_mean, f0_std = float(f0[voiced].mean()), float(f0[voiced].std())
        else:
            # Khung vô thanh hoàn toàn: dùng giá trị mặc định của CSDL
            f0_mean, f0_std = default_f0_mean, default_f0_std

        # 3. Spectral Centroid, Rolloff, ZCR
        centroid = librosa.feature.spectral_centroid(
            y=y, sr=SR, n_fft=N_FFT, hop_length=HOP, win_length=FRAME_LEN, window="hamming")[0]
        rolloff = librosa.feature.spectral_rolloff(
            y=y, sr=SR, n_fft=N_FFT, hop_length=HOP, win_length=FRAME_LEN, window="hamming",
            roll_percent=ROLLOFF_PCT)[0]
        zcr = librosa.feature.zero_crossing_rate(
            y, frame_length=FRAME_LEN, hop_length=HOP)[0]

        vec_29d = np.concatenate([
            mfcc_mean, mfcc_std,
            [f0_mean, f0_std, centroid.mean(), rolloff.mean(), zcr.mean()],
        ]).astype(np.float32)

        meta = {
            "duration_s": float(len(y) / SR),
            "voiced_pct": float(100.0 * float(voiced.mean())),
            "sample_rate": SR,
            "f0_mean": f0_mean,
            "spectral_centroid": float(centroid.mean())
        }
        return vec_29d, meta

    def extract_ecapa(self, y):
        """
        Trích xuất vector nhúng sinh trắc học sâu 192 chiều từ ECAPA-TDNN, chuẩn hóa L2.
        """
        self._init_ecapa_model()
        with torch.no_grad():
            sig = torch.from_numpy(y).float().unsqueeze(0)
            if self.device != "cpu":
                sig = sig.to(self.device)
            e = self.ecapa_model.encode_batch(sig).squeeze()
            e = F.normalize(e, p=2, dim=-1) # Chuẩn hóa L2 về siêu mặt cầu đơn vị
            return e.cpu().numpy().astype(np.float32)

    def extract_file(self, audio_path, scaler_mu=None, scaler_sigma=None, peak_norm=False):
        """
        Pipeline trích xuất toàn diện cho 1 file audio:
        - Đọc audio 16kHz
        - Trích xuất 29 chiều thô
        - Tính 29 chiều Z-score (nếu có mu, sigma)
        - Trích xuất 192 chiều ECAPA-TDNN
        """
        y = self.load_audio(audio_path, peak_norm=peak_norm)
        
        # Trích xuất 29D thô
        raw_29d, meta = self.extract_29d(y)

        # Tính Z-score 29D
        z_29d = None
        if scaler_mu is not None and scaler_sigma is not None:
            # Tránh chia cho 0
            safe_sigma = np.where(scaler_sigma == 0, 1.0, scaler_sigma)
            z_29d = ((raw_29d - scaler_mu) / safe_sigma).astype(np.float32)

        # Trích xuất 192D ECAPA-TDNN
        emb_192d = self.extract_ecapa(y)

        return {
            "metadata": meta,
            "raw_29d": raw_29d,
            "z_29d": z_29d,
            "emb_192d": emb_192d,
            "audio_signal": y
        }

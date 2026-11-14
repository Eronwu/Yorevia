"""Optional local YuNet/SFace engine. No network calls, identity lookup, or demographics."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

MODELS = {
    'face_detection_yunet_2023mar.onnx': '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4',
    'face_recognition_sface_2021dec.onnx': '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79',
}


def model_directory() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'models'
    return Path(__file__).resolve().parents[2] / 'models'


def model_status(directory: Path | None = None) -> dict:
    directory = directory or model_directory()
    missing = [name for name in MODELS if not (directory / name).is_file()]
    return {'installed': not missing, 'missing': missing, 'engine': 'YuNet 2023 + SFace 2021 (CPU)',
            'automatic_download': False}


def normalize(vector):
    import numpy as np
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    if not np.isfinite(vector).all() or np.linalg.norm(vector) < 1e-8:
        raise ValueError('无效的人脸特征向量')
    return vector / np.linalg.norm(vector)


def candidate(vector, prototypes: dict, excluded: set | None = None,
              threshold: float = 0.52, margin: float = 0.06) -> str | None:
    """Conservative heuristic, not a calibrated probability or biometric guarantee."""
    import numpy as np
    excluded = excluded or set()
    scored = sorted(((float(np.dot(vector, p)), key) for key, p in prototypes.items()
                     if key not in excluded and len(vector) == len(p)), reverse=True)
    if not scored or scored[0][0] < threshold:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < margin:
        return None
    return scored[0][1]


class FaceEngine:
    def __init__(self, directory: Path | None = None):
        import cv2
        self.directory = directory or model_directory()
        for name, digest in MODELS.items():
            file = self.directory / name
            if not file.is_file():
                raise ValueError('尚未安装本地人像模型。开发版先运行 python scripts/fetch_models.py；应用不会自动联网。')
            if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                raise ValueError('本地模型校验失败，请重新安装官方模型。')
        self.detector = cv2.FaceDetectorYN.create(str(self.directory / list(MODELS)[0]), '', (320, 320), 0.90, 0.30, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(str(self.directory / list(MODELS)[1]), '')
        cv2.setNumThreads(2)

    def detect(self, path: Path) -> list[dict]:
        import cv2
        import numpy as np
        from .media import load_photo
        image = load_photo(path)
        image.thumbnail((1600, 1600))
        bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        height, width = bgr.shape[:2]
        self.detector.setInputSize((width, height))
        _, detections = self.detector.detect(bgr)
        result = []
        if detections is None:
            return result
        for face in detections:
            if min(float(face[2]), float(face[3])) < 24:
                continue
            aligned = self.recognizer.alignCrop(bgr, face)
            vector = normalize(self.recognizer.feature(aligned))
            result.append({'box': json.dumps([float(face[0]/width), float(face[1]/height),
                                               float(face[2]/width), float(face[3]/height)]),
                           'embedding': vector, 'confidence': float(face[-1]),
                           'crop': cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB)})
        return result

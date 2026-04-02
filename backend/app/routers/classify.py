# backend/app/routers/classify.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import tensorflow as tf
import os
import time

router = APIRouter(prefix="/api", tags=["classification"])

# Global model cache
_model_cache = {}

def load_model(model_name: str, feature_set: str):
    key = f"{model_name}_{feature_set}"
    if key not in _model_cache:
        model_path = os.path.join("app", "models", "Results", f"{model_name}_{feature_set}.keras")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        _model_cache[key] = tf.keras.models.load_model(model_path)
        print(f"✅ Loaded: {model_path}")
    return _model_cache[key]

class FrameData(BaseModel):
    angles: Optional[List[float]] = None
    coords: Optional[List[float]] = None

class ClassifyRequest(BaseModel):
    frames: List[FrameData]
    feature_set: str = "angles14"
    model: str = "Bi-LSTM"

class ClassifyResponse(BaseModel):
    move: str
    confidence: float
    move_id: str
    inference_time_ms: float
    all_probabilities: List[float]

@router.post("/classify", response_model=ClassifyResponse)
async def classify_movement(request: ClassifyRequest):
    start_time = time.time()
    
    try:
        if len(request.frames) != 30:
            raise HTTPException(400, f"Exactly 30 frames required, got {len(request.frames)}")
        
        # Your class names from training - UPDATE IF DIFFERENT
        class_names = ["mae_geri", "gyaku_zuki", "gedan_barai"]
        
        if request.feature_set == "angles14":
            X = np.array([frame.angles for frame in request.frames], dtype=np.float32)
            feature_key = "Angles14"
        elif request.feature_set == "coords132":
            X = np.array([frame.coords for frame in request.frames], dtype=np.float32)
            feature_key = "Coords132"
        else:
            raise HTTPException(400, "Use 'angles14' or 'coords132'")
        
        X = np.expand_dims(X, axis=0)  # Add batch dimension
        model = load_model("Bi-LSTM", feature_key)
        prediction = model.predict(X, verbose=0)[0]
        
        predicted_idx = int(np.argmax(prediction))
        confidence = float(np.max(prediction))
        inference_time = (time.time() - start_time) * 1000
        
        return ClassifyResponse(
            move=class_names[predicted_idx].replace("_", " ").title(),
            confidence=round(confidence, 4),
            move_id=class_names[predicted_idx],
            inference_time_ms=round(inference_time, 2),
            all_probabilities=[round(float(p), 4) for p in prediction]
        )
        
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")
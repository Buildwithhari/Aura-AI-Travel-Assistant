import os
import re

# Load environment variables from .env if present
def _load_dotenv():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

_load_dotenv()

# Global variables for caching loaded models and classifiers
_MBERT_TOKENIZER = None
_MBERT_MODEL = None
_CLASSIFIER_HEAD = None
_LABEL_ENCODER = None
_MODEL_LOADED = False

def detect_multilingual_text(message: str) -> bool:
    """
    Detect if the user message contains mixed-language words or Indian language text.
    Checks unicode ranges for Devanagari, Tamil, Kannada, Telugu, and a list of common transliterated words.
    """
    if not message:
        return False
        
    # Check unicode ranges for Devanagari, Tamil, Kannada, Telugu, Malayalam
    # Devanagari (Hindi): \u0900-\u097F
    # Tamil: \u0B80-\u0BFF
    # Kannada: \u0C80-\u0CFF
    # Telugu: \u0C00-\u0C7F
    # Malayalam: \u0D00-\u0D7F
    non_ascii_pattern = re.compile(r"[\u0900-\u097F\u0B80-\u0BFF\u0C80-\u0CFF\u0C00-\u0C7F\u0D00-\u0D7F]")
    if non_ascii_pattern.search(message):
        return True
        
    # Check transliterated words (Hinglish, Tanglish, Kanglish, Telinglish, Malayalinglish)
    words = re.findall(r"\b[a-z]+\b", message.lower())
    indian_words = {
        # Hindi / Hinglish
        "ke", "liye", "chahiye", "karo", "hai", "milega", "karni", "se", "baat", "alvida",
        # Tamil / Tanglish
        "la", "irundhu", "ku", "venum", "naan", "poganum", "panna", "mudiyuma", "pannanum", 
        "eppadi", "edukkuradhu", "nandri", "vanakkam", "pesanum", "romba",
        # Kannada / Kanglish
        "inda", "ge", "beku", "madi", "dalli", "bagge", "heli", "enu", "ege", "madodu", 
        "siguthe", "dhanyavadagalu",
        # Telugu / Telinglish
        "nundi", "ki", "kavali", "naku", "lo", "cheyali", "entha", "ela", "marchali", 
        "namaskaram", "selavu", "dhanyavadalu",
        # Malayalam / Malayalinglish
        "enikku", "venam", "pokanam", "ninnu", "ilekku"
    }
    
    for w in words:
        if w in indian_words:
            return True
            
    return False

def load_mbert_model() -> bool:
    """
    Lazy load mBERT model and tokenizer, and train/load classification head.
    Returns True if successful, False otherwise.
    """
    global _MBERT_TOKENIZER, _MBERT_MODEL, _CLASSIFIER_HEAD, _LABEL_ENCODER, _MODEL_LOADED
    if _MODEL_LOADED:
        return True
        
    try:
        import torch
        from transformers import AutoTokenizer, AutoModel
        import pandas as pd
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import LabelEncoder
        import pickle
    except ImportError as e:
        print(f"Failed to import required libraries for mBERT: {e}")
        return False

    try:
        model_name = os.environ.get("MBERT_MODEL", "bert-base-multilingual-cased")
        
        # Load tokenizer and model
        _MBERT_TOKENIZER = AutoTokenizer.from_pretrained(model_name)
        _MBERT_MODEL = AutoModel.from_pretrained(model_name)
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _MBERT_MODEL.to(device)
        _MBERT_MODEL.eval()
        
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "multilingual_intents.csv")
        cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mbert_classifier.pkl")
        
        csv_modified = os.path.getmtime(csv_path) if os.path.exists(csv_path) else 0
        cache_modified = os.path.getmtime(cache_path) if os.path.exists(cache_path) else 0
        
        if os.path.exists(cache_path) and cache_modified > csv_modified:
            with open(cache_path, "rb") as f:
                cache = pickle.load(f)
                _CLASSIFIER_HEAD = cache["clf"]
                _LABEL_ENCODER = cache["le"]
        else:
            if not os.path.exists(csv_path):
                print(f"Training CSV not found at {csv_path}. Cannot train mBERT classifier.")
                return False
                
            df = pd.read_csv(csv_path)
            texts = df["text"].tolist()
            labels = df["intent"].tolist()
            
            # Extract embeddings in batches
            embeddings = []
            batch_size = 16
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                inputs = _MBERT_TOKENIZER(batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=128)
                inputs = {k: v.to(device) for k, v in inputs.items()}
                with torch.no_grad():
                    outputs = _MBERT_MODEL(**inputs)
                batch_emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                embeddings.append(batch_emb)
            
            X = np.vstack(embeddings)
            
            _LABEL_ENCODER = LabelEncoder()
            y = _LABEL_ENCODER.fit_transform(labels)
            
            _CLASSIFIER_HEAD = LogisticRegression(max_iter=1000, C=1.0)
            _CLASSIFIER_HEAD.fit(X, y)
            
            # Save cache
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "wb") as f:
                pickle.dump({"clf": _CLASSIFIER_HEAD, "le": _LABEL_ENCODER}, f)
                
        _MODEL_LOADED = True
        return True
    except Exception as e:
        print(f"Error loading or training mBERT model: {e}")
        return False

def predict_intent_with_mbert(message: str) -> dict:
    """
    Classify the message intent using the mBERT model and custom classification head.
    Expected output:
    {
      "intent": "flight_search",
      "confidence": 0.82,
      "source": "mbert"
    }
    """
    if not _MODEL_LOADED:
        success = load_mbert_model()
        if not success:
            return {
                "intent": "fallback",
                "confidence": 0.0,
                "source": "mbert_failed"
            }
            
    try:
        import torch
        import numpy as np
        device = "cuda" if torch.cuda.is_available() else "cpu"
        inputs = _MBERT_TOKENIZER([message], return_tensors="pt", padding=True, truncation=True, max_length=128)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = _MBERT_MODEL(**inputs)
        emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()
        
        proba = _CLASSIFIER_HEAD.predict_proba(emb)[0]
        idx = int(np.argmax(proba))
        intent = _LABEL_ENCODER.classes_[idx]
        confidence = float(proba[idx])
        
        return {
            "intent": str(intent),
            "confidence": round(confidence, 3),
            "source": "mbert"
        }
    except Exception as e:
        print(f"Prediction failed in mbert_classifier: {e}")
        return {
            "intent": "fallback",
            "confidence": 0.0,
            "source": "mbert_failed"
        }

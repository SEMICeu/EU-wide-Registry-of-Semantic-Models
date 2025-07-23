from pydantic import BaseModel
from typing import List

class Synonym(BaseModel):
    term: str
    source: str
    score: int

class DetectedLanguage(BaseModel):
    language: str
    score: float

class TranslationItem(BaseModel):
    term: str
    lang: str

class TranslationResponse(BaseModel):
    detectedLanguage: DetectedLanguage
    translations: List[TranslationItem]

class ErrorResponse(BaseModel):
    error: str
    detail: str

from functools import lru_cache
from transformers import MarianMTModel, MarianTokenizer
from huggingface_hub import snapshot_download
import urllib3
import ssl
import os
import requests
import fasttext

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# Disable cert verification globally
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

# Custom Session subclass to prevent recursion
class NoVerifySession(requests.Session):
    def __init__(self):
        super().__init__()
        self.verify = False

@lru_cache(maxsize=10)
def load_model(source: str, target: str):
    try:
        # Monkey-patch requests.Session temporarily
        original_session = requests.Session
        requests.Session = NoVerifySession

        local_model_path = snapshot_download(
            repo_id=f"Helsinki-NLP/opus-mt-{source}-{target}",
            local_dir=f"./models/opus-mt-{source}-{target}",
            local_dir_use_symlinks=False,
        )
        print(f"Model downloaded to: {local_model_path}")

        tokenizer = MarianTokenizer.from_pretrained(local_model_path)
        model = MarianMTModel.from_pretrained(local_model_path)

        print("Model and tokenizer loaded from local directory!")
        return tokenizer, model

    except Exception as e:
        print(f"Error loading model: {e}")

    finally:
        # Restore the original requests.Session to avoid side effects
        requests.Session = original_session

from pathlib import Path

MODEL_DIR = Path(__file__).parent.parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "lid.176.ftz"
MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"

import urllib.request

def download_fasttext_model():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print("🔽 Downloading FastText model...")

    response = requests.get(MODEL_URL, stream=True)
    if not response.ok:
        raise RuntimeError(f"HTTP error {response.status_code} when downloading model")

    with open(MODEL_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    # Basic size check (FastText .ftz file is ~126MB)
    if MODEL_PATH.stat().st_size < 1_000_000:
        raise RuntimeError("Downloaded model file is too small — likely corrupted or incomplete.")
    
    print("✅ FastText model downloaded and validated.")

@lru_cache(maxsize=1)
def get_fasttext_model() -> fasttext.FastText._FastText:
    if not MODEL_PATH.exists():
        download_fasttext_model()

    return fasttext.load_model(str(MODEL_PATH.resolve()))
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
import urllib.request
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "lid.176.ftz"

def download_fasttext_model():
    
    MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
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

from sentence_transformers import SentenceTransformer, util

# Load the model once (you can reuse this outside the function)


@lru_cache(maxsize=1)
def load_model_mini():
    try:
        # Monkey-patch requests.Session temporarily
        original_session = requests.Session
        requests.Session = NoVerifySession

        local_model_path = snapshot_download(
            repo_id=f"sentence-transformers/all-MiniLM-L6-v2",
            local_dir=f"./models/all-MiniLM-L6-v2",
            local_dir_use_symlinks=False,
        )
        print(f"Model downloaded to: {local_model_path}")

        model = SentenceTransformer(local_model_path)

        print("Model mini loaded from local directory!")
        return model

    except Exception as e:
        print(f"Error loading model: {e}")

    finally:
        # Restore the original requests.Session to avoid side effects
        requests.Session = original_session

def best_synonym_for_context(context: str, synonyms: list[str], return_all=False):
    """
    Returns the synonym that best fits the given context sentence.
    
    Parameters:
        context (str): A sentence providing context.
        synonyms (list[str]): List of synonym candidates.
        return_all (bool): If True, returns all synonyms with scores.
        
    Returns:
        str: The best-fitting synonym (or list of tuples if return_all=True)
    """
    # Embed the context
    model = load_model_mini()
    context_embedding = model.encode(context, convert_to_tensor=True)

    # Optionally, make synonym phrases more natural (optional)
    synonym_phrases = [f"The word is '{syn}'." for syn in synonyms]

    # Embed the synonyms
    synonym_embeddings = model.encode(synonym_phrases, convert_to_tensor=True)

    # Compute cosine similarity
    cos_scores = util.cos_sim(context_embedding, synonym_embeddings)[0]

    # Pair scores with original synonyms
    # Scale scores to integers (0–100)
    scored_synonyms = [
        (syn, int((score + 1) * 50)) 
        for syn, score in zip(synonyms, cos_scores.tolist())
    ]

    # Sort by similarity score descending
    scored_synonyms.sort(key=lambda x: x[1], reverse=True)

    if return_all:
        return scored_synonyms
    else:
        return scored_synonyms[0][0]  # Just the best synonym
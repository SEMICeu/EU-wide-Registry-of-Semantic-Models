from functools import lru_cache
from transformers import MarianMTModel, MarianTokenizer
from huggingface_hub import snapshot_download
import urllib3
import ssl
import os
import requests
import fasttext
import traceback
import logging

from huggingface_hub import configure_http_backend

logger = logging.getLogger(__name__)

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

def backend_factory() -> requests.Session:
    session = requests.Session()
    session.verify = False
    return session

configure_http_backend(backend_factory=backend_factory)

@lru_cache(maxsize=10)
def load_model_translate(source: str, target: str):
    try:
        # Monkey-patch requests.Session temporarily
        original_session = requests.Session
        #requests.Session = NoVerifySession

        repo_id="Helsinki-NLP/opus-mt-" +source + "-" + target
        local_dir="./models/opus-mt-" + source + "-" + target

        try:
            local_model_path = snapshot_download(
                repo_id=repo_id,
                local_dir=local_dir,
                local_dir_use_symlinks=False,
                local_files_only=True
            )
            logger.info("Model " + repo_id + " found locally:" + local_model_path)
        except Exception as e:
            logger.warning(f"Local model not found, attempting download from hub... ({e})")
            # Retry with network access
            local_model_path = snapshot_download(
                repo_id=repo_id,
                local_dir=local_dir,
                local_dir_use_symlinks=False,
                local_files_only=False,  # Allow download
            )
            logger.info("Model " + repo_id + " downloaded to:" + local_model_path)

        tokenizer = MarianTokenizer.from_pretrained(local_model_path)
        model = MarianMTModel.from_pretrained(local_model_path)

        logger.info("Model and tokenizer loaded from local directory!")
        return tokenizer, model

    except Exception as e:
        logger.info(f"Error loading model: {e}")
        logger.info(traceback.print_exc())

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
    logger.info("🔽 Downloading FastText model...")

    response = requests.get(MODEL_URL, stream=True)
    if not response.ok:
        raise RuntimeError(f"HTTP error {response.status_code} when downloading model")

    with open(MODEL_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    # Basic size check (FastText .ftz file is ~126MB)
    if MODEL_PATH.stat().st_size < 1_000_000:
        raise RuntimeError("Downloaded model file is too small — likely corrupted or incomplete.")
    
    logger.info("✅ FastText model downloaded and validated.")

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
            local_files_only=True
        )
        logger.info(f"Model downloaded to: {local_model_path}")

        model = SentenceTransformer(local_model_path)

        logger.info("Model mini loaded from local directory!")
        return model

    except Exception as e:
        logger.error(f"Error loading model: {e}")

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

from huggingface_hub import list_models
import re
import time

def list_pairs():
    pattern = re.compile(r"^Helsinki-NLP/opus-mt-([a-z\-]+)-([a-z\-]+)$")

    lang_pairs = set()

    try:
        logger.info("Fetching models from Hugging Face Hub...")
        models = list_models(author="Helsinki-NLP")
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        exit(1)

    for model in models:
        model_id = model.modelId
        match = pattern.match(model_id)
        if match:
            src, tgt = match.groups()
            lang_pairs.add((src, tgt))

    return lang_pairs

def rank_theme_codes_by_context(context: str, themes: dict, return_all=False):
    """
    Ranks dataset theme codes by semantic similarity to a given context sentence.
    
    Parameters:
        context (str): A sentence providing context.
        themes (dict): A dictionary of theme codes -> {code, label, definition}.
        return_all (bool): If True, returns all codes ranked by similarity.
        
    Returns:
        list | str: Best-matching theme code or list of (code, score) tuples if return_all=True
    """
    model = load_model_mini()
    context_embedding = model.encode(context, convert_to_tensor=True)

    # Prepare descriptive texts from themes
    theme_texts = []
    codes = []
    for code, data in themes.items():
        text = f"{data['label']}. {data['definition']}"
        theme_texts.append(text)
        codes.append(code)

    # Embed the theme descriptions
    theme_embeddings = model.encode(theme_texts, convert_to_tensor=True)

    # Compute cosine similarity
    cos_scores = util.cos_sim(context_embedding, theme_embeddings)[0]

    # Pair scores with codes and scale to 0–100
    scored_codes = [
        (code, int((score + 1) * 50))
        for code, score in zip(codes, cos_scores.tolist())
    ]

    # Sort descending
    scored_codes.sort(key=lambda x: x[1], reverse=True)

    if return_all:
        return scored_codes
    else:
        return scored_codes[0][0]

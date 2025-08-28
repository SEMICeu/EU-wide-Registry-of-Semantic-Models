from huggingface_hub import list_models
from collections import Counter, defaultdict

import urllib3
import ssl
import os
import requests
from huggingface_hub import configure_http_backend
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

# Languages of interest
start_langs = ["en", "de", "fr", "it", "pl", "es", "ro", "pt", "hu", "nl", 
               "el", "pt", "cs", "sv", "bg", "sk", "fi", "da", "fi", "no", "lt", "lv"
               "sl", "et", "ga", "mt"]

# List all Helsinki-NLP models
models = list_models(author="Helsinki-NLP")

# Filter MarianMT models
marian_models = [m.modelId for m in models if "opus-mt" in m.modelId]

# Extract language pairs
pairs = []
for model in marian_models:
    parts = model.split("opus-mt-")
    if len(parts) > 1:
        langs = parts[1].split("-")
        src = langs[0]
        tgts = langs[1:]
        for tgt in tgts:
            pairs.append((src, tgt))

# Collect targets for each start language
targets_by_src = defaultdict(set)
for src, tgt in pairs:
    if src in start_langs:
        targets_by_src[src].add(tgt)

# Count pairs
start_counts = {src: len(targets_by_src[src]) for src in start_langs}

# Sort by decreasing count
ordered_langs = sorted(start_counts.items(), key=lambda x: x[1], reverse=True)

# Now build the “exclusive” target sets
already_seen = set()
result = []
for src, count in ordered_langs:
    unique_targets = targets_by_src[src] - already_seen
    result.append((src, count, sorted(unique_targets)))
    already_seen |= targets_by_src[src]

# Print results
print("Language | Pair count | Exclusive targets (removing overlaps with previous)")
print("---------|------------|--------------------------------------------")
for src, count, uniques in result:
    print(f"{src:<8} | {count:<10} | {', '.join(uniques) if uniques else '-'}")
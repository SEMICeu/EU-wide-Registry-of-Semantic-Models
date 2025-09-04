from huggingface_hub import list_models, model_info
from collections import Counter, defaultdict

import urllib3
import ssl
import os
import requests
from huggingface_hub import configure_http_backend
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context
import pandas as pd

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

# Table 1: Pair count and exclusive targets
print("Language | Pair count | Exclusive targets (removing overlaps with previous)")
print("---------|------------|--------------------------------------------")
for src, count, uniques in result:
    print(f"{src:<8} | {count:<10} | {', '.join(uniques) if uniques else '-'}")

print("\n")  # Spacer between tables

# Table 2: Full list of targets with counts, ordered by decreasing pair count
print("Language | Pair count | All targets")
print("---------|------------|----------------")
for src, count in ordered_langs:
    all_targets = sorted(targets_by_src[src]) if targets_by_src[src] else []
    print(f"{src:<8} | {len(all_targets):<10} | {', '.join(all_targets) if all_targets else '-'}")

# Collect metadata
rows = []
for model_id in marian_models:
    try:
        info = model_info(model_id)
        # Sum file sizes (in bytes) from all siblings
        total_size = sum(s.size for s in info.siblings if s.size is not None)

        rows.append({
            "model": model_id,
            "downloads": info.downloads,
            "lastModified": info.lastModified,
            "likes": info.likes,
            "tags": ", ".join(info.tags) if info.tags else "",
            "size_bytes": total_size,
            "size_MB": round(total_size / (1024 * 1024), 2)
        })
    except Exception as e:
        print(f"Could not fetch info for {model_id}: {e}")

# Build DataFrame
df = pd.DataFrame(rows)

# Sort by downloads (most popular first)
df = df.sort_values(by="downloads", ascending=False).reset_index(drop=True)

# Print table to console
print(df.to_string(max_rows=50, max_colwidth=40))
df.to_csv("helsinki_models.csv", index=False)
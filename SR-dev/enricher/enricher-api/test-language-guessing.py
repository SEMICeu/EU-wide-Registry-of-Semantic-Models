import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import fasttext
import logging
import requests
import urllib3
import ssl
import os
from huggingface_hub import configure_http_backend
import torch.nn.functional as F
import time

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

# --------------------------
# 1️⃣ Input Data
# --------------------------
descriptions = [
    "DCAT es un vocabulario RDF diseñado para facilitar la interoperabilidad entre catálogos de datos publicados en la Web. Utilizando DCAT para describir datos disponibles en catálogos se aumenta la posibilidad de que sean descubiertos y se permite que las aplicaciones consuman fácilmente los metadatos de varios catálogos.",        # Espagnol
    "DCAT est un vocabulaire développé pour faciliter l'interopérabilité entre les jeux de données publiées sur le Web. En utilisant DCAT pour décrire les jeux de données dans les catalogues de données, les fournisseurs de données facilitent leur découverte et permettent que les applications consomment facilement les métadonnées de plusieurs catalogues. Il permet de plus la publication décentralisée des catalogues et facilite la recherche fédérée des données entre plusieurs sites. Les métadonnées DCAT aggrégées peuvent servir comme un manifeste pour faciliter la préservation digitale des ressources. DCAT est définie à l'adresse http://www.w3.org/TR/vocab-dcat/. Toute différence entre ce document normatif et le présent vocabulaire est une erreur dans le vocabulaire.",                  # French
    "DCAT is an RDF vocabulary designed to facilitate interoperability between data catalogs published on the Web. By using DCAT to describe datasets in data catalogs, publishers increase discoverability and enable applications easily to consume metadata from multiple catalogs. It further enables decentralized publishing of catalogs and facilitates federated dataset search across sites. Aggregated DCAT metadata can serve as a manifest file to facilitate digital preservation. DCAT is defined at http://www.w3.org/TR/vocab-dcat/. Any variance between that normative document and this schema is an error in this schema.",           # English
    "DCAT je RDF slovník navržený pro zprostředkování interoperability mezi datovými katalogy publikovanými na Webu. Poskytovatelé dat používáním slovníku DCAT pro popis datových sad v datových katalozích zvyšují jejich dohledatelnost a umožňují aplikacím konzumovat metadata z více katalogů. Dále je umožňena decentralizovaná publikace katalogů a federované dotazování na datové sady napříč katalogy. Agregovaná DCAT metadata mohou také sloužit jako průvodka umožňující digitální uchování informace. DCAT je definován na http://www.w3.org/TR/vocab-dcat/. Jakýkoliv nesoulad mezi odkazovaným dokumentem a tímto schématem je chybou v tomto schématu.",                   # CS
    "DCAT è un vocabolario RDF progettato per facilitare l'interoperabilità tra i cataloghi di dati pubblicati nel Web. Utilizzando DCAT per descrivere i dataset nei cataloghi di dati, i fornitori migliorano la capacità di individuazione dei dati e abilitano le  applicazioni al consumo di dati provenienti da cataloghi differenti. DCAT permette di decentralizzare la pubblicazione di cataloghi e facilita la ricerca federata dei dataset. L'aggregazione dei metadati federati può fungere da file manifesto per facilitare la conservazione digitale. DCAT è definito all'indirizzo http://www.w3.org/TR/vocab-dcat/. Qualsiasi scostamento tra tale definizione normativa e questo schema è da considerarsi un errore di questo schema.",                   # Italian
    "DCATは、ウェブ上で公開されたデータ・カタログ間の相互運用性の促進を目的とするRDFの語彙です。このドキュメントでは、その利用のために、スキーマを定義し、例を提供します。データ・カタログ内のデータセットを記述するためにDCATを用いると、公開者が、発見可能性を増加させ、アプリケーションが複数のカタログのメタデータを容易に利用できるようになります。さらに、カタログの分散公開を可能にし、複数のサイトにまたがるデータセットの統合検索を促進します。集約されたDCATメタデータは、ディジタル保存を促進するためのマニフェスト・ファイルとして使用できます。",               # Japanese
    "Το DCAT είναι ένα RDF λεξιλόγιο που σχεδιάσθηκε για να κάνει εφικτή τη διαλειτουργικότητα μεταξύ καταλόγων δεδομένων στον Παγκόσμιο Ιστό. Χρησιμοποιώντας το DCAT για την περιγραφή συνόλων δεδομένων, οι εκδότες αυτών αυξάνουν την ανακαλυψιμότητα και επιτρέπουν στις εφαρμογές την εύκολη κατανάλωση μεταδεδομένων από πολλαπλούς καταλόγους. Επιπλέον, δίνει τη δυνατότητα για αποκεντρωμένη έκδοση και διάθεση καταλόγων και επιτρέπει δυνατότητες ενοποιημένης αναζήτησης μεταξύ διαφορετικών πηγών. Συγκεντρωτικά μεταδεδομένα που έχουν περιγραφεί με το DCAT μπορούν να χρησιμοποιηθούν σαν ένα δηλωτικό αρχείο (manifest file) ώστε να διευκολύνουν την ψηφιακή συντήρηση.",                  # Greek
    "هي أنطولوجية تسهل تبادل البيانات بين مختلف الفهارس على الوب. استخدام هذه الأنطولوجية يساعد على اكتشاف قوائم  البيانات المنشورة على الوب و يمكن التطبيقات المختلفة من الاستفادة أتوماتيكيا من البيانات المتاحة من مختلف الفهارس.", #ar
    "DCAT er et RDF-vokabular som har til formål at understøtte interoperabilitet mellem datakataloger udgivet på nettet. Ved at anvende DCAT til at beskrive datasæt i datakataloger, kan udgivere øge findbarhed og gøre det gøre det lettere for applikationer at anvende metadata fra forskellige kataloger. Derudover understøttes decentraliseret udstilling af kataloger og fødererede datasætsøgninger på tværs af websider. Aggregerede DCAT-metadata kan fungere som fortegnelsesfiler der kan understøtte digital bevaring. DCAT er defineret på http://www.w3.org/TR/vocab-dcat/. Enhver forskel mellem det normative dokument og dette schema er en fejl i dette schema." #Danish
]

df = pd.DataFrame({"description": descriptions})

# --------------------------
# 2️⃣ Load Models
# --------------------------

# FastText
if not os.path.exists("lid.176.bin"):
    import urllib.request
    print("Downloading fastText lid.176.bin...")
    urllib.request.urlretrieve(
        "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin",
        "lid.176.bin"
    )
fasttext_model = fasttext.load_model("lid.176.bin")

# Hugging Face Transformer (papluca)
# papluca/xlm-roberta-base-language-detection
# simoneteglia/xlm-roberta-europarl-language-detection
papluca_model_name = "dinalzein/xlm-roberta-base-finetuned-language-identification"
papluca_tokenizer = AutoTokenizer.from_pretrained(papluca_model_name)
papluca_model = AutoModelForSequenceClassification.from_pretrained(papluca_model_name)

# --------------------------
# 3️⃣ Detection Functions
# --------------------------

def detect_fasttext(text):
    label, prob = fasttext_model.predict(text)
    return label[0].replace("__label__", ""), prob[0]

def detect_transformer_with_prob(texts, tokenizer, model):
    # batch for speed
    inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
    outputs = model(**inputs)
    probs = F.softmax(outputs.logits, dim=1)
    predictions = torch.argmax(probs, dim=1)
    labels = model.config.id2label
    results = [(labels[p.item()], probs[i][p].item()) for i, p in enumerate(predictions)]
    return results

# --------------------------
# 4️⃣ Run Detection + Measure Performance
# --------------------------

# FastText (per row, but very fast)
t0 = time.time()
df["lang_fasttext"], df["prob_fasttext"] = zip(*df["description"].apply(detect_fasttext))
fasttext_time = time.time() - t0

# Hugging Face (batch)
t0 = time.time()
results = detect_transformer_with_prob(df["description"].tolist(), papluca_tokenizer, papluca_model)
df["lang_papluca"], df["prob_papluca"] = zip(*results)
papluca_time = time.time() - t0

# --------------------------
# 5️⃣ Add Description Preview
# --------------------------
df["description_preview"] = df["description"].str[:20]

# Reorder columns for readability
cols = ["description_preview", 
        "lang_fasttext", "prob_fasttext", 
        "lang_papluca", "prob_papluca"]
df = df[cols]

# --------------------------
# 6️⃣ Save Results
# --------------------------
df.to_csv("descriptions_languages.csv", index=False)

print("✅ CSV generated: descriptions_languages.csv")
print(df)
print("\n⏱️ Performance:")
print(f"FastText: {fasttext_time:.4f} seconds for {len(df)} texts")
print(f"Papluca/XLM-R: {papluca_time:.4f} seconds for {len(df)} texts")

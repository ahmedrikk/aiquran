import requests
import json
import os
import time
from sentence_transformers import SentenceTransformer
import hnswlib
import numpy as np

# --- Configuration ---
DATA_DIR = "quran_data"
INDEX_PATH = os.path.join(DATA_DIR, "quran_hadith.index")
METADATA_PATH = os.path.join(DATA_DIR, "metadata.json")
MODEL_NAME = 'all-MiniLM-L6-v2'

# URLs
QURAN_EN_URL = "https://api.alquran.cloud/v1/quran/en.asad"
QURAN_AR_URL = "https://api.alquran.cloud/v1/quran/quran-uthmani"


def fetch_json(url):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()

HADITH_COLLECTIONS = {
    "bukhari": {
        "en": "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/eng-bukhari.json",
        "ar": "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-bukhari.json",
        "name": "Sahih Bukhari"
    },
    "muslim": {
        "en": "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/eng-muslim.json",
        "ar": "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-muslim.json",
        "name": "Sahih Muslim"
    }
}

def fetch_quran_data():
    """Fetch and merge English and Arabic Quran."""
    print("🌍 Fetching Quran (English)...")
    res_en = fetch_json(QURAN_EN_URL)
    print("🌍 Fetching Quran (Arabic)...")
    res_ar = fetch_json(QURAN_AR_URL)
    
    quran_items = []
    
    surahs_en = res_en['data']['surahs']
    surahs_ar = res_ar['data']['surahs']
    
    arabic_surahs = {s['number']: s for s in surahs_ar}
    if len(surahs_en) != 114 or len(arabic_surahs) != 114:
        raise ValueError("Incomplete Quran dataset")
    for s_en in surahs_en:
        s_ar = arabic_surahs[s_en['number']]
        arabic_verses = {v['numberInSurah']: v for v in s_ar['ayahs']}
        if {v['numberInSurah'] for v in s_en['ayahs']} != set(arabic_verses):
            raise ValueError(f"Verse numbering mismatch in surah {s_en['number']}")
        
        for v_en in s_en['ayahs']:
            v_ar = arabic_verses[v_en['numberInSurah']]
            
            quran_items.append({
                "source_type": "quran",
                "text_en": v_en['text'],
                "text_ar": v_ar['text'],
                "surah_name": s_en['englishName'],
                "surah_number": s_en['number'],
                "verse_number": v_en['numberInSurah'],
                "id": f"quran-{s_en['number']}-{v_en['numberInSurah']}"
            })
            
    if len(quran_items) != 6236:
        raise ValueError("Expected 6236 explicitly numbered Quran verses")
    print(f"✅ Processed {len(quran_items)} Quran verses.")
    return quran_items

def fetch_hadith_collection(key, urls):
    """Fetch and merge English and Arabic Hadith."""
    print(f"🌍 Fetching {urls['name']} (English)...")
    res_en = requests.get(urls['en']).json()
    print(f"🌍 Fetching {urls['name']} (Arabic)...")
    res_ar = requests.get(urls['ar']).json()
    
    # Map Arabic hadiths by hadithnumber for merging
    ar_map = {h['hadithnumber']: h['text'] for h in res_ar['hadiths']}
    
    items = []
    
    for h_en in res_en['hadiths']:
        h_num = h_en['hadithnumber']
        raw_text_en = h_en['text']
        
        # Skip placeholders
        if not raw_text_en or len(raw_text_en) < 10:
            continue
            
        text_ar = ar_map.get(h_num, "")
        
        items.append({
            "source_type": "hadith",
            "collection": urls['name'],
            "text_en": raw_text_en,
            "text_ar": text_ar, 
            "hadith_number": h_num,
            "id": f"hadith-{key}-{h_num}"
        })
        
    print(f"✅ Processed {len(items)} hadiths for {urls['name']}.")
    return items

def create_index_and_embeddings():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 1. Fetch All Data
    all_items = fetch_quran_data()
    
    for key, urls in HADITH_COLLECTIONS.items():
        try:
            all_items.extend(fetch_hadith_collection(key, urls))
        except Exception as e:
            print(f"⚠️ Error fetching {key}: {e}")
        
    print(f"📦 Total items to index: {len(all_items)}")
    
    # 2. Create Embeddings (using English text for search)
    # We search primarily in English, but retrieve both
    start_time = time.time()
    
    # Use CPU friendly model loading check
    print("🧠 Loading model...")
    model = SentenceTransformer(MODEL_NAME)
    
    print("🧠 Generating embeddings...")
    texts_to_embed = [item['text_en'] for item in all_items]
    embeddings = model.encode(texts_to_embed, show_progress_bar=True)
    
    # 3. Build HNSW Index
    dim = embeddings.shape[1]
    count = len(all_items)
    
    print("🗂️ Building index...")
    p = hnswlib.Index(space='cosine', dim=dim)
    p.init_index(max_elements=count, ef_construction=200, M=16)
    p.add_items(embeddings, np.arange(count))
    
    p.save_index(INDEX_PATH)
    
    with open(METADATA_PATH, 'w') as f:
        json.dump(all_items, f)
        
    print(f"🎉 Index saved to {INDEX_PATH}")
    print(f"⏱️ Time taken: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    create_index_and_embeddings()

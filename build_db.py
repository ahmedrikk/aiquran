"""
QuranAI Data Ingestion Engine
Downloads Quran and Hadith from HuggingFace, generates embeddings, and builds vector index.
"""

import os
import json
import numpy as np
import hnswlib
from sentence_transformers import SentenceTransformer
from datasets import load_dataset
from tqdm import tqdm

# Configuration
DATA_DIR = "./quran_data"
INDEX_PATH = os.path.join(DATA_DIR, "quran_hadith.index")
METADATA_PATH = os.path.join(DATA_DIR, "metadata.json")
MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSION = 384  # For MiniLM-L6-v2

# Standard Quran Structure (Verse counts for Surahs 1-114)
SURAH_VERSE_COUNTS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135,
    112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85,
    54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13,
    14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
    29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11,
    11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6
]

SURAH_NAMES = [
    "Al-Fatiha", "Al-Baqarah", "Aal-Imran", "An-Nisa", "Al-Ma'idah", "Al-An'am", "Al-A'raf",
    "Al-Anfal", "At-Tawbah", "Yunus", "Hud", "Yusuf", "Ar-Ra'd", "Ibrahim", "Al-Hijr",
    "An-Nahl", "Al-Isra", "Al-Kahf", "Maryam", "Ta-Ha", "Al-Anbiya", "Al-Hajj", "Al-Mu'minun",
    "An-Nur", "Al-Furqan", "Ash-Shu'ara", "An-Naml", "Al-Qasas", "Al-Ankabut", "Ar-Rum",
    "Luqman", "As-Sajdah", "Al-Ahzab", "Saba", "Fatir", "Ya-Sin", "As-Saffat", "Sad",
    "Az-Zumar", "Ghafir", "Fussilat", "Ash-Shura", "Az-Zukhruf", "Ad-Dukhan", "Al-Jathiyah",
    "Al-Ahqaf", "Muhammad", "Al-Fath", "Al-Hujurat", "Qaf", "Adh-Dhariyat", "At-Tur",
    "An-Najm", "Al-Qamar", "Ar-Rahman", "Al-Waqi'ah", "Al-Hadid", "Al-Mujadila", "Al-Hashr",
    "Al-Mumtahanah", "As-Saff", "Al-Jumu'ah", "Al-Munafiqun", "At-Taghabun", "At-Talaq",
    "At-Tahrim", "Al-Mulk", "Al-Qalam", "Al-Haqqah", "Al-Ma'arij", "Nuh", "Al-Jinn",
    "Al-Muzzammil", "Al-Muddaththir", "Al-Qiyamah", "Al-Insan", "Al-Mursalat", "An-Naba",
    "An-Nazi'at", "Abasa", "At-Takwir", "Al-Infitar", "Al-Mutaffifin", "Al-Inshiqaq",
    "Al-Buruj", "At-Tariq", "Al-A'la", "Al-Ghashiyah", "Al-Fajr", "Al-Balad", "Ash-Shams",
    "Al-Layl", "Ad-Duha", "Ash-Sharh", "At-Tin", "Al-Alaq", "Al-Qadr", "Al-Bayyinah",
    "Az-Zalzalah", "Al-Adiyat", "Al-Qari'ah", "At-Takathur", "Al-Asr", "Al-Humazah",
    "Al-Fil", "Quraysh", "Al-Ma'un", "Al-Kawthar", "Al-Kafirun", "An-Nasr", "Al-Masad",
    "Al-Ikhlas", "Al-Falaq", "An-Nas"
]


def build_database():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    print("🧠 Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    all_items = []
    
    # ---------------------------------------------------------
    # 1. Fetch Quran Dataset
    # ---------------------------------------------------------
    # Never reconstruct references from row position: a missing row shifts every citation.
    from ingest import fetch_quran_data
    all_items.extend(fetch_quran_data())
    quran_items_count = len(all_items)

    # ---------------------------------------------------------
    # 2. Fetch Hadith Dataset
    # ---------------------------------------------------------
    print("🌍 Fetching Hadith dataset (gurgutan/sunnah_ar_en_dataset)...")
    try:
        hadith_ds = load_dataset("gurgutan/sunnah_ar_en_dataset", split="train")
    except Exception as e:
        print(f"❌ Error loading Hadith dataset: {e}")
        hadith_ds = []
    
    hadith_items_count = 0
    
    # Filter for Sahih Bukhari only
    for row in tqdm(hadith_ds, desc="📜 Processing Hadith (Bukhari)"):
        if row.get('book_title_en') == 'Sahih al-Bukhari':
            text_en = row.get('hadith_text_en', '')
            text_ar = row.get('hadith_text_ar', '')
            
            # Skip empty records
            if not text_en and not text_ar:
                continue
                
            all_items.append({
                "source_type": "hadith",
                "collection": "Sahih Bukhari",
                "hadith_number": str(row.get('hadith_uid', hadith_items_count + 1)),
                "chapter": row.get('hadith_chapter_name_en', ''),
                "narrator": row.get('hadith_narrator_en', ''),
                "text_en": text_en,
                "text_ar": text_ar,
                "id": f"hadith-bukhari-{row.get('hadith_uid', hadith_items_count + 1)}"
            })
            hadith_items_count += 1

    print(f"\n📦 Total items to index: {len(all_items)}")
    print(f"   • Quran Verses: {quran_items_count}")
    print(f"   • Bukhari Hadiths: {hadith_items_count}")

    # ---------------------------------------------------------
    # 3. Generate Embeddings & Index
    # ---------------------------------------------------------
    print("\n🧠 Generating embeddings (this may take a few minutes)...")
    
    # Combine Arabic and English for better semantic search
    texts_to_embed = [
        f"{item.get('text_ar', '')} {item.get('text_en', '')}" for item in all_items
    ]
    
    embeddings = model.encode(texts_to_embed, show_progress_bar=True, batch_size=32)
    embeddings = np.array(embeddings).astype('float32')

    print("\n🗂️ Building HNSW vector index...")
    index = hnswlib.Index(space='cosine', dim=DIMENSION)
    index.init_index(max_elements=len(all_items), ef_construction=200, M=16)
    index.add_items(embeddings, np.arange(len(all_items)))
    
    print(f"💾 Saving to {DATA_DIR}...")
    index.save_index(INDEX_PATH)
    
    with open(METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    print("\n✅ Database built successfully!")
    print(f"   Index: {INDEX_PATH}")
    print(f"   Metadata: {METADATA_PATH}")


if __name__ == "__main__":
    build_database()

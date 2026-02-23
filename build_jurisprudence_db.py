"""
QuranAI Comprehensive Jurisprudence Database Builder
Builds a complete vector index covering all Usul al-Fiqh sources:
1. Quran (complete)
2. Hadith (all major collections: Bukhari, Muslim, Tirmidhi, Abu Dawud, Ibn Majah, Nasa'i)
3. Ijma (scholarly consensus records)
4. Qiyas (analogical reasoning cases)
"""

import os
import json
import numpy as np
import hnswlib
from sentence_transformers import SentenceTransformer
from datasets import load_dataset
from tqdm import tqdm
import requests

# Configuration
DATA_DIR = "./quran_data"
INDEX_PATH = os.path.join(DATA_DIR, "jurisprudence.index")
METADATA_PATH = os.path.join(DATA_DIR, "jurisprudence_metadata.json")
MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSION = 384

# Quran structure
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

# All major hadith collections to fetch
HADITH_COLLECTIONS = {
    "bukhari": {"name": "Sahih Bukhari", "priority": 1},
    "muslim": {"name": "Sahih Muslim", "priority": 1},
    "tirmidhi": {"name": "Jami' at-Tirmidhi", "priority": 2},
    "abudawud": {"name": "Sunan Abu Dawud", "priority": 2},
    "ibnmajah": {"name": "Sunan Ibn Majah", "priority": 2},
    "nasai": {"name": "Sunan an-Nasa'i", "priority": 2},
}


def fetch_quran_complete():
    """Fetch complete Quran with Arabic and English."""
    print("📖 Fetching complete Quran...")
    
    try:
        quran_ds = load_dataset("ImruQays/Quran-Classical-Arabic-English-Parallel-texts", split="train")
    except Exception as e:
        print(f"⚠️ Primary dataset failed: {e}")
        try:
            quran_ds = load_dataset("Buraaq/quran-audio-text-dataset", split="train")
        except Exception as e2:
            print(f"❌ Fallback dataset failed: {e2}")
            return []
    
    items = []
    current_surah = 1
    current_verse = 1
    
    for row in tqdm(quran_ds, desc="Processing Quran"):
        text_ar = row.get('arabic-uthmanic') or row.get('arabic') or row.get('ar', '')
        text_en = row.get('en-sahih') or row.get('translation') or row.get('en', '')
        
        surah_name = SURAH_NAMES[current_surah - 1] if current_surah <= len(SURAH_NAMES) else f"Surah {current_surah}"
        
        items.append({
            "source_type": "quran",
            "source_category": "primary",
            "surah_name": surah_name,
            "surah_number": current_surah,
            "verse_number": current_verse,
            "text_en": text_en,
            "text_ar": text_ar,
            "id": f"quran-{current_surah}-{current_verse}",
            "search_text": f"{text_ar} {text_en} Surah {surah_name} verse {current_surah}:{current_verse}"
        })
        
        if current_surah <= len(SURAH_VERSE_COUNTS) and current_verse < SURAH_VERSE_COUNTS[current_surah - 1]:
            current_verse += 1
        else:
            current_surah += 1
            current_verse = 1
    
    print(f"✅ Loaded {len(items)} Quran verses")
    return items


def fetch_hadith_collection(collection_key: str, collection_info: dict):
    """Fetch a hadith collection from the hadith-api."""
    collection_name = collection_info["name"]
    print(f"\n📜 Fetching {collection_name}...")
    
    # URLs for English and Arabic
    en_url = f"https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/eng-{collection_key}.json"
    ar_url = f"https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-{collection_key}.json"
    
    items = []
    
    try:
        # Fetch English
        en_response = requests.get(en_url, timeout=60)
        en_data = en_response.json()
        
        # Fetch Arabic
        ar_response = requests.get(ar_url, timeout=60)
        ar_data = ar_response.json()
        
        # Create Arabic lookup map
        ar_map = {}
        for h in ar_data.get('hadiths', []):
            h_num = h.get('hadithnumber')
            if h_num:
                ar_map[h_num] = h.get('text', '')
        
        # Process English hadiths
        for h_en in tqdm(en_data.get('hadiths', []), desc=f"Processing {collection_name}"):
            h_num = h_en.get('hadithnumber')
            text_en = h_en.get('text', '')
            
            # Skip empty or too short
            if not text_en or len(text_en) < 20:
                continue
            
            text_ar = ar_map.get(h_num, '')
            
            # Get additional metadata
            metadata = h_en.get('metadata', {})
            chapter = metadata.get('chapter', {}).get('english', '')
            narrator = metadata.get('narrator', '')
            
            # Grade if available
            grade = None
            if 'grades' in metadata:
                for g in metadata['grades']:
                    if isinstance(g, dict):
                        grade = g.get('grade', '')
                        break
            
            items.append({
                "source_type": "hadith",
                "source_category": "primary",
                "collection": collection_name,
                "collection_key": collection_key,
                "hadith_number": str(h_num) if h_num else None,
                "chapter": chapter,
                "narrator": narrator,
                "grade": grade,
                "text_en": text_en,
                "text_ar": text_ar,
                "id": f"hadith-{collection_key}-{h_num}",
                "search_text": f"{text_en} {collection_name} hadith {chapter} {narrator}"
            })
        
        print(f"✅ Loaded {len(items)} hadiths from {collection_name}")
        
    except Exception as e:
        print(f"❌ Error fetching {collection_name}: {e}")
    
    return items


def load_ijma_database():
    """
    Load Ijma (scholarly consensus) records.
    These are established consensus rulings from the four major Sunni schools.
    """
    print("\n⚖️ Loading Ijma (Scholarly Consensus) database...")
    
    # Structured Ijma records covering major topics
    ijma_records = [
        {
            "topic": "Five Daily Prayers",
            "ruling": "The obligation of the five daily prayers (Salah) is established by Ijma of all Muslim scholars from the time of the Sahaba to the present day. Denial removes one from Islam.",
            "evidence_summary": "Quran 2:238, 4:103, 11:114, 17:78, 20:14, 30:17 - combined with universal practice",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Imam Abu Hanifa", "Imam Malik", "Imam Shafi'i", "Imam Ahmad", "Imam al-Tahawi"],
            "category": "aqeedah"
        },
        {
            "topic": "Prohibition of Riba (Usury/Interest)",
            "ruling": "All forms of riba (interest/usury) are strictly prohibited. This is Ijma among all four schools and all major scholars throughout Islamic history.",
            "evidence_summary": "Quran 2:275-279, 3:130, 4:161, 30:39 - Hadith on gold, silver, wheat, barley, dates, salt",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All major jurists"],
            "category": "muamalat"
        },
        {
            "topic": "Prohibition of Intoxicants",
            "ruling": "All intoxicants (khamr) are prohibited, regardless of quantity or type (alcohol, drugs, etc.). Consensus established after initial gradual prohibition.",
            "evidence_summary": "Quran 2:219, 4:43, 5:90-91 - gradual prohibition culminating in complete ban",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Sahaba consensus at time of Prophet ﷺ death"],
            "category": "muamalat"
        },
        {
            "topic": "Prohibition of Zina (Fornication/Adultery)",
            "ruling": "Zina (sexual relations outside marriage) is a major sin with prescribed hudud punishment. Unanimously prohibited.",
            "evidence_summary": "Quran 17:32, 24:2 - Sahih Bukhari and Muslim on avoiding zina",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "jinayat"
        },
        {
            "topic": "Obligation of Fasting Ramadan",
            "ruling": "Fasting the month of Ramadan is obligatory for every adult Muslim who is able. Consensus from time of Prophet ﷺ.",
            "evidence_summary": "Quran 2:183-185 - universal Muslim practice since revelation",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "ibadah"
        },
        {
            "topic": "Obligation of Zakat",
            "ruling": "Zakat on wealth is obligatory. Denial of its obligation removes one from Islam. Consensus on 2.5% for gold/silver/trade goods.",
            "evidence_summary": "Quran 9:5, 9:11, 9:60 - established practice of Sahaba",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Imam Abu Bakr's war against those who denied Zakat"],
            "category": "ibadah"
        },
        {
            "topic": "Finality of Prophethood",
            "ruling": "Prophet Muhammad ﷺ is the final prophet. No prophet will come after him. This is definitive Ijma of Ahl al-Sunnah.",
            "evidence_summary": "Quran 33:40 - 'Khatam al-Nabiyyin' - mutawatir hadith",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All orthodox scholars"],
            "category": "aqeedah"
        },
        {
            "topic": "Respect for the Quran",
            "ruling": "The Quran is the uncreated word of Allah. Disrespecting it (intentional desecration) takes one out of Islam.",
            "evidence_summary": "Ijma of Ahl al-Sunnah on Quran being Kalamullah Ghayr Makhluq",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Imam Ahmad and all Ahl al-Sunnah"],
            "category": "aqeedah"
        },
        {
            "topic": "Prohibition of Murder",
            "ruling": "Unlawful killing of a Muslim (or protected non-Muslim) is among the greatest sins. Consensus on prohibition and severe punishment.",
            "evidence_summary": "Quran 4:93, 5:32, 6:151, 17:33, 25:68",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "jinayat"
        },
        {
            "topic": "Prohibition of Pork",
            "ruling": "Consumption of pork (and pork products) is absolutely prohibited. No quantity is permissible.",
            "evidence_summary": "Quran 2:173, 5:3, 6:145, 16:115",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "muamalat"
        },
        {
            "topic": "Prohibition of Eating Carrion (Maytah)",
            "ruling": "Eating dead animals (that were not properly slaughtered) is prohibited except in dire necessity to save life.",
            "evidence_summary": "Quran 2:173, 5:3, 6:145, 16:115",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "muamalat"
        },
        {
            "topic": "Prohibition of Blood Consumption",
            "ruling": "Drinking blood is prohibited. Blood must be drained from slaughtered animals.",
            "evidence_summary": "Quran 6:145, 16:115 - combined with hadith on proper slaughter",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "muamalat"
        },
        {
            "topic": "Wudu for Prayer",
            "ruling": "Ritual ablution (wudu) is required before prayer when one has minor impurity. Consensus on the essential acts.",
            "evidence_summary": "Quran 5:6 - detailed in hadith literature",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four Imams and their schools"],
            "category": "taharah"
        },
        {
            "topic": "Ghusl for Major Impurity",
            "ruling": "Full bath (ghusl) is required after major impurity (janabah, menstruation, post-natal bleeding) before prayer.",
            "evidence_summary": "Quran 4:43, 5:6 - Sahih Muslim on occasions requiring ghusl",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "taharah"
        },
        {
            "topic": "Facing Qiblah in Prayer",
            "ruling": "Muslims must face the Ka'bah (Qiblah) in prayer when able. Established by Quran, Sunnah, and consensus.",
            "evidence_summary": "Quran 2:144, 2:149-150 - universal practice since Mecca became Qiblah",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "ibadah"
        },
        {
            "topic": "Hajj Once in Lifetime",
            "ruling": "Hajj to the Sacred House is obligatory once in a lifetime for those who are able. Consensus on this being a pillar of Islam.",
            "evidence_summary": "Quran 3:97 - hadith 'Islam is built on five' - Ijma",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "ibadah"
        },
        {
            "topic": "Prohibition of Apostasy",
            "ruling": "Leaving Islam (apostasy/riddah) is a major crime with prescribed punishment. Consensus among all four schools.",
            "evidence_summary": "Quran 4:89 - Sahih Bukhari on killing apostate - Ijma of Sahaba",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools agree on punishment, differ on repentance period"],
            "category": "jinayat"
        },
        {
            "topic": "Prohibition of Sorcery/Magic",
            "ruling": "Practicing magic/sorcery (sihr) that involves seeking help from jinn/shayateen is major kufr. Consensus of Ahl al-Sunnah.",
            "evidence_summary": "Quran 2:102 - hadith on seven destructive sins - Ijma",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All orthodox scholars"],
            "category": "aqeedah"
        },
        {
            "topic": "Tawhid (Oneness of Allah)",
            "ruling": "Allah is One, with no partners. Associating partners with Allah (shirk) is the greatest sin. Core of Islamic faith.",
            "evidence_summary": "Quran 112:1-4, 4:48, 31:13 - fundamental message of all prophets",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars throughout history"],
            "category": "aqeedah"
        },
        {
            "topic": "Belief in Angels",
            "ruling": "Belief in angels is obligatory. Denial constitutes disbelief. They are created from light, do not disobey Allah.",
            "evidence_summary": "Quran 2:285, 4:136 - detailed descriptions throughout Quran",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "aqeedah"
        },
        {
            "topic": "Belief in the Books",
            "ruling": "Belief in all divinely revealed books (Torah, Gospel, Psalms, Quran) is obligatory. We believe in their original form as revealed.",
            "evidence_summary": "Quran 2:285, 3:3-4, 4:136 - belief in previous revelations",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "aqeedah"
        },
        {
            "topic": "Belief in the Messengers",
            "ruling": "Belief in all prophets and messengers, with Muhammad ﷺ as the final messenger. Making distinction between them is prohibited.",
            "evidence_summary": "Quran 2:285, 4:152 - belief in all prophets equally",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "aqeedah"
        },
        {
            "topic": "Belief in the Last Day",
            "ruling": "Belief in the Day of Judgment, resurrection, paradise and hellfire is fundamental to Islamic faith.",
            "evidence_summary": "Quran throughout - especially Surahs on resurrection (75, 78, 81, etc.)",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "aqeedah"
        },
        {
            "topic": "Belief in Divine Decree (Qadar)",
            "ruling": "Belief that all good and evil is by Allah's decree (qadar), while maintaining human responsibility and choice.",
            "evidence_summary": "Hadith of Jibril on Iman - detailed in Aqeedah al-Tahawiyyah",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Ahl al-Sunnah wal Jama'ah consensus"],
            "category": "aqeedah"
        },
        {
            "topic": "Prohibition of Suicide",
            "ruling": "Suicide is absolutely prohibited and results in eternal hellfire. Consensus among all scholars.",
            "evidence_summary": "Hadith on suicide - Quran forbidding despair - numerous ahadith",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "jinayat"
        },
        {
            "topic": "Prohibition of Eating during Ramadan Days",
            "ruling": "Eating or drinking intentionally during fasting hours in Ramadan invalidates the fast and requires makeup plus expiation (for breaking without excuse).",
            "evidence_summary": "Quran 2:187 - hadith on fasting requirements",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools"],
            "category": "ibadah"
        },
        {
            "topic": "Adhan for Prayer",
            "ruling": "The call to prayer (Adhan) is established sunnah mu'akkadah for congregational prayers in mosques. Consensus on its form.",
            "evidence_summary": "Hadith on dream of Abdullah ibn Zaid - standardized form since Sahaba",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Consensus on six phrases of Adhan"],
            "category": "ibadah"
        },
        {
            "topic": "Friday Prayer Obligation",
            "ruling": "Friday prayer (Jumu'ah) is obligatory for adult males who are able. Attending is obligatory, abandoning without excuse is sin.",
            "evidence_summary": "Quran 62:9 - hadith on leaving three Fridays - Ijma",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools"],
            "category": "ibadah"
        },
        {
            "topic": "Congregational Prayer Merit",
            "ruling": "Praying in congregation (for men) is strongly emphasized. Prayer in congregation is 27 times better than alone. Consensus on merit.",
            "evidence_summary": "Sahih Bukhari and Muslim on congregation merit - Ijma on its importance",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All Muslim scholars"],
            "category": "ibadah"
        },
        {
            "topic": "Prohibition of Rebellion Against Ruler",
            "ruling": "Rebellion against the legitimate Muslim ruler without clear kufr and proof is prohibited. Maintains social order.",
            "evidence_summary": "Numerous ahadith on obedience to ruler unless clear kufr - Ijma of Sahaba",
            "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools emphasize stability"],
            "category": "siyasah"
        },
    ]
    
    items = []
    for idx, record in enumerate(ijma_records):
        items.append({
            "source_type": "ijma",
            "source_category": "secondary",
            "topic": record["topic"],
            "ruling": record["ruling"],
            "evidence_summary": record["evidence_summary"],
            "schools": record["schools"],
            "scholars": record["scholars"],
            "category": record["category"],
            "id": f"ijma-{idx}",
            "text_en": f"**{record['topic']}** - {record['ruling']}\n\nEvidence: {record['evidence_summary']}\n\nAgreed upon by: {', '.join(record['schools'])}",
            "search_text": f"{record['topic']} {record['ruling']} ijma consensus {record['category']}"
        })
    
    print(f"✅ Loaded {len(items)} Ijma records")
    return items


def load_qiyas_database():
    """
    Load Qiyas (analogical reasoning) cases.
    These are well-established cases where scholars applied analogy.
    """
    print("\n⚖️ Loading Qiyas (Analogical Reasoning) database...")
    
    qiyas_cases = [
        {
            "case": "Prohibition of All Intoxicants from Wine",
            "original_case": "Wine (khamr) is explicitly prohibited in Quran 5:90",
            "new_case": "All intoxicating substances (drugs, etc.)",
            "effective_cause": "Intoxication (sukr) - the mind-altering effect",
            "reasoning": "Since the effective cause of prohibition is intoxication, all substances that cause intoxication are prohibited by analogy to wine.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Imam Abu Hanifa", "Imam Shafi'i", "Imam Malik", "Imam Ahmad"],
            "category": "muamalat"
        },
        {
            "case": "Prohibition of All Carrion Animals",
            "original_case": "Dead animals (maytah) are prohibited in Quran 2:173",
            "new_case": "Animals killed by strangulation, violent blow, fall, goring, or eaten by wild beasts",
            "effective_cause": "Not being properly slaughtered with Bismillah and blood flow",
            "reasoning": "Animals that die without proper Islamic slaughter share the same effective cause as carrion - lack of proper purification through slaughter.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four Imams"],
            "category": "muamalat"
        },
        {
            "case": "Prohibition of All forms of Riba",
            "original_case": "Riba in gold and silver (currency) is explicitly prohibited",
            "new_case": "Riba in all commodities (foodstuffs, etc.)",
            "effective_cause": "Excess without consideration in exchange of similar commodities",
            "reasoning": "The Prophet ﷺ established riba applies to the six commodities (gold, silver, wheat, barley, dates, salt). By analogy, modern currencies and staple foods follow same rule.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools"],
            "category": "muamalat"
        },
        {
            "case": "Purity of All Liquids from Impurity",
            "original_case": "Water is pure until its color, taste, or smell changes",
            "new_case": "Other pure liquids (milk, vinegar, etc.)",
            "effective_cause": "Inherent purity until altered by impurity",
            "reasoning": "Just as water remains pure until changed by impurity, other pure liquids maintain purity unless contaminated.",
            "schools_applying": ["Hanafi", "Maliki"],
            "scholars": ["Hanafi and Maliki jurists"],
            "category": "taharah"
        },
        {
            "case": "Invalidity of Marriage Without Guardian",
            "original_case": "Prophet ﷺ said 'There is no marriage without a guardian (wali)'",
            "new_case": "Marriage contracts without proper guardian in all cases",
            "effective_cause": "Protection of woman's rights and proper contracting party",
            "reasoning": "Since the guardian's role is essential for valid marriage, any marriage without guardian shares this defect.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools - Hanafi differs on adult woman's right to self-marry"],
            "category": "nikah"
        },
        {
            "case": "Breaking Prayer on Uncovered Aurah",
            "original_case": "Prophet ﷺ commanded covering awrah for prayer",
            "new_case": "If awrah becomes uncovered during prayer, prayer is broken",
            "effective_cause": "Prayer requires proper covering as condition of validity",
            "reasoning": "Just as prayer requires wudu which if broken invalidates prayer, uncovering awrah which is condition of prayer invalidates it.",
            "schools_applying": ["Hanafi", "Shafi'i", "Hanbali"],
            "scholars": ["Imam Abu Hanifa", "Imam Shafi'i", "Imam Ahmad"],
            "category": "ibadah"
        },
        {
            "case": "Prohibition of Selling Unborn Animals",
            "original_case": "Selling what one does not possess is prohibited",
            "new_case": "Selling unborn fetuses in wombs",
            "effective_cause": "Uncertainty (gharar) and lack of possession/delivery capability",
            "reasoning": "Unborn animals involve excessive uncertainty (gharar) and the seller cannot deliver immediately, similar to selling what one doesn't possess.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools on prohibition of gharar"],
            "category": "muamalat"
        },
        {
            "case": "Wudu Breaking from Loss of Consciousness",
            "original_case": "Sleep breaks wudu (hadith)",
            "new_case": "Fainting, intoxication, insanity break wudu",
            "effective_cause": "Loss of consciousness and control",
            "reasoning": "Since sleep breaks wudu due to potential loss of control, any greater loss of consciousness (fainting, etc.) also breaks wudu.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Consensus of four schools"],
            "category": "taharah"
        },
        {
            "case": "Inheritance of Grandchildren Through Representation",
            "original_case": "Children inherit from parents",
            "new_case": "Grandchildren inherit their deceased parent's share from grandparents",
            "effective_cause": "Blood relationship and need for maintenance",
            "reasoning": "Grandchildren standing in place of their deceased parent maintains the same effective cause of inheritance: blood relation and need.",
            "schools_applying": ["Hanafi"],
            "scholars": ["Imam Abu Hanifa - Hanafi doctrine of representation"],
            "category": "mawarith"
        },
        {
            "case": "Prohibition of Selling Debt for Debt",
            "original_case": "Selling gold for gold with delay is riba (hadith)",
            "new_case": "Selling debt for debt (kali bil-kali)",
            "effective_cause": "Delay in both exchanges leading to uncertainty and potential riba",
            "reasoning": "Just as riba prohibits delayed exchange of similar commodities, selling debt for debt involves delay in both exchanges (kali bil-kali) and is prohibited.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools"],
            "category": "muamalat"
        },
        {
            "case": "Impurity of Dog Saliva",
            "original_case": "Dog licking vessel requires washing seven times (hadith)",
            "new_case": "All contact with dog saliva requires purification",
            "effective_cause": "Impurifying nature of dog saliva",
            "reasoning": "Since dog saliva requires specific purification for vessels, the same effective cause applies to any contact with dog saliva.",
            "schools_applying": ["Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Maliki, Shafi'i, and Hanbali schools - Hanafi differs on saliva"],
            "category": "taharah"
        },
        {
            "case": "Permission of Istihsan (Juristic Preference)",
            "original_case": "Textual exceptions override general rules in specific cases",
            "new_case": "Departing from strict analogy when it leads to hardship",
            "effective_cause": "Preventing hardship and maintaining maslaha (public interest)",
            "reasoning": "When strict qiyas leads to undue hardship, departing from it follows the spirit of sharia in easing difficulty.",
            "schools_applying": ["Hanafi", "Maliki"],
            "scholars": ["Imam Abu Hanifa", "Imam Malik - Hanafi and Maliki schools"],
            "category": "usul"
        },
        {
            "case": "Prohibition of Eating Predatory Animals",
            "original_case": "Predatory animals with fangs are prohibited (hadith)",
            "new_case": "All predatory animals (lions, tigers, bears, etc.)",
            "effective_cause": "Predatory nature and harm to humans",
            "reasoning": "Since predatory animals with fangs are prohibited due to their harmful nature, all animals sharing this characteristic are prohibited by analogy.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Consensus on prohibition of predators"],
            "category": "muamalat"
        },
        {
            "case": "Breaking Fast for Travelers",
            "original_case": "Travelers are given concession not to fast (Quran 2:184)",
            "new_case": "Difficulty in fasting during travel excuses breaking fast",
            "effective_cause": "Hardship and difficulty in observing the obligation",
            "reasoning": "Since travel hardship excuses fasting, any similar hardship that makes fasting genuinely difficult follows the same effective cause.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["All four schools"],
            "category": "ibadah"
        },
        {
            "case": "Requirement of Two Witnesses for Marriage",
            "original_case": "Financial transactions require two witnesses (Quran 2:282)",
            "new_case": "Marriage requires two witnesses for validity",
            "effective_cause": "Public declaration and verification of contract",
            "reasoning": "Just as financial contracts need witnesses for validity and public record, marriage contracts require witnesses for same purpose.",
            "schools_applying": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
            "scholars": ["Consensus on requirement of witnesses - differ on number"],
            "category": "nikah"
        },
    ]
    
    items = []
    for idx, case in enumerate(qiyas_cases):
        items.append({
            "source_type": "qiyas",
            "source_category": "secondary",
            "case": case["case"],
            "original_case": case["original_case"],
            "new_case": case["new_case"],
            "effective_cause": case["effective_cause"],
            "reasoning": case["reasoning"],
            "schools_applying": case["schools_applying"],
            "scholars": case["scholars"],
            "category": case["category"],
            "id": f"qiyas-{idx}",
            "text_en": f"**Qiyas Case: {case['case']}**\n\nOriginal Case: {case['original_case']}\nNew Case: {case['new_case']}\nEffective Cause ('Illah): {case['effective_cause']}\n\nReasoning: {case['reasoning']}",
            "search_text": f"{case['case']} qiyas analogy {case['category']} {case['effective_cause']}"
        })
    
    print(f"✅ Loaded {len(items)} Qiyas cases")
    return items


def build_jurisprudence_database():
    """Build the complete jurisprudence database."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    print("=" * 60)
    print("🏛️ BUILDING COMPREHENSIVE JURISPRUDENCE DATABASE")
    print("=" * 60)
    
    all_items = []
    
    # 1. Load Quran (Primary Source)
    quran_items = fetch_quran_complete()
    all_items.extend(quran_items)
    
    # 2. Load Hadith Collections (Primary Sources)
    for key, info in HADITH_COLLECTIONS.items():
        try:
            hadith_items = fetch_hadith_collection(key, info)
            all_items.extend(hadith_items)
        except Exception as e:
            print(f"⚠️ Skipping {info['name']} due to error: {e}")
    
    # 3. Load Ijma Records (Secondary Source)
    ijma_items = load_ijma_database()
    all_items.extend(ijma_items)
    
    # 4. Load Qiyas Cases (Secondary Source)
    qiyas_items = load_qiyas_database()
    all_items.extend(qiyas_items)
    
    print("\n" + "=" * 60)
    print(f"📊 TOTAL ITEMS TO INDEX: {len(all_items)}")
    print("=" * 60)
    
    # Print breakdown
    source_counts = {}
    for item in all_items:
        st = item.get("source_type", "unknown")
        source_counts[st] = source_counts.get(st, 0) + 1
    
    for source_type, count in sorted(source_counts.items()):
        print(f"   • {source_type.upper()}: {count}")
    
    # Generate embeddings
    print("\n🧠 Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)
    
    print("🧠 Generating embeddings...")
    texts_to_embed = [item.get("search_text", item.get("text_en", "")) for item in all_items]
    embeddings = model.encode(texts_to_embed, show_progress_bar=True, batch_size=32)
    embeddings = np.array(embeddings).astype('float32')
    
    # Build index
    print("\n🗂️ Building HNSW vector index...")
    index = hnswlib.Index(space='cosine', dim=DIMENSION)
    index.init_index(max_elements=len(all_items), ef_construction=200, M=16)
    index.add_items(embeddings, np.arange(len(all_items)))
    
    # Save
    print(f"💾 Saving to {DATA_DIR}...")
    index.save_index(INDEX_PATH)
    
    with open(METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("✅ DATABASE BUILD COMPLETE!")
    print("=" * 60)
    print(f"   Index: {INDEX_PATH}")
    print(f"   Metadata: {METADATA_PATH}")
    print(f"   Total Records: {len(all_items)}")


if __name__ == "__main__":
    build_jurisprudence_database()

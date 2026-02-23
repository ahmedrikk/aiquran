"""
Edge case tests for the jurisprudence system.
Functions are inlined here to avoid module-level startup (DB loading, model init).
"""
import re
import sys
import unittest

# ══════════════════════════════════════════════════════════════════════════════
#  FUNCTIONS UNDER TEST  (copied verbatim from backend.py)
# ══════════════════════════════════════════════════════════════════════════════

GREETING_PATTERNS = [
    r'^(hi|hello|hey|howdy|hiya|greetings|salaam|assalamu alaikum|salam)[\s!?.]*$',
    r'^(good\s*(morning|afternoon|evening|day))[\s!?.]*$',
    r'^(how\s*are\s*you|how\'?s\s*it\s*going|what\'?s\s*up|sup)[\s!?.]*$',
    r'^(thanks|thank\s*you|thx)[\s!?.]*$',
    r'^(bye|goodbye|see\s*you|take\s*care)[\s!?.]*$',
]

def is_small_talk(query: str) -> bool:
    normalized = query.lower().strip()
    for pattern in GREETING_PATTERNS:
        if re.match(pattern, normalized, re.IGNORECASE):
            return True
    return False


def format_source_for_context(item: dict) -> str:
    text_ar = item.get('text_ar') or "[Arabic unavailable]"
    text_en = item.get('text_en') or "[English unavailable]"
    source_type = item.get("source_type", "unknown")

    if source_type == "quran":
        return (f"📖 QURAN {item['surah_name']} [{item.get('surah_number', '?')}:{item['verse_number']}]\n"
                f"   Arabic: {text_ar}\n"
                f"   Translation: {text_en}")

    elif source_type == "hadith":
        collection = item.get('collection', 'Hadith')
        hadith_num = item.get('hadith_number', '?')
        grade = item.get('grade', '')
        grade_str = f" [{grade}]" if grade else ""
        return (f"📜 HADITH - {collection} #{hadith_num}{grade_str}\n"
                f"   Arabic: {text_ar}\n"
                f"   English: {text_en}")

    elif source_type == "ijma":
        topic = item.get('topic', 'Unknown Topic')
        schools = ', '.join(item.get('schools', []))
        return (f"⚖️ IJMA (SCHOLARLY CONSENSUS) - {topic}\n"
                f"   Consensus of: {schools}\n"
                f"   Ruling: {item.get('ruling', text_en)}")

    elif source_type == "qiyas":
        case = item.get('case', 'Unknown Case')
        return (f"⚖️ QIYAS (ANALOGICAL REASONING) - {case}\n"
                f"   Original Case: {item.get('original_case', '')}\n"
                f"   New Case: {item.get('new_case', '')}\n"
                f"   Effective Cause ('Illah): {item.get('effective_cause', '')}\n"
                f"   Reasoning: {item.get('reasoning', text_en)}")

    else:
        return f"📄 SOURCE: {text_en}"


def format_source_reference(item: dict) -> dict:
    source_type = item.get("source_type", "unknown")

    if source_type == "quran":
        return {
            "type": "quran",
            "surah_name": item.get("surah_name", "Unknown"),
            "verse_number": item.get("verse_number", "?")
        }

    elif source_type == "hadith":
        hadith_num = item.get("hadith_number", "")
        if not hadith_num or str(hadith_num).lower() in ("none", "n/a", "", "na"):
            hadith_num = None
        return {
            "type": "hadith",
            "collection": item.get("collection", "Hadith"),
            "hadith_number": hadith_num
        }

    elif source_type == "ijma":
        return {
            "type": "ijma",
            "topic": item.get("topic", "Scholarly Consensus"),
            "category": item.get("category", "general")
        }

    elif source_type == "qiyas":
        return {
            "type": "qiyas",
            "case": item.get("case", "Analogical Reasoning"),
            "category": item.get("category", "general")
        }

    return {"type": "unknown", "text": str(item.get("text_en", ""))[:50]}


# ══════════════════════════════════════════════════════════════════════════════
#  TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatSourceForContext(unittest.TestCase):

    # ── Quran ──────────────────────────────────────────────────────────────
    def test_quran_full(self):
        item = {"source_type": "quran", "surah_name": "Al-Baqarah",
                "surah_number": 2, "verse_number": 255,
                "text_ar": "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ", "text_en": "Allah — no deity except Him."}
        out = format_source_for_context(item)
        self.assertIn("Al-Baqarah", out)
        self.assertIn("2:255", out)
        self.assertIn("Arabic:", out)
        self.assertIn("Translation:", out)

    def test_quran_missing_arabic(self):
        item = {"source_type": "quran", "surah_name": "Al-Fatiha",
                "surah_number": 1, "verse_number": 1,
                "text_ar": None, "text_en": "In the name of Allah."}
        out = format_source_for_context(item)
        self.assertIn("[Arabic unavailable]", out)
        self.assertIn("In the name of Allah.", out)

    def test_quran_missing_english(self):
        item = {"source_type": "quran", "surah_name": "Al-Ikhlas",
                "surah_number": 112, "verse_number": 1,
                "text_ar": "قُلْ هُوَ اللَّهُ أَحَدٌ", "text_en": None}
        out = format_source_for_context(item)
        self.assertIn("[English unavailable]", out)

    def test_quran_missing_surah_number(self):
        item = {"source_type": "quran", "surah_name": "Al-Baqarah",
                "verse_number": 255, "text_ar": "x", "text_en": "y"}
        out = format_source_for_context(item)
        self.assertIn("?:255", out)

    # ── Hadith ─────────────────────────────────────────────────────────────
    def test_hadith_with_grade(self):
        item = {"source_type": "hadith", "collection": "Sahih Bukhari",
                "hadith_number": 5590, "grade": "Sahih",
                "text_ar": "Arabic text", "text_en": "English text"}
        out = format_source_for_context(item)
        self.assertIn("Sahih Bukhari #5590", out)
        self.assertIn("[Sahih]", out)

    def test_hadith_without_grade(self):
        item = {"source_type": "hadith", "collection": "Tirmidhi",
                "hadith_number": 1234, "grade": "",
                "text_ar": "x", "text_en": "y"}
        out = format_source_for_context(item)
        self.assertIn("Tirmidhi #1234", out)
        self.assertNotIn("[]", out)

    def test_hadith_missing_collection(self):
        item = {"source_type": "hadith", "hadith_number": 99,
                "text_ar": "x", "text_en": "y"}
        out = format_source_for_context(item)
        self.assertIn("Hadith #99", out)

    def test_hadith_missing_number(self):
        item = {"source_type": "hadith", "collection": "Muslim",
                "text_ar": "x", "text_en": "y"}
        out = format_source_for_context(item)
        self.assertIn("Muslim #?", out)

    # ── Ijma ───────────────────────────────────────────────────────────────
    def test_ijma_full(self):
        item = {"source_type": "ijma", "topic": "Five Prayers",
                "schools": ["Hanafi", "Maliki", "Shafi'i", "Hanbali"],
                "ruling": "Obligatory (Fard)", "text_en": "fallback", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("Five Prayers", out)
        self.assertIn("Hanafi", out)
        self.assertIn("Obligatory", out)

    def test_ijma_empty_schools(self):
        """Empty schools list must not crash."""
        item = {"source_type": "ijma", "topic": "Test",
                "schools": [], "ruling": "Obligatory", "text_en": "x", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("IJMA", out)
        self.assertIn("Test", out)

    def test_ijma_missing_ruling_falls_back_to_text_en(self):
        item = {"source_type": "ijma", "topic": "Topic",
                "schools": ["Hanafi"], "text_en": "Fallback text", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("Fallback text", out)

    def test_ijma_missing_schools_key(self):
        """Schools key entirely absent must not crash."""
        item = {"source_type": "ijma", "topic": "Test",
                "ruling": "Obligatory", "text_en": "x", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("IJMA", out)

    # ── Qiyas ──────────────────────────────────────────────────────────────
    def test_qiyas_full(self):
        item = {"source_type": "qiyas", "case": "Drugs",
                "original_case": "Khamr (wine)", "new_case": "Drugs",
                "effective_cause": "Intoxication", "reasoning": "Both intoxicate.",
                "text_en": "x", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("Drugs", out)
        self.assertIn("Intoxication", out)
        self.assertIn("Both intoxicate.", out)

    def test_qiyas_missing_all_optional_fields(self):
        """Qiyas with only source_type must not crash."""
        item = {"source_type": "qiyas", "text_en": "some text", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("QIYAS", out)
        self.assertIn("Unknown Case", out)

    def test_qiyas_missing_reasoning_falls_back_to_text_en(self):
        item = {"source_type": "qiyas", "case": "Test",
                "text_en": "Fallback reasoning", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("Fallback reasoning", out)

    # ── Unknown / missing type ─────────────────────────────────────────────
    def test_unknown_source_type(self):
        item = {"source_type": "fatwa", "text_en": "Some fatwa text", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("Some fatwa text", out)

    def test_missing_source_type(self):
        item = {"text_en": "No type at all", "text_ar": "x"}
        out = format_source_for_context(item)
        self.assertIn("No type at all", out)

    def test_both_texts_missing(self):
        """All text fields None/missing — must not crash."""
        item = {"source_type": "quran", "surah_name": "Al-Baqarah",
                "surah_number": 2, "verse_number": 1}
        out = format_source_for_context(item)
        self.assertIn("[Arabic unavailable]", out)
        self.assertIn("[English unavailable]", out)


class TestFormatSourceReference(unittest.TestCase):

    def test_quran_reference(self):
        item = {"source_type": "quran", "surah_name": "Al-Baqarah", "verse_number": 255}
        ref = format_source_reference(item)
        self.assertEqual(ref["type"], "quran")
        self.assertEqual(ref["surah_name"], "Al-Baqarah")
        self.assertEqual(ref["verse_number"], 255)

    def test_quran_missing_fields(self):
        ref = format_source_reference({"source_type": "quran"})
        self.assertEqual(ref["surah_name"], "Unknown")
        self.assertEqual(ref["verse_number"], "?")

    def test_hadith_normal(self):
        item = {"source_type": "hadith", "collection": "Bukhari", "hadith_number": 5590}
        ref = format_source_reference(item)
        self.assertEqual(ref["type"], "hadith")
        self.assertEqual(ref["hadith_number"], 5590)

    def test_hadith_number_none(self):
        item = {"source_type": "hadith", "collection": "Bukhari", "hadith_number": None}
        self.assertIsNone(format_source_reference(item)["hadith_number"])

    def test_hadith_number_na_variants(self):
        for val in ("N/A", "n/a", "NA", "na", "none", "None", ""):
            item = {"source_type": "hadith", "collection": "Bukhari", "hadith_number": val}
            ref = format_source_reference(item)
            self.assertIsNone(ref["hadith_number"], f"Expected None for {val!r}")

    def test_hadith_missing_collection(self):
        ref = format_source_reference({"source_type": "hadith", "hadith_number": 1})
        self.assertEqual(ref["collection"], "Hadith")

    def test_ijma_reference(self):
        item = {"source_type": "ijma", "topic": "Five Prayers", "category": "worship"}
        ref = format_source_reference(item)
        self.assertEqual(ref["type"], "ijma")
        self.assertEqual(ref["topic"], "Five Prayers")
        self.assertEqual(ref["category"], "worship")

    def test_ijma_missing_fields(self):
        ref = format_source_reference({"source_type": "ijma"})
        self.assertEqual(ref["topic"], "Scholarly Consensus")
        self.assertEqual(ref["category"], "general")

    def test_qiyas_reference(self):
        item = {"source_type": "qiyas", "case": "Drug analogy", "category": "prohibitions"}
        ref = format_source_reference(item)
        self.assertEqual(ref["type"], "qiyas")
        self.assertEqual(ref["case"], "Drug analogy")

    def test_qiyas_missing_fields(self):
        ref = format_source_reference({"source_type": "qiyas"})
        self.assertEqual(ref["case"], "Analogical Reasoning")
        self.assertEqual(ref["category"], "general")

    def test_unknown_type_returns_fallback(self):
        ref = format_source_reference({"source_type": "fatwa", "text_en": "Some fatwa text"})
        self.assertEqual(ref["type"], "unknown")
        self.assertIn("Some fatwa", ref["text"])

    def test_unknown_type_text_truncated_at_50(self):
        ref = format_source_reference({"source_type": "xyz", "text_en": "A" * 100})
        self.assertLessEqual(len(ref["text"]), 50)

    def test_completely_empty_item(self):
        """Entirely empty dict must not crash."""
        ref = format_source_reference({})
        self.assertEqual(ref["type"], "unknown")


class TestSmallTalkDetection(unittest.TestCase):

    def test_greetings_detected(self):
        for msg in ["hi", "hello", "Hey", "Salaam", "assalamu alaikum", "salam"]:
            self.assertTrue(is_small_talk(msg), f"Expected small talk: {msg!r}")

    def test_thanks_detected(self):
        for msg in ["thanks", "thank you", "thx"]:
            self.assertTrue(is_small_talk(msg), f"Expected small talk: {msg!r}")

    def test_farewells_detected(self):
        for msg in ["bye", "goodbye", "see you", "take care"]:
            self.assertTrue(is_small_talk(msg), f"Expected small talk: {msg!r}")

    def test_real_questions_not_small_talk(self):
        for msg in [
            "What does Islam say about interest (riba)?",
            "Is music halal or haram?",
            "What is the ruling on fasting?",
            "Tell me about zakat",
            "What is the consensus on prayer times?",
            "Is salam a greeting or a question?",  # contains "salam" but is a real question
        ]:
            self.assertFalse(is_small_talk(msg), f"Should NOT be small talk: {msg!r}")

    def test_empty_string(self):
        self.assertFalse(is_small_talk(""))

    def test_whitespace_only(self):
        self.assertFalse(is_small_talk("   "))


class TestSourceGrouping(unittest.TestCase):
    """Tests the grouping logic used in generate_response."""

    def _group(self, sources):
        return {
            "quran":  [s for s in sources if s.get("source_type") == "quran"],
            "hadith": [s for s in sources if s.get("source_type") == "hadith"],
            "ijma":   [s for s in sources if s.get("source_type") == "ijma"],
            "qiyas":  [s for s in sources if s.get("source_type") == "qiyas"],
        }

    def test_all_four_types(self):
        sources = [
            {"source_type": "quran"},
            {"source_type": "hadith"},
            {"source_type": "ijma"},
            {"source_type": "qiyas"},
        ]
        g = self._group(sources)
        for t in ("quran", "hadith", "ijma", "qiyas"):
            self.assertEqual(len(g[t]), 1, f"Expected 1 {t} source")

    def test_empty_sources_list(self):
        g = self._group([])
        for t in ("quran", "hadith", "ijma", "qiyas"):
            self.assertEqual(g[t], [])

    def test_unknown_type_not_grouped(self):
        g = self._group([{"source_type": "fatwa"}])
        self.assertEqual(sum(len(v) for v in g.values()), 0)

    def test_multiple_same_type(self):
        sources = [{"source_type": "hadith"}, {"source_type": "hadith"}, {"source_type": "quran"}]
        g = self._group(sources)
        self.assertEqual(len(g["hadith"]), 2)
        self.assertEqual(len(g["quran"]), 1)

    def test_missing_source_type_key(self):
        """Items with no source_type key must not crash and are excluded."""
        sources = [{"text_en": "No type"}, {"source_type": "quran"}]
        g = self._group(sources)
        self.assertEqual(len(g["quran"]), 1)
        self.assertEqual(len(g["hadith"]), 0)


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False)
    sys.exit(0 if result.result.wasSuccessful() else 1)

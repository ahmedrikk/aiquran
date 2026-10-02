import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const output = fileURLToPath(new URL('../quran_data/verified_sources.json', import.meta.url));
const counts = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6];

async function fetchJson(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(60_000) });
  if (!response.ok) throw new Error(`Source download failed (${response.status})`);
  return response.json();
}

export function mergeQuran(english, arabic) {
  const en = english.data.surahs;
  const ar = new Map(arabic.data.surahs.map(s => [s.number, s]));
  if (en.length !== 114 || ar.size !== 114) throw new Error('Expected 114 chapters');
  const rows = [];
  for (const chapter of en) {
    if (chapter.ayahs.length !== counts[chapter.number - 1]) throw new Error('Chapter verse count mismatch');
    const arabicVerses = new Map(ar.get(chapter.number).ayahs.map(v => [v.numberInSurah, v]));
    for (const verse of chapter.ayahs) {
      const matching = arabicVerses.get(verse.numberInSurah);
      if (!matching || matching.number !== verse.number || !matching.text || !verse.text) throw new Error('Arabic/translation reference mismatch');
      rows.push({ id: `quran-${chapter.number}-${verse.numberInSurah}`, source_type: 'quran',
        surah_number: chapter.number, surah_name: chapter.englishName, verse_number: verse.numberInSurah,
        text_en: verse.text, text_ar: matching.text, source_url: `https://alquran.cloud/ayah/${chapter.number}:${verse.numberInSurah}` });
    }
  }
  if (rows.length !== 6236 || new Set(rows.map(r => r.id)).size !== 6236) throw new Error('Incomplete or duplicate Quran references');
  if (!rows.find(r => r.id === 'quran-1-1')?.text_en.toLowerCase().includes('name')) throw new Error('Al-Fatiha 1:1 integrity check failed');
  return rows;
}

async function downloadSources() {
  const [english, arabic, hadithEn, hadithAr] = await Promise.all([
    fetchJson('https://api.alquran.cloud/v1/quran/en.asad'),
    fetchJson('https://api.alquran.cloud/v1/quran/quran-uthmani'),
    fetchJson('https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/eng-bukhari.json'),
    fetchJson('https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-bukhari.json'),
  ]);
  const rows = mergeQuran(english, arabic);
  const arabicHadith = new Map(hadithAr.hadiths.map(h => [String(h.hadithnumber), h.text]));
  for (const h of hadithEn.hadiths) {
    const number = String(h.hadithnumber);
    const ar = arabicHadith.get(number);
    if (!/^\d+(?:\.\d+)?$/.test(number) || !h.text?.trim() || !ar?.trim()) continue;
    rows.push({ id: `hadith-bukhari-${number}`, source_type: 'hadith', collection: 'Sahih Bukhari',
      hadith_number: number, text_en: h.text.trim(), text_ar: ar.trim(),
      source_url: `https://sunnah.com/bukhari:${number}` });
  }
  if (new Set(rows.map(r => r.id)).size !== rows.length) throw new Error('Duplicate source IDs');
  await mkdir(new URL('../quran_data/', import.meta.url), { recursive: true });
  await writeFile(output, JSON.stringify(rows));
  console.log(`Prepared ${rows.length} sources with explicit references (${6236} Quran verses).`);
  return rows;
}

async function upload(rows) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to import sources. Never use VITE_ for the service key.');
  for (let start = 0; start < rows.length; start += 100) {
    const result = await fetch(`${url}/rest/v1/quran_sources?on_conflict=id`, {
      method: 'POST', signal: AbortSignal.timeout(60_000),
      headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', Prefer: 'resolution=merge-duplicates,return=minimal' },
      body: JSON.stringify(rows.slice(start, start + 100).map(row => ({
        surah_number: null, surah_name: null, verse_number: null,
        collection: null, hadith_number: null, ...row,
      }))),
    });
    if (!result.ok) throw new Error(`Source import failed at batch ${start} (${result.status})`);
  }
  console.log(`Imported ${rows.length} sources.`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const rows = process.argv.includes('--cached') ? JSON.parse(await readFile(output, 'utf8')) : await downloadSources();
  if (process.argv.includes('--upload')) await upload(rows);
}

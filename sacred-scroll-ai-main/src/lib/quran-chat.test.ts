import { describe, it, expect } from 'vitest';
import { composeAnswer, searchQuestion, sourceOnlyAnswer, validateQuestion, type Source } from '../../../supabase/functions/quran-chat/core';

const source: Source = {
  id: 'quran-2-153', source_type: 'quran', surah_name: 'Al-Baqarah', surah_number: 2, verse_number: 153,
  text_ar: 'يَا أَيُّهَا الَّذِينَ آمَنُوا اسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ',
  text_en: 'Seek help through patience and prayer.', source_url: 'https://alquran.cloud/ayah/2:153',
};

describe('grounded chat', () => {
  it('rejects empty and excessively long questions', () => {
    expect(() => validateQuestion({ message: '  ' })).toThrow();
    expect(() => validateQuestion({ message: 'x'.repeat(4001) })).toThrow();
    expect(() => validateQuestion({ message: 'hello', chat_id: '../other-user' })).toThrow();
  });
  it('retrieves a requested verse directly', () => {
    expect(searchQuestion('Explain 2:153')).toEqual({ p_query: 'Explain 2:153', p_surah: 2, p_verse: 153 });
  });
  it('uses topical terms instead of requiring every question word to match', () => {
    expect(searchQuestion('What does the Quran say about patience?').p_query).toBe('patience');
    expect(searchQuestion('patience and prayer').p_query).toBe('patience OR prayer');
  });
  it('appends exact source text and validated reference numbers', () => {
    const result = composeAnswer(JSON.stringify({ answer: 'This passage encourages perseverance.', source_ids: [source.id, source.id] }), [source]);
    expect(result.response).toContain(source.text_ar);
    expect(result.response).toContain(source.text_en);
    expect(result.response).toContain('Al-Baqarah (2:153)');
    expect(result.sources_used).toHaveLength(1);
  });
  it('rejects invented sources and missing attribution', () => {
    expect(() => composeAnswer('{"answer":"Explanation","source_ids":["quran-99-999"]}', [source])).toThrow();
    expect(() => composeAnswer('{"answer":"Explanation","source_ids":[]}', [source])).toThrow();
  });
  it('rejects model-written reference numbers and quotations', () => {
    expect(() => composeAnswer(JSON.stringify({ answer: 'See 9:999', source_ids: [source.id] }), [source])).toThrow();
    expect(() => composeAnswer(JSON.stringify({ answer: 'The scripture says "invented text"', source_ids: [source.id] }), [source])).toThrow();
  });
  it('returns a clearly labeled source-only fallback on provider failure', () => {
    const result = sourceOnlyAnswer([source]);
    expect(result.degraded).toBe(true);
    expect(result.response).toContain('temporarily unavailable');
    expect(result.response).toContain(source.text_ar);
  });
});

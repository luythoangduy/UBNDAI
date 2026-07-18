import { describe, expect, it } from 'vitest';
import { clarificationControlFor, latestInteractiveMessageIndex, messagesFromHistory } from './chat-flow';

describe('chat flow helpers', () => {
  it('restores ordered transcript messages from a case', () => {
    expect(messagesFromHistory({
      case_id: 'case-1',
      messages: [
        { id: 1, role: 'user', content: 'Tôi cần làm khai sinh', created_at: '2026-07-18T10:00:00Z' },
        { id: 2, role: 'assistant', content: 'Trẻ sinh tại Việt Nam?', created_at: '2026-07-18T10:00:01Z', response: { reply: 'Trẻ sinh tại Việt Nam?', kind: 'clarify', clarifying_questions: ['Trẻ sinh tại Việt Nam?'] } },
      ],
    })).toEqual([
      { id: 1, role: 'user', text: 'Tôi cần làm khai sinh' },
      { id: 2, role: 'assistant', text: 'Trẻ sinh tại Việt Nam?', response: { reply: 'Trẻ sinh tại Việt Nam?', kind: 'clarify', clarifying_questions: ['Trẻ sinh tại Việt Nam?'] } },
    ]);
  });

  it('uses controls that match common clarification wording', () => {
    expect(clarificationControlFor('Trẻ sinh tại Việt Nam?')).toBe('boolean');
    expect(clarificationControlFor('Đã quá bao nhiêu ngày kể từ ngày sinh?')).toBe('number');
    expect(clarificationControlFor('Ngày sinh của trẻ là ngày nào?')).toBe('date');
    expect(clarificationControlFor('Bạn dự định nộp tại cơ quan nào?')).toBe('text');
  });

  it('only keeps the latest assistant response interactive', () => {
    expect(latestInteractiveMessageIndex([
      { role: 'assistant', text: 'Cũ', response: { reply: 'Cũ' } },
      { role: 'user', text: 'Có' },
      { role: 'assistant', text: 'Mới', response: { reply: 'Mới' } },
    ])).toBe(2);
  });
});

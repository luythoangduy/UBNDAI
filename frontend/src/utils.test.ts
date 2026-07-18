import { describe, expect, it } from 'vitest';
import { buildCaseQuery, clarificationAnswerEntries, formatBytes, formatSubmissionValue, humanizeStatus, visibleSubmissionEntries } from './utils';

describe('portal presentation helpers', () => {
  it('uses Vietnamese workflow labels and a readable fallback', () => {
    expect(humanizeStatus('in_officer_review')).toBe('Đang thẩm tra');
    expect(humanizeStatus('custom_state')).toBe('custom state');
  });

  it('formats upload sizes', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(1536)).toBe('1.5 KB');
    expect(formatBytes(2 * 1024 * 1024)).toBe('2.0 MB');
  });

  it('builds encoded server-side queue filters', () => {
    const query = new URLSearchParams(buildCaseQuery('khai sinh', 'in_officer_review', 'newest', 2));
    expect(query.get('q')).toBe('khai sinh');
    expect(query.get('status')).toBe('in_officer_review');
    expect(query.get('sort')).toBe('newest');
    expect(query.get('page')).toBe('2');
  });

  it('keeps internal draft metadata out of officer-facing rows', () => {
    const submission = { ho_ten: 'Nguyễn Văn A', _draft_html: '<p>long draft</p>', _readiness_score: 80, _answers: { ket_hon: false } };
    expect(visibleSubmissionEntries(submission)).toEqual([['ho_ten', 'Nguyễn Văn A']]);
    expect(clarificationAnswerEntries(submission)).toEqual([['ket_hon', false]]);
    expect(formatSubmissionValue(false)).toBe('Không');
  });
});

import { describe, expect, it } from 'vitest';
import { buildCaseQuery, formatBytes, humanizeStatus } from './utils';

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
});

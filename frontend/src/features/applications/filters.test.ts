import { describe, expect, it } from 'vitest';
import { readApplicationFilters, updateApplicationFilters } from './filters';

describe('application URL filters', () => {
  it('reads filters and pagination from a query string', () => {
    expect(readApplicationFilters(new URLSearchParams('search=HS-01&status=CAUTION_REVIEW_REQUIRED&page=3&page_size=10'))).toMatchObject({ search: 'HS-01', status: 'CAUTION_REVIEW_REQUIRED', page: 3, pageSize: 10 });
  });
  it('resets the page when a filter changes', () => {
    const next = updateApplicationFilters(new URLSearchParams('page=4&status=IN_PROCESS'), 'status', 'COMPLETED');
    expect(next.get('page')).toBeNull();
    expect(next.get('status')).toBe('COMPLETED');
  });
});

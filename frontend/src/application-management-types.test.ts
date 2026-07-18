import { describe, expect, it } from 'vitest';
import { projectApplicationStatus, serializeApplicationFilters } from './application-management-types';

describe('application management contracts', () => {
  it('projects legacy statuses without relabeling precheck as approval', () => {
    expect(projectApplicationStatus('awaiting_officer_review', true)).toBe('CAUTION_REVIEW_REQUIRED');
    expect(projectApplicationStatus('awaiting_officer_review', false)).toBe('READY_FOR_PROCESSING');
    expect(projectApplicationStatus('precheck_ready')).toBe('READY_FOR_PROCESSING');
    expect(projectApplicationStatus('unknown')).toBe('UNKNOWN');
  });

  it('serializes only non-default filters', () => {
    expect(serializeApplicationFilters({ search: '  HS-1 ', page: 2, pageSize: 20 })).toBe('search=HS-1&page=2');
  });
});

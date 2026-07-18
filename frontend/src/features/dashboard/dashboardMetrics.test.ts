import { describe, expect, it } from 'vitest';
import { normalizeStatusMetrics } from './dashboardMetrics';

describe('normalizeStatusMetrics', () => {
  it('uses API keys and translates each application status separately', () => {
    expect(normalizeStatusMetrics([
      { key: 'READY_FOR_PROCESSING', count: 1 },
      { key: 'CAUTION_REVIEW_REQUIRED', count: 1 },
    ])).toEqual([
      { key: 'READY_FOR_PROCESSING', name: 'Sẵn sàng xử lý', value: 1 },
      { key: 'CAUTION_REVIEW_REQUIRED', name: 'Cần xem xét', value: 1 },
    ]);
  });

  it('keeps an unknown backend status identifiable instead of merging it into Khác', () => {
    expect(normalizeStatusMetrics([{ key: 'WAITING_ARCHIVE', count: 2 }])).toEqual([
      { key: 'WAITING_ARCHIVE', name: 'Waiting archive', value: 2 },
    ]);
  });
});

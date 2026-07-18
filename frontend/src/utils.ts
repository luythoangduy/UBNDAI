export const statusLabels: Record<string, string> = {
  draft: 'Bản nháp',
  collecting: 'Đang chuẩn bị',
  awaiting_officer_review: 'Chờ tiếp nhận',
  in_officer_review: 'Đang thẩm tra',
  needs_citizen_update: 'Chờ bổ sung',
  escalated: 'Đã chuyển cấp',
  precheck_ready: 'Đạt tiền kiểm',
  closed: 'Đã đóng',
  ready: 'Sẵn sàng',
  manual_review_required: 'Cần xem thủ công',
  upload_pending: 'Chờ tải lên',
  rejected: 'Không hợp lệ',
};

export function humanizeStatus(value: string) {
  return statusLabels[value] ?? value.replace(/_/g, ' ');
}

export function formatBytes(value?: number) {
  if (value === undefined) return 'Không rõ dung lượng';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(value?: string) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
}

export function buildCaseQuery(search: string, status: string, sort: string, page = 1) {
  const query = new URLSearchParams({ sort, page: String(page), page_size: '20' });
  if (search.trim()) query.set('q', search.trim());
  if (status) query.set('status', status);
  return query.toString();
}

export function visibleSubmissionEntries(submission: Record<string, unknown>) {
  return Object.entries(submission).filter(([key]) => !key.startsWith('_'));
}

export function clarificationAnswerEntries(submission: Record<string, unknown>) {
  const answers = submission._answers;
  if (!answers || typeof answers !== 'object' || Array.isArray(answers)) return [];
  return Object.entries(answers as Record<string, unknown>);
}

export function formatSubmissionValue(value: unknown): string {
  if (value === true) return 'Có';
  if (value === false) return 'Không';
  if (value === undefined || value === null || value === '') return '—';
  if (Array.isArray(value)) return value.map(formatSubmissionValue).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

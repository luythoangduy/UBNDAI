export type ApplicationStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'AI_ANALYZING'
  | 'READY_FOR_PROCESSING'
  | 'CAUTION_REVIEW_REQUIRED'
  | 'IN_PROCESS'
  | 'RETURNED_TO_CITIZEN'
  | 'RESUBMITTED'
  | 'COMPLETED'
  | 'REJECTED'
  | 'ESCALATED'
  | 'CANCELLED'
  | 'CLOSED'
  | 'UNKNOWN';

export const applicationStatusLabels: Record<ApplicationStatus, string> = {
  DRAFT: 'Bản nháp',
  SUBMITTED: 'Đã nộp',
  AI_ANALYZING: 'Đang phân tích',
  READY_FOR_PROCESSING: 'Sẵn sàng xử lý',
  CAUTION_REVIEW_REQUIRED: 'Cần xem xét',
  IN_PROCESS: 'Đang xử lý',
  RETURNED_TO_CITIZEN: 'Trả lại công dân',
  RESUBMITTED: 'Đã nộp lại',
  COMPLETED: 'Đã hoàn tất',
  REJECTED: 'Không hợp lệ',
  ESCALATED: 'Đã chuyển cấp',
  CANCELLED: 'Đã hủy',
  CLOSED: 'Đã đóng',
  UNKNOWN: 'Chưa xác định',
};

export function projectApplicationStatus(internalStatus: string, hasCaution = false): ApplicationStatus {
  if (internalStatus === 'awaiting_officer_review') return hasCaution ? 'CAUTION_REVIEW_REQUIRED' : 'READY_FOR_PROCESSING';
  if (internalStatus === 'precheck_ready' || internalStatus === 'ready') return 'READY_FOR_PROCESSING';
  if (internalStatus === 'needs_citizen_update' || internalStatus === 'need_more_info') return 'RETURNED_TO_CITIZEN';
  if (internalStatus === 'in_officer_review' || internalStatus === 'processing') return 'IN_PROCESS';
  if (internalStatus === 'ocr_processing' || internalStatus === 'precheck_processing') return 'AI_ANALYZING';
  if (internalStatus === 'submitted' || internalStatus === 'submitted_for_precheck') return 'SUBMITTED';
  if (internalStatus === 'resubmitted') return 'RESUBMITTED';
  if (internalStatus === 'done' || internalStatus === 'completed') return 'COMPLETED';
  if (internalStatus === 'rejected') return 'REJECTED';
  if (internalStatus === 'escalated') return 'ESCALATED';
  if (internalStatus === 'cancelled') return 'CANCELLED';
  if (internalStatus === 'closed') return 'CLOSED';
  if (internalStatus === 'draft' || internalStatus === 'collecting') return 'DRAFT';
  return 'UNKNOWN';
}

export type ApplicationAnomaly = {
  id: string;
  code: string;
  message: string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO' | 'error' | 'warning' | 'info';
  status?: string;
  confidence?: number | null;
  field_name?: string | null;
  document_id?: string | null;
  detected_by?: string;
};

export type ApplicationSummary = {
  id: string;
  application_code: string;
  citizen_name?: string | null;
  application_type_code: string;
  application_type_name: string;
  classification_confidence?: number | null;
  status: ApplicationStatus;
  internal_status?: string;
  anomaly_count: number;
  assigned_officer_name?: string | null;
  submitted_at?: string | null;
  created_at?: string | null;
};

export type ApplicationDetail = ApplicationSummary & {
  citizen_id?: string | null;
  documents: Array<Record<string, unknown>>;
  extracted_fields: Array<Record<string, unknown>>;
  anomalies: ApplicationAnomaly[];
  events: Array<Record<string, unknown>>;
  form_data?: Record<string, unknown>;
  checklist?: Record<string, unknown>;
  version: number;
};

export type ApplicationFilters = {
  search?: string;
  status?: ApplicationStatus | '';
  applicationType?: string;
  hasAnomaly?: boolean | '';
  assignedOfficerId?: string;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
};

export function serializeApplicationFilters(filters: ApplicationFilters): string {
  const params = new URLSearchParams();
  const entries: Array<[string, string | number | boolean | undefined]> = [
    ['search', filters.search?.trim() || undefined],
    ['status', filters.status || undefined],
    ['application_type_code', filters.applicationType || undefined],
    ['has_anomaly', filters.hasAnomaly === '' ? undefined : filters.hasAnomaly],
    ['assigned_officer_id', filters.assignedOfficerId || undefined],
    ['submitted_from', filters.from || undefined],
    ['submitted_to', filters.to || undefined],
    ['page', filters.page && filters.page > 1 ? filters.page : undefined],
    ['page_size', filters.pageSize && filters.pageSize !== 20 ? filters.pageSize : undefined],
    ['sort_by', filters.sortBy || undefined],
    ['sort_order', filters.sortOrder || undefined],
  ];
  for (const [key, value] of entries) if (value !== undefined) params.set(key, String(value));
  return params.toString();
}

export type PortalRole = 'citizen' | 'officer';

export type CaseRecord = {
  id: string;
  case_code?: string;
  status: string;
  procedure_id: string;
  priority?: number;
  assigned_to?: string | null;
  form_data?: Record<string, unknown>;
  checklist?: Record<string, unknown>;
  version: number;
  current_submission_version?: number;
  created_at?: string;
  updated_at?: string;
};

export type Submission = {
  id: string;
  version: number;
  form_data: Record<string, unknown>;
  checklist_snapshot: Record<string, unknown>;
  procedure_rule_version: string;
  created_at: string;
};

export type Finding = {
  id: string;
  severity: 'error' | 'warning' | 'info';
  source: 'rule' | 'ai';
  message: string;
  suggestion?: string;
  status: 'open' | 'accepted' | 'dismissed' | 'escalated' | 'superseded';
  field_keys: string[];
  rule_id?: string;
};

export type CaseDocument = {
  id: string;
  original_filename?: string;
  document_type: string;
  content_type?: string;
  size_bytes?: number;
  ocr_status: string;
  ocr_engine?: string;
};

export type ExtractedField = {
  id: string;
  document_id: string;
  field_key: string;
  raw_value: string;
  normalized_value?: string;
  confidence: number;
  page?: number;
  bounding_box?: [number, number, number, number];
  review_status: string;
  previous_value?: string;
};

export type TimelineEvent = {
  id: string;
  event_type: string;
  created_at: string;
  actor_id: string;
};

export type CaseDetail = {
  case: CaseRecord;
  submission: Submission;
  documents: CaseDocument[];
  findings: Finding[];
  timeline: TimelineEvent[];
};

export type DashboardSummary = {
  total: number;
  awaiting_review: number;
  in_review: number;
  needs_citizen_update: number;
  document_total: number;
  document_ready: number;
  document_manual_review: number;
  document_processing: number;
  document_rejected: number;
};

export type PreprocessStep = { name: string; image: string };
export type PreprocessResult = { applied_steps: string[]; steps: PreprocessStep[] };

export type ChatCitation = { index: number; section?: string; excerpt?: string; source_url?: string };
export type ChatResponse = {
  case_id?: string;
  reply: string;
  kind: 'clarify' | 'checklist' | 'answer' | 'fallback';
  clarifying_questions?: string[];
  citations?: ChatCitation[];
};

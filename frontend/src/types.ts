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
export type ChatAction = {
  id: string;
  label: string;
  description: string;
  kind: 'send_message' | 'start_form' | 'open_url';
  value: string;
  icon: 'search' | 'checklist' | 'clock' | 'template' | 'form' | 'source';
  primary: boolean;
};
export type TemplateCitation = {
  document_number: string;
  title: string;
  issuing_authority: string;
  role: string;
  source_url: string;
  official: boolean;
  priority: number;
};
export type ChatTemplateResource = {
  template_id: string;
  title: string;
  version: string;
  source_checked_on: string;
  field_count: number;
  source_url: string;
  source_label: string;
  official_source: boolean;
  citations: TemplateCitation[];
};
export type EvidenceStep = {
  id: string;
  label: string;
  detail: string;
  status: 'ready' | 'cache_hit' | 'fallback' | 'unavailable';
  source_url?: string;
};
export type ChatCacheInfo = {
  backend: 'redis' | 'memory' | 'none';
  status: 'hit' | 'miss' | 'unavailable';
  ttl_seconds: number;
};
export type ChatExperience = {
  actions?: ChatAction[];
  templates?: ChatTemplateResource[];
  evidence?: EvidenceStep[];
  cache?: ChatCacheInfo;
};
export type ChatResponse = {
  case_id?: string;
  reply: string;
  kind: 'clarify' | 'checklist' | 'answer' | 'fallback';
  procedure_id?: string | null;
  clarifying_questions?: string[];
  citations?: ChatCitation[];
} & ChatExperience;
export type ChatStarterResponse = { reply: string } & ChatExperience;

export type ProcedureSummary = {
  id: string;
  national_code?: string | null;
  name: string;
  agency: string;
  locality_code: string;
  status: 'approved' | 'published';
  source_url?: string | null;
};

export type ProcedureRequirement = {
  code: string;
  name: string;
  condition?: string | null;
  condition_label?: string | null;
  original_required: boolean;
  copies: number;
  accepted_doc_types: string[];
  notes?: string | null;
};

export type ProcedureCapabilities = {
  chat: boolean;
  checklist: boolean;
  dynamic_form: boolean;
  ocr_autofill: boolean;
  legal_validation: boolean;
  official_draft: boolean;
  requires_human_review: boolean;
};

export type ProcedureFormField = {
  key: string;
  label: string;
  type: 'text' | 'date' | 'number' | 'select' | 'checkbox';
  required: boolean;
  options: string[];
  ocr_sources: string[];
};

export type ClarifyingQuestion = {
  key: string;
  text: string;
  answer_type: 'boolean' | 'integer' | 'text' | 'choice';
  options: string[];
  minimum?: number | null;
  maximum?: number | null;
};

export type ProcedureFormSchema = {
  procedure_id: string;
  template_id: string;
  title: string;
  fields: ProcedureFormField[];
  clarifying_questions: ClarifyingQuestion[];
};

export type DraftFieldSpec = {
  key: string;
  label: string;
  input_type: 'text' | 'date' | 'year';
  required: boolean;
  allowed_values: string[];
  description?: string | null;
};

export type DraftTemplateInfo = {
  id: string;
  procedure_id: string;
  output_name: string;
  version: string;
  source_checked_on: string;
  fields: DraftFieldSpec[];
  disclaimer: string;
  legal_sources: Array<{
    document_number: string;
    title: string;
    issuing_authority: string;
    role: string;
    source_url: string;
  }>;
};

export type GeneratedDraft = {
  id: string;
  procedure_id: string;
  template_id: string;
  output_name: string;
  rendered_text: string;
  missing_required_fields: string[];
  ready_for_review: boolean;
  warnings: string[];
};

export type DraftRevision = {
  revised_html: string;
  summary: string;
  model_used: string;
  warnings: string[];
};

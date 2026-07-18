import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ApiError, api, apiBlob, idempotency } from '../../api';
import type { CaseDetail, ExtractedField } from '../../types';
import type { ApplicationDetail } from '../../application-management-types';
import { DecisionDialog } from './DecisionDialog';

const fieldLabel = (key: string) => key.replace(/_/g, ' ').replace(/^./, (value: string) => value.toUpperCase());
const displayValue = (value: unknown) => typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—');

function DocumentViewer({ detail }: { detail: CaseDetail }) {
  const [documentId, setDocumentId] = useState(detail.documents[0]?.id ?? '');
  const fields = useQuery({ queryKey: ['document-fields', documentId], enabled: !!documentId, queryFn: () => api<ExtractedField[]>(`/officer/documents/${documentId}/fields`) });
  const preview = useQuery({ queryKey: ['document-content', documentId], enabled: !!documentId, queryFn: () => apiBlob(`/officer/documents/${documentId}/content`) });
  const previewUrl = useMemo(() => preview.data ? URL.createObjectURL(preview.data) : '', [preview.data]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  const averageConfidence = fields.data?.length ? Math.round(fields.data.reduce((sum, field) => sum + field.confidence, 0) / fields.data.length * 100) : 0;
  return <section className="am-evidence-panel" aria-label="Tài liệu và dữ liệu OCR">
    <div className="am-panel-heading"><div><span className="am-eyebrow">TÀI LIỆU GỐC</span><h2>Đối chiếu hồ sơ</h2></div><select aria-label="Chọn tài liệu" value={documentId} onChange={event => setDocumentId(event.target.value)}>{detail.documents.map(document => <option key={document.id} value={document.id}>{document.original_filename ?? document.document_type}</option>)}</select></div>
    <div className="am-document-preview">{preview.isLoading ? 'Đang mở tài liệu…' : previewUrl ? <iframe title="Bản xem trước tài liệu" src={previewUrl} /> : <p>Không thể hiển thị tài liệu. Vẫn có thể đối chiếu dữ liệu OCR bên cạnh.</p>}</div>
    <div className="am-ocr-heading"><div><span className="am-eyebrow">TRÍCH XUẤT TỰ ĐỘNG</span><h3>Dữ liệu OCR</h3></div><span className="am-confidence-pill">{averageConfidence}% tin cậy</span></div>
    <dl className="am-field-list am-ocr-list">{fields.isLoading && <div className="am-ocr-loading">Đang đọc dữ liệu trên tài liệu…</div>}{fields.data?.map(field => <div key={field.id}><dt>{fieldLabel(field.field_key)}</dt><dd><strong>{field.normalized_value || field.raw_value || '—'}</strong><small><span className={field.confidence >= .85 ? 'am-confidence-high' : 'am-confidence-low'}>{Math.round(field.confidence * 100)}%</span> độ tin cậy</small></dd></div>)}{!fields.isLoading && !fields.data?.length && <div className="am-ocr-loading">Chưa có trường OCR cho tài liệu này.</div>}</dl>
  </section>;
}

export default function ApplicationDetailPage() {
  const { applicationId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') ?? 'overview';
  const client = useQueryClient();
  const [decision, setDecision] = useState<'CONTINUE_PROCESSING' | 'RETURN_TO_CITIZEN' | null>(null);
  const [note, setNote] = useState('');
  const [toast, setToast] = useState('');
  const management = useQuery({ queryKey: ['application', applicationId], queryFn: () => api<ApplicationDetail>(`/applications/${applicationId}`) });
  const legacy = useQuery({ queryKey: ['application-workspace', applicationId], queryFn: () => api<CaseDetail>(`/officer/cases/${applicationId}`) });
  const submit = useMutation({ mutationFn: () => api(`/applications/${applicationId}/decisions`, { method: 'POST', body: JSON.stringify({ decision, note: note.trim(), citizen_message: note.trim(), anomaly_ids: decision === 'RETURN_TO_CITIZEN' ? management.data?.anomalies.map(item => item.id) ?? [] : [], expected_version: management.data?.version, idempotency_key: idempotency() }) }), onSuccess: async () => { setDecision(null); setNote(''); setToast('Đã lưu quyết định xử lý.'); await Promise.all([client.invalidateQueries({ queryKey: ['application', applicationId] }), client.invalidateQueries({ queryKey: ['application-workspace', applicationId] }), client.invalidateQueries({ queryKey: ['applications'] })]); }, onError: error => { if (error instanceof ApiError && error.status === 409) client.invalidateQueries({ queryKey: ['application', applicationId] }); } });
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 4000); return () => window.clearTimeout(timer); }, [toast]);
  if (management.isLoading || legacy.isLoading) return <div className="officer-container am-loading" aria-live="polite">Đang tải không gian xử lý…</div>;
  if (management.error || legacy.error || !management.data || !legacy.data) return <div className="officer-container"><div className="am-error" role="alert">Không thể tải hồ sơ. <Link to="/officer/applications">Quay lại danh sách</Link></div></div>;
  const app = management.data, detail = legacy.data;
  const tabs = [['overview', 'Thông tin chung'], ['documents', `Tài liệu (${detail.documents.length})`], ['fields', 'Thông tin trích xuất'], ['anomalies', `Cảnh báo (${app.anomalies.length})`], ['history', 'Lịch sử']];
  return <>
    <header className="officer-topbar"><div><Link to="/officer/applications">Hồ sơ</Link><h1>{app.application_code}</h1><p>{app.application_type_name}</p></div><span className="am-status am-status-warning">{app.status}</span></header>
    <div className="officer-container am-detail-container"><nav className="am-tabs" aria-label="Nội dung hồ sơ">{tabs.map(([id, label]) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setParams(id === 'overview' ? {} : { tab: id })}>{label}</button>)}</nav>
      <div className="am-review-grid">
        <DocumentViewer detail={detail} />
        <section className="am-form-panel"><div className="am-panel-heading"><h2>{tab === 'history' ? 'Lịch sử xử lý' : 'Nội dung đơn'}</h2></div>{tab === 'history' ? <ol className="timeline">{detail.timeline.map(event => <li key={event.id}><strong>{fieldLabel(event.event_type)}</strong><small>{new Date(event.created_at).toLocaleString('vi-VN')}</small></li>)}</ol> : <dl className="am-data-list">{Object.entries(detail.submission.form_data).map(([key, value]) => <div key={key}><dt>{fieldLabel(key)}</dt><dd>{displayValue(value)}</dd></div>)}</dl>}</section>
        <aside className="am-caution-rail"><h2>Cảnh báo ({app.anomalies.length})</h2>{app.anomalies.length ? <ul>{app.anomalies.map(item => <li key={item.id} className={`severity-${item.severity.toLowerCase()}`}><strong>{item.code}</strong><p>{item.message}</p>{item.confidence != null && <small>Độ tin cậy {Math.round(item.confidence * 100)}%</small>}</li>)}</ul> : <div className="am-empty"><p>Không phát hiện cảnh báo.</p></div>}<div className="am-action-stack"><button className="am-button" onClick={() => setDecision('CONTINUE_PROCESSING')}>Tiếp tục xử lý</button><button className="am-button am-button-danger" disabled={!app.anomalies.length} onClick={() => setDecision('RETURN_TO_CITIZEN')}>Trả lại cho công dân</button></div></aside>
      </div>
    </div>
    {toast && <div className="am-toast" role="status">{toast}</div>}
    {decision && <DecisionDialog title={decision === 'CONTINUE_PROCESSING' ? 'Vẫn tiếp tục xử lý hồ sơ' : 'Trả lại hồ sơ cho công dân'} note={note} setNote={setNote} busy={submit.isPending} valid={decision === 'CONTINUE_PROCESSING' ? note.trim().length >= 10 : !!note.trim() && app.anomalies.length > 0} error={submit.error instanceof ApiError && submit.error.status === 409 ? 'Hồ sơ vừa được cập nhật. Dữ liệu mới đã được tải lại.' : submit.error ? 'Không thể lưu quyết định. Vui lòng thử lại.' : undefined} onClose={() => { setDecision(null); setNote(''); }} onConfirm={() => submit.mutate()} />}
  </>;
}

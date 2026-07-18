import { useEffect, useState } from 'react';
import { api, apiBlob } from '../../api';
import type { CaseDetail, CaseDocument, ExtractedField, Finding } from '../../types';
import { formatBytes, formatDate, humanizeStatus } from '../../utils';
import { procedureNames } from './procedureCatalog';

const activeFindingStatuses = new Set<Finding['status']>(['open', 'accepted', 'escalated']);
const isActiveFinding = (finding: Finding) => activeFindingStatuses.has(finding.status);

function Status({ value }: { value: string }) {
  return <span className={`status status-${value}`}>{humanizeStatus(value)}</span>;
}

function Empty({ title, text }: { title: string; text: string }) {
  return <div className="empty-state"><span>◇</span><h3>{title}</h3><p>{text}</p></div>;
}

export type ReviewWorkspaceProps = {
  detail: CaseDetail;
  procedureName?: string;
  onRefresh: () => Promise<void>;
  onError: (cause: unknown) => void;
};

export function ReviewWorkspace({ detail, procedureName, onRefresh, onError }: ReviewWorkspaceProps) {
  const [documentId, setDocumentId] = useState(detail.documents[0]?.id ?? '');
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [previewUrl, setPreviewUrl] = useState('');
  const [previewError, setPreviewError] = useState('');
  const [busy, setBusy] = useState('');
  const [supplement, setSupplement] = useState('');
  const [selectedFindings, setSelectedFindings] = useState<string[]>(detail.findings.filter(isActiveFinding).map(item => item.id));
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const activeDocument = detail.documents.find(item => item.id === documentId);

  useEffect(() => {
    setDocumentId(detail.documents[0]?.id ?? '');
    setSelectedFindings(detail.findings.filter(isActiveFinding).map(item => item.id));
  }, [detail.case.id]);

  useEffect(() => {
    if (!documentId) {
      setFields([]);
      setPreviewUrl('');
      return;
    }
    let objectUrl = '';
    api<ExtractedField[]>(`/officer/documents/${documentId}/fields`).then(setFields).catch(onError);
    apiBlob(`/officer/documents/${documentId}/content`)
      .then(blob => {
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
        setPreviewError('');
      })
      .catch(cause => {
        setPreviewUrl('');
        setPreviewError((cause as Error).message);
      });
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  const action = async (name: string, work: () => Promise<unknown>) => {
    setBusy(name);
    try {
      await work();
      await onRefresh();
    } catch (cause) {
      onError(cause);
    } finally {
      setBusy('');
    }
  };
  const claim = () => action('claim', () => api(`/officer/cases/${detail.case.id}/claim`, { method: 'POST' }));
  const decide = (finding: Finding, decision: 'accept' | 'dismiss' | 'escalate') => action(`${decision}-${finding.id}`, () => api(`/officer/findings/${finding.id}/${decision}`, {
    method: 'POST',
    body: decision === 'accept' ? undefined : JSON.stringify({ reason: reasons[finding.id] || (decision === 'dismiss' ? 'Đã đối chiếu tài liệu gốc.' : 'Cần ý kiến chuyên môn.') }),
  }));
  const transition = (target_status: string) => action(target_status, () => api(`/officer/cases/${detail.case.id}/transition`, { method: 'POST', body: JSON.stringify({ target_status }) }));
  const requestSupplement = () => action('supplement', () => api(`/officer/cases/${detail.case.id}/supplement-requests`, { method: 'POST', body: JSON.stringify({ public_message: supplement, finding_ids: selectedFindings }) }));
  const rerun = () => action('rerun', () => api(`/officer/cases/${detail.case.id}/rerun-validation`, { method: 'POST' }));

  return <div className="review-workspace">
    <div className="review-header">
      <div>
        <div className="case-code"><span>{detail.case.case_code}</span><Status value={detail.case.status}/></div>
        <h2>{procedureName ?? procedureNames[detail.case.procedure_id] ?? detail.case.procedure_id}</h2>
        <p>Phiên bản hồ sơ {detail.submission.version} · Bộ quy tắc {detail.submission.procedure_rule_version}</p>
      </div>
      <div className="review-header-actions">
        {detail.case.status === 'awaiting_officer_review' && <button className="primary" onClick={claim} disabled={!!busy}>{busy === 'claim' ? 'Đang nhận…' : 'Nhận xử lý'}</button>}
        <button className="icon-button" aria-label="Làm mới hồ sơ" onClick={onRefresh}>↻</button>
      </div>
    </div>
    <div className="progress-line">
      <span className="done">Đã nộp</span><span className="done">Tiền kiểm AI</span>
      <span className={detail.case.status === 'awaiting_officer_review' ? 'current' : 'done'}>Tiếp nhận</span>
      <span className={detail.case.status === 'in_officer_review' ? 'current' : ''}>Thẩm tra</span>
      <span className={detail.case.status === 'precheck_ready' ? 'done' : ''}>Hoàn tất</span>
    </div>
    <div className="review-columns">
      <EvidencePanel documents={detail.documents} activeId={documentId} onSelect={setDocumentId} active={activeDocument} previewUrl={previewUrl} previewError={previewError} fields={fields}/>
      <DataPanel submission={detail.submission.form_data} fields={fields} editable={detail.case.status === 'in_officer_review'} onSaved={async () => { if (documentId) setFields(await api<ExtractedField[]>(`/officer/documents/${documentId}/fields`)); }} onError={onError}/>
      <FindingsPanel findings={detail.findings} busy={busy} reasons={reasons} setReasons={setReasons} onDecide={decide}/>
    </div>
    <div className="review-bottom">
      <details><summary>Lịch sử xử lý <span>{detail.timeline.length}</span></summary><ol className="timeline">{detail.timeline.length ? detail.timeline.map(item => <li key={item.id}><i/><div><b>{humanizeStatus(item.event_type)}</b><small>{formatDate(item.created_at)} · {item.actor_id}</small></div></li>) : <li>Chưa có hoạt động.</li>}</ol></details>
      {detail.case.status === 'in_officer_review' && <section className="decision-box">
        <div><span className="eyebrow">HÀNH ĐỘNG XỬ LÝ</span><h3>Yêu cầu công dân bổ sung</h3></div>
        <textarea value={supplement} onChange={event => setSupplement(event.target.value)} maxLength={5000} placeholder="Mô tả rõ thông tin hoặc giấy tờ cần bổ sung…"/>
        <div className="finding-selector">{detail.findings.filter(isActiveFinding).map(item => <label key={item.id}><input type="checkbox" checked={selectedFindings.includes(item.id)} onChange={() => setSelectedFindings(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id])}/><span>{item.message}</span></label>)}</div>
        <div className="decision-actions"><button className="warning-button" disabled={!supplement.trim() || !selectedFindings.length || !!busy} onClick={requestSupplement}>Yêu cầu bổ sung</button><button className="ghost" disabled={!!busy} onClick={() => transition('escalated')}>Chuyển chuyên môn</button><button className="ghost" disabled={!!busy} onClick={rerun}>{busy === 'rerun' ? 'Đang kiểm tra…' : 'Chạy lại kiểm tra'}</button><button className="success-button" disabled={!!busy || detail.findings.some(item => item.severity === 'error' && isActiveFinding(item))} onClick={() => transition('precheck_ready')}>Đạt tiền kiểm</button></div>
      </section>}
    </div>
  </div>;
}

function EvidencePanel({ documents, activeId, onSelect, active, previewUrl, previewError, fields }: { documents: CaseDocument[]; activeId: string; onSelect: (id: string) => void; active?: CaseDocument; previewUrl: string; previewError: string; fields?: ExtractedField[] }) {
  return <section className="review-panel evidence-panel">
    <div className="column-heading"><span>TÀI LIỆU & CĂN CỨ</span><b>{documents.length}</b></div>
    <div className="document-tabs">{documents.map(item => <button key={item.id} className={activeId === item.id ? 'active' : ''} onClick={() => onSelect(item.id)}><span>▤</span><div><b>{item.original_filename ?? item.document_type}</b><small>{formatBytes(item.size_bytes)}</small></div><Status value={item.ocr_status}/></button>)}</div>
    {active ? <div className="document-viewer">
      {previewUrl ? active.content_type === 'application/pdf' ? <iframe title={active.original_filename ?? 'Tài liệu'} src={previewUrl}/> : <div className="image-preview-container"><img alt={active.original_filename ?? 'Tài liệu'} src={previewUrl}/>{fields?.map(field => field.bounding_box && <div key={field.id} className="bbox-overlay" style={{ left: `${field.bounding_box[0] * 100}%`, top: `${field.bounding_box[1] * 100}%`, width: `${field.bounding_box[2] * 100}%`, height: `${field.bounding_box[3] * 100}%` }} title={`${field.field_key}: ${field.normalized_value || field.raw_value}`}/>)}</div> : <div className="document-placeholder"><div className="paper-lines"><i/><i/><i/><i/><i/></div><span>▧</span><b>Chưa có bản xem trước</b><small>{previewError || 'Tài liệu được bảo vệ và chỉ mở khi được cấp quyền.'}</small></div>}
      <div className="viewer-meta"><span>{active.ocr_engine ? `OCR: ${active.ocr_engine}` : 'Chưa có OCR'}</span><Status value={active.ocr_status}/></div>
    </div> : <Empty title="Chưa có tài liệu" text="Hồ sơ này chưa đính kèm giấy tờ."/>}
  </section>;
}

function DataPanel({ submission, fields, editable, onSaved, onError }: { submission: Record<string, unknown>; fields: ExtractedField[]; editable: boolean; onSaved: () => Promise<void>; onError: (cause: unknown) => void }) {
  const [editing, setEditing] = useState<string>();
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const save = async (field: ExtractedField) => {
    setBusy(true);
    try {
      await api(`/officer/extracted-fields/${field.id}`, { method: 'PATCH', body: JSON.stringify({ normalized_value: value, reason: 'Cán bộ đối chiếu tài liệu gốc' }) });
      setEditing(undefined);
      await onSaved();
    } catch (cause) {
      onError(cause);
    } finally {
      setBusy(false);
    }
  };
  const rows = Object.entries(submission);
  return <section className="review-panel data-panel">
    <div className="column-heading"><span>DỮ LIỆU CÓ CẤU TRÚC</span><b>{rows.length + fields.length}</b></div>
    <div className="data-section"><h3>Thông tin người khai</h3>{rows.length ? rows.map(([key, item]) => <div className="data-row" key={key}><span>{humanizeStatus(key)}</span><strong>{String(item || '—')}</strong><small className="verified">✓ Đã khai</small></div>) : <p className="empty">Không có dữ liệu biểu mẫu.</p>}</div>
    <div className="data-section"><div className="section-title"><h3>Kết quả OCR</h3>{fields.some(item => item.review_status === 'needs_human_review') && <span className="needs-review">Cần xác minh</span>}</div>{fields.length ? fields.map(field => <div className={`ocr-row ${field.review_status === 'needs_human_review' ? 'low-confidence' : ''}`} key={field.id}><div><span>{humanizeStatus(field.field_key)}</span><small>Độ tin cậy {Math.round(field.confidence * 100)}%</small></div>{editing === field.id ? <div className="edit-field"><input value={value} onChange={event => setValue(event.target.value)} autoFocus/><button onClick={() => save(field)} disabled={busy}>Lưu</button><button className="text-button" onClick={() => setEditing(undefined)}>Hủy</button></div> : <div className="field-value"><strong>{field.normalized_value || field.raw_value || '—'}</strong>{editable && <button aria-label={`Sửa ${field.field_key}`} onClick={() => { setEditing(field.id); setValue(field.normalized_value || field.raw_value); }}>✎</button>}</div>}</div>) : <p className="empty">Chọn tài liệu có dữ liệu OCR để xem.</p>}</div>
  </section>;
}

function FindingsPanel({ findings, busy, reasons, setReasons, onDecide }: { findings: Finding[]; busy: string; reasons: Record<string, string>; setReasons: React.Dispatch<React.SetStateAction<Record<string, string>>>; onDecide: (finding: Finding, decision: 'accept' | 'dismiss' | 'escalate') => void }) {
  const openCount = findings.filter(isActiveFinding).length;
  return <section className="review-panel findings-panel">
    <div className="column-heading"><span>KẾT QUẢ KIỂM TRA</span><b>{openCount}</b></div>
    <div className="finding-summary"><span><i className="red"/>{findings.filter(item => item.severity === 'error' && isActiveFinding(item)).length} lỗi</span><span><i className="gold"/>{findings.filter(item => item.severity === 'warning' && isActiveFinding(item)).length} cảnh báo</span></div>
    {findings.length ? findings.map(item => <article className={`finding-card ${item.severity} ${!isActiveFinding(item) ? 'resolved' : ''}`} key={item.id}><div className="finding-title"><span>{item.severity === 'error' ? '!' : item.severity === 'warning' ? '△' : 'i'}</span><div><b>{item.severity === 'error' ? 'Cần xử lý' : item.severity === 'warning' ? 'Cần lưu ý' : 'Thông tin'}</b><small>{item.source === 'rule' ? 'Quy tắc nghiệp vụ' : 'Gợi ý AI'}</small></div><Status value={item.status}/></div><p>{item.message}</p>{item.suggestion && <small className="suggestion-text">Gợi ý: {item.suggestion}</small>}{item.status === 'open' && <><input className="reason-input" value={reasons[item.id] ?? ''} onChange={event => setReasons(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Lý do xử lý (nếu cần)"/><div className="finding-actions"><button onClick={() => onDecide(item, 'accept')} disabled={!!busy}>Ghi nhận lỗi</button><button onClick={() => onDecide(item, 'dismiss')} disabled={!!busy}>Bỏ qua có lý do</button><button onClick={() => onDecide(item, 'escalate')} disabled={!!busy}>Chuyển cấp</button></div></>}</article>) : <Empty title="Không có cảnh báo" text="Chưa phát hiện vấn đề trong phiên bản hiện tại."/>}
  </section>;
}

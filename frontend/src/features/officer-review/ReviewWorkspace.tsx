import { useEffect, useState } from 'react';
import { ArrowClockwise, CheckCircle, FileText, Info, NotePencil, Tray, Warning, XCircle } from '@phosphor-icons/react';
import { api, apiBlob } from '../../api';
import type { CaseDetail, CaseDocument, ExtractedField, Finding } from '../../types';
import { clarificationAnswerEntries, formatBytes, formatDate, formatSubmissionValue, humanizeStatus, visibleSubmissionEntries } from '../../utils';
import { procedureNames } from './procedureCatalog';

const activeFindingStatuses = new Set<Finding['status']>(['open', 'accepted', 'escalated']);
const isActiveFinding = (finding: Finding) => activeFindingStatuses.has(finding.status);

function Status({ value }: { value: string }) {
  return <span className={`status status-${value}`}>{humanizeStatus(value)}</span>;
}

function Empty({ title, text }: { title: string; text: string }) {
  return <div className="empty-state"><Tray size={30} weight="duotone" aria-hidden="true"/><h3>{title}</h3><p>{text}</p></div>;
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
        <p><span>Phiên bản hồ sơ {detail.submission.version}</span><span>Bộ quy tắc {detail.submission.procedure_rule_version}</span></p>
      </div>
      <div className="review-header-actions">
        {detail.case.status === 'awaiting_officer_review' && <button className="primary" onClick={claim} disabled={!!busy}>{busy === 'claim' ? 'Đang nhận…' : 'Nhận xử lý'}</button>}
        <button className="icon-button" type="button" aria-label="Làm mới hồ sơ" onClick={onRefresh}><ArrowClockwise size={20} aria-hidden="true"/></button>
      </div>
    </div>
    <ol className="progress-line" aria-label="Tiến trình xử lý hồ sơ">
      <li className="done"><CheckCircle aria-hidden="true"/>Đã nộp</li><li className="done"><CheckCircle aria-hidden="true"/>Tiền kiểm AI</li>
      <li className={detail.case.status === 'awaiting_officer_review' ? 'current' : 'done'}>Tiếp nhận</li>
      <li className={detail.case.status === 'in_officer_review' ? 'current' : ''}>Thẩm tra</li>
      <li className={detail.case.status === 'precheck_ready' ? 'done' : ''}>Hoàn tất</li>
    </ol>
    <div className="review-columns">
      <EvidencePanel documents={detail.documents} activeId={documentId} onSelect={setDocumentId} active={activeDocument} previewUrl={previewUrl} previewError={previewError} fields={fields}/>
      <DataPanel submission={detail.submission.form_data} fields={fields} editable={detail.case.status === 'in_officer_review'} onSaved={async () => { if (documentId) setFields(await api<ExtractedField[]>(`/officer/documents/${documentId}/fields`)); }} onError={onError}/>
      <FindingsPanel findings={detail.findings} busy={busy} reasons={reasons} setReasons={setReasons} onDecide={decide}/>
    </div>
    <div className="review-bottom">
      <details><summary>Lịch sử xử lý <span>{detail.timeline.length}</span></summary><ol className="timeline">{detail.timeline.length ? detail.timeline.map(item => <li key={item.id}><i/><div><b>{humanizeStatus(item.event_type)}</b><small className="timeline-meta"><span>{formatDate(item.created_at)}</span><span>{item.actor_id}</span></small></div></li>) : <li>Chưa có hoạt động.</li>}</ol></details>
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
  return <section className="review-panel evidence-panel" aria-labelledby="evidence-panel-title">
    <div className="column-heading"><h3 id="evidence-panel-title">Tài liệu và căn cứ</h3><b aria-label={`${documents.length} tài liệu`}>{documents.length}</b></div>
    <div className="document-tabs" role="list">{documents.map(item => <button type="button" role="listitem" key={item.id} className={activeId === item.id ? 'active' : ''} aria-pressed={activeId === item.id} onClick={() => onSelect(item.id)}><FileText size={19} aria-hidden="true"/><div><b>{item.original_filename ?? item.document_type}</b><small>{formatBytes(item.size_bytes)}</small></div><Status value={item.ocr_status}/></button>)}</div>
    {active ? <div className="document-viewer">
      {previewUrl ? active.content_type === 'application/pdf' ? <iframe title={active.original_filename ?? 'Tài liệu'} src={previewUrl}/> : <div className="image-preview-container"><img alt={active.original_filename ?? 'Tài liệu'} src={previewUrl}/>{fields?.map(field => field.bounding_box && <div key={field.id} className="bbox-overlay" style={{ left: `${field.bounding_box[0] * 100}%`, top: `${field.bounding_box[1] * 100}%`, width: `${field.bounding_box[2] * 100}%`, height: `${field.bounding_box[3] * 100}%` }} title={`${field.field_key}: ${field.normalized_value || field.raw_value}`}/>)}</div> : <div className="document-placeholder"><div className="paper-lines"><i/><i/><i/><i/><i/></div><FileText size={30} aria-hidden="true"/><b>Chưa có bản xem trước</b><small>{previewError || 'Tài liệu được bảo vệ và chỉ mở khi được cấp quyền.'}</small></div>}
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
  const rows = visibleSubmissionEntries(submission);
  const answerRows = clarificationAnswerEntries(submission);
  return <section className="review-panel data-panel" aria-labelledby="data-panel-title">
    <div className="column-heading"><h3 id="data-panel-title">Dữ liệu có cấu trúc</h3><b>{rows.length + answerRows.length + fields.length}</b></div>
    <div className="data-section"><h3>Thông tin người khai</h3>{rows.length ? rows.map(([key, item]) => <div className="data-row" key={key}><span>{humanizeStatus(key)}</span><strong>{formatSubmissionValue(item)}</strong><small className="verified"><CheckCircle aria-hidden="true"/> Đã khai</small></div>) : <p className="empty">Không có dữ liệu biểu mẫu.</p>}</div>
    {answerRows.length > 0 && <div className="data-section"><h3>Thông tin xác định trường hợp</h3>{answerRows.map(([key, item]) => <div className="data-row" key={key}><span>{humanizeStatus(key)}</span><strong>{formatSubmissionValue(item)}</strong><small className="verified"><CheckCircle aria-hidden="true"/> Đã áp dụng</small></div>)}</div>}
    <div className="data-section"><div className="section-title"><h3>Kết quả OCR</h3>{fields.some(item => item.review_status === 'needs_human_review') && <span className="needs-review">Cần xác minh</span>}</div>{fields.length ? fields.map(field => <div className={`ocr-row ${field.review_status === 'needs_human_review' ? 'low-confidence' : ''}`} key={field.id}><div><span>{humanizeStatus(field.field_key)}</span><small>Độ tin cậy {Math.round(field.confidence * 100)}%</small></div>{editing === field.id ? <div className="edit-field"><input aria-label={`Giá trị ${field.field_key}`} value={value} onChange={event => setValue(event.target.value)} autoFocus/><button type="button" onClick={() => save(field)} disabled={busy}>Lưu</button><button type="button" className="text-button" onClick={() => setEditing(undefined)}>Hủy</button></div> : <div className="field-value"><strong>{field.normalized_value || field.raw_value || 'Chưa nhận dạng'}</strong>{editable && <button type="button" aria-label={`Sửa ${field.field_key}`} onClick={() => { setEditing(field.id); setValue(field.normalized_value || field.raw_value); }}><NotePencil size={18} aria-hidden="true"/></button>}</div>}</div>) : <p className="empty">Chọn tài liệu có dữ liệu OCR để xem.</p>}</div>
  </section>;
}

function FindingsPanel({ findings, busy, reasons, setReasons, onDecide }: { findings: Finding[]; busy: string; reasons: Record<string, string>; setReasons: React.Dispatch<React.SetStateAction<Record<string, string>>>; onDecide: (finding: Finding, decision: 'accept' | 'dismiss' | 'escalate') => void }) {
  const openCount = findings.filter(isActiveFinding).length;
  return <section className="review-panel findings-panel" aria-labelledby="findings-panel-title">
    <div className="column-heading"><h3 id="findings-panel-title">Kết quả kiểm tra</h3><b>{openCount}</b></div>
    <div className="finding-summary"><span><i className="red"/>{findings.filter(item => item.severity === 'error' && isActiveFinding(item)).length} lỗi</span><span><i className="gold"/>{findings.filter(item => item.severity === 'warning' && isActiveFinding(item)).length} cảnh báo</span></div>
    {findings.length ? findings.map(item => { const FindingIcon = item.severity === 'error' ? XCircle : item.severity === 'warning' ? Warning : Info; return <article className={`finding-card ${item.severity} ${!isActiveFinding(item) ? 'resolved' : ''}`} key={item.id}><div className="finding-title"><FindingIcon size={22} weight="fill" aria-hidden="true"/><div><b>{item.severity === 'error' ? 'Cần xử lý' : item.severity === 'warning' ? 'Cần lưu ý' : 'Thông tin'}</b><small>{item.source === 'rule' ? 'Quy tắc nghiệp vụ' : 'Gợi ý AI'}</small></div><Status value={item.status}/></div><p>{item.message}</p>{item.suggestion && <small className="suggestion-text">Gợi ý: {item.suggestion}</small>}{item.status === 'open' && <><input aria-label={`Lý do xử lý: ${item.message}`} className="reason-input" value={reasons[item.id] ?? ''} onChange={event => setReasons(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Lý do xử lý (nếu cần)"/><div className="finding-actions"><button type="button" onClick={() => onDecide(item, 'accept')} disabled={!!busy}>Ghi nhận lỗi</button><button type="button" onClick={() => onDecide(item, 'dismiss')} disabled={!!busy}>Bỏ qua có lý do</button><button type="button" onClick={() => onDecide(item, 'escalate')} disabled={!!busy}>Chuyển cấp</button></div></>}</article>; }) : <Empty title="Không có cảnh báo" text="Chưa phát hiện vấn đề trong phiên bản hiện tại."/>}
  </section>;
}

import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MessageCircle, X, FileText, Download, Check, Bold, Italic, Strikethrough, List as ListIcon, Printer } from 'lucide-react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { api, apiBlob, ApiError, idempotency, setToken, token } from './api';
import type { CaseDetail, CaseDocument, CaseRecord, ChatAction, ChatExperience, ChatResponse, ChatStarterResponse, DashboardSummary, ExtractedField, Finding, PortalRole, PreprocessResult, PreprocessStep, ProcedureCapabilities, ProcedureFormSchema, ProcedureSummary } from './types';
import { buildCaseQuery, formatBytes, formatDate, humanizeStatus } from './utils';
import './styles.css';

const procedureNames: Record<string, string> = {};
const rememberProcedureNames = (items: ProcedureSummary[]) => items.forEach(item => { procedureNames[item.id] = item.name; });
const activeFindingStatuses = new Set<Finding['status']>(['open', 'accepted', 'escalated']);
const isActiveFinding = (finding: Finding) => activeFindingStatuses.has(finding.status);

function Brand() {
  return <a className="brand" href="/citizen" aria-label="Trang chủ UBNDAI"><span className="brand-mark">AI</span><span><strong>UBNDAI</strong><small>Trợ lý thủ tục hành chính</small></span></a>;
}

function Shell({ children, role }: { children: React.ReactNode; role: PortalRole }) {
  return <div className="app-shell"><header className="topbar"><Brand/><nav aria-label="Điều hướng chính"><a className={role === 'citizen' ? 'active' : ''} href="/citizen">Dành cho công dân</a><a className={role === 'officer' ? 'active' : ''} href="/officer">Cổng cán bộ</a></nav><span className="secure-label">Kết nối bảo mật</span></header>{children}<footer><span>© 2026 UBNDAI</span><span>Hệ thống hỗ trợ tiền kiểm, không thay thế quyết định của cơ quan có thẩm quyền.</span></footer></div>;
}

function Login({ role, onSuccess }: { role: PortalRole; onSuccess: () => void }) {
  const [username, setUsername] = useState(role === 'citizen' ? 'citizen.demo' : 'officer.demo');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const result = await api<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
      setToken(result.access_token, role); onSuccess();
    } catch (cause) { setError((cause as Error).message); } finally { setBusy(false); }
  };
  return <Shell role={role}><main className="login-page"><section className="login-story"><span className="eyebrow">DỊCH VỤ CÔNG THÔNG MINH</span><h1>{role === 'citizen' ? 'Chuẩn bị hồ sơ đúng ngay từ lần đầu.' : 'Một không gian làm việc, toàn bộ căn cứ cần thiết.'}</h1><p>{role === 'citizen' ? 'Được hướng dẫn từng bước, kiểm tra giấy tờ và theo dõi hồ sơ minh bạch.' : 'Tiếp nhận, đối chiếu OCR, xử lý cảnh báo và lưu vết mọi quyết định.'}</p><div className="trust-row"><span>✓ Dữ liệu riêng tư</span><span>✓ Có căn cứ</span><span>✓ Có người kiểm tra</span></div></section><form className="login-card" onSubmit={submit}><div className="login-icon">{role === 'citizen' ? 'CN' : 'CB'}</div><span className="eyebrow">{role === 'citizen' ? 'CỔNG CÔNG DÂN' : 'DÀNH CHO CÁN BỘ'}</span><h2>Đăng nhập hệ thống</h2><p className="muted">Sử dụng tài khoản được cấp để tiếp tục.</p><label>Tên đăng nhập<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} /></label><label>Mật khẩu<input autoComplete="current-password" type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Nhập mật khẩu" /></label>{error && <div className="alert error" role="alert">{error}</div>}<button className="primary wide" disabled={busy}>{busy ? 'Đang xác thực…' : 'Đăng nhập'}</button><small className="demo-hint">Tài khoản demo dùng mật khẩu <code>ChangeMe123!</code></small></form></main></Shell>;
}

type ChatMessage = { role: 'user' | 'assistant'; text: string; response?: ChatExperience & Partial<ChatResponse> };
function CitizenAssistant({ activeCaseId, onChecklist, onStartProcedure, selectedContext }: { activeCaseId?: string; onChecklist?: (caseId: string) => void; onStartProcedure?: (procedureId: string) => void; selectedContext?: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: 'Đang kết nối kho thủ tục và nguồn chính thức…' }]);
  const [message, setMessage] = useState(''); const [caseId, setCaseId] = useState<string | undefined>(activeCaseId); const [busy, setBusy] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  useEffect(() => { if (activeCaseId) setCaseId(activeCaseId); }, [activeCaseId]);
  useEffect(() => {
    api<ChatStarterResponse>('/chat/starter')
      .then(response => setMessages([{ role: 'assistant', text: response.reply, response }]))
      .catch(() => setMessages([{ role: 'assistant', text: 'Xin chào! Bạn cần thực hiện thủ tục gì? Hãy mô tả bằng lời của bạn.' }]));
  }, []);
  const submitMessage = async (rawValue: string) => {
    const value = rawValue.trim(); if (!value || busy) return;
    setMessages(current => [...current, { role: 'user', text: value }]); setMessage(''); setBusy(true); setStreamedText('');
    try {
      const payloadMessage = selectedContext ? `${value}\n\n[Ngữ cảnh đang chọn]: "${selectedContext}"` : value;
      const response = await api<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ message: payloadMessage, ...(caseId ? { case_id: caseId } : {}) }) });
      setCaseId(response.case_id ?? caseId); 
      setBusy(false);
      
      let currentText = '';
      const fullText = response.reply;
      const interval = setInterval(() => {
        if (currentText.length < fullText.length) {
          currentText = fullText.slice(0, currentText.length + 3);
          setStreamedText(currentText);
        } else {
          clearInterval(interval);
          setStreamedText('');
          setMessages(current => [...current, { role: 'assistant', text: fullText, response }]);
          if (response.kind === 'checklist' && onChecklist && response.case_id) onChecklist(response.case_id);
        }
      }, 10);
    } catch (cause) { setBusy(false); setMessages(current => [...current, { role: 'assistant', text: `Chưa thể kết nối trợ lý: ${(cause as Error).message}` }]); }
  };
  const send = (event: FormEvent) => { event.preventDefault(); void submitMessage(message); };
  const runAction = (action: ChatAction) => {
    if (action.kind === 'send_message') void submitMessage(action.value);
    else if (action.kind === 'start_form') onStartProcedure?.(action.value);
    else window.open(action.value, '_blank', 'noopener,noreferrer');
  };
  const iconFor = (icon: ChatAction['icon']) => ({ search: '⌕', checklist: '✓', clock: '◷', template: '▤', form: '✦', source: '↗' }[icon]);
  return (
    <div className={`chat-widget-container ${isOpen ? 'open' : ''}`}>
      {!isOpen && (
        <button className="fab-button" onClick={() => setIsOpen(true)}>
          <MessageCircle />
        </button>
      )}
      {isOpen && (
        <section className="assistant-card floating">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">TRỢ LÝ AI</span>
              <h2>Hỏi đáp thủ tục</h2>
            </div>
            <div className="actions">
              <span className="online"><i/></span>
              <button className="close-btn" onClick={() => setIsOpen(false)}><X size={16} /></button>
            </div>
          </div>
          <div className="chat-log" aria-live="polite">
            {messages.map((item, index) => <article key={index} className={`bubble ${item.role}`}><span>{item.role === 'assistant' ? 'AI' : 'Bạn'}</span><div><p>{item.text}</p>{!!item.response?.evidence?.length && <div className="source-trace"><div className="trace-heading"><b>Đã kiểm chứng nguồn</b>{item.response.cache && <small className={`cache-badge ${item.response.cache.status}`}>{item.response.cache.backend === 'redis' ? 'Redis' : 'Cache'} · {item.response.cache.status === 'hit' ? 'HIT' : 'MISS'}</small>}</div>{item.response.evidence.map(step => <a key={`${step.id}-${step.detail}`} className={`trace-step ${step.status}`} href={step.source_url || undefined} target={step.source_url ? '_blank' : undefined} rel="noreferrer"><i>{step.status === 'ready' || step.status === 'cache_hit' ? '✓' : '!'}</i><span><b>{step.label}</b><small>{step.detail}</small></span></a>)}</div>}{!!item.response?.actions?.length && <div className="chat-actions">{item.response.actions.map(action => <button key={action.id} className={action.primary ? 'featured' : ''} onClick={() => runAction(action)} disabled={busy}><i>{iconFor(action.icon)}</i><span><b>{action.label}</b><small>{action.description}</small></span></button>)}</div>}{!!item.response?.templates?.length && <div className="template-results"><div className="template-heading"><b>Biểu mẫu tìm thấy</b><small>có nguồn ban hành</small></div>{item.response.templates.map(template => <article key={template.template_id} className="template-card"><div><span className={template.official_source ? 'official-mark' : 'source-mark'}>{template.official_source ? '✓ NGUỒN CHÍNH PHỦ' : 'NGUỒN THAM KHẢO'}</span><h4>{template.title}</h4><p>{template.field_count ? `${template.field_count} trường · ` : ''}{template.source_label}</p></div><a href={template.source_url} target="_blank" rel="noreferrer">Xem mẫu ↗</a><details><summary>{template.citations.length} căn cứ nguồn</summary>{template.citations.map(source => <a key={`${source.document_number}-${source.source_url}`} href={source.source_url} target="_blank" rel="noreferrer"><b>{source.document_number}</b><span>{source.issuing_authority} · {source.role}</span></a>)}</details></article>)}</div>}{!!item.response?.clarifying_questions?.length && <div className="clarifying-block">{item.response.clarifying_questions.map((question, questionIndex) => <p key={questionIndex} className="clarifying-question">{questionIndex + 1}. {question}</p>)}<div className="answer-chips"><button onClick={() => setMessage('Có')}>Có</button><button onClick={() => setMessage('Không')}>Không</button><button onClick={() => setMessage('Tôi chưa rõ')}>Chưa rõ</button></div></div>}{!!item.response?.citations?.length && <details><summary>{item.response.citations.length} nguồn tham khảo</summary>{item.response.citations.map(citation => <p key={citation.index} className="citation">[{citation.index}] {citation.section ?? citation.excerpt ?? 'Nguồn thủ tục'}{citation.source_url && <> · <a href={citation.source_url} target="_blank" rel="noreferrer">Xem nguồn chính thức ↗</a></>}</p>)}</details>}</div></article>)}
            {busy && <article className="bubble assistant"><span>AI</span><div className="skeleton-loader"><div className="skeleton-line"></div><div className="skeleton-line short"></div></div></article>}
            {streamedText && <article className="bubble assistant"><span>AI</span><div><p>{streamedText}<span className="cursor">|</span></p></div></article>}
          </div>
          <form className="chat-input" onSubmit={send}>
            {selectedContext && <div className="chat-context-banner"><strong>Đang chọn:</strong> "{selectedContext.length > 40 ? selectedContext.substring(0, 40) + '...' : selectedContext}"</div>}
            <textarea aria-label="Nội dung cần hỏi" rows={2} maxLength={4000} value={message} onChange={event => setMessage(event.target.value)} placeholder="Mô tả việc hành chính bạn cần thực hiện…"/>
            <button className="primary" disabled={!message.trim() || busy || !!streamedText}>Gửi</button>
          </form>
          <p className="ai-note">AI có thể chưa đầy đủ. Đối chiếu nội dung với nguồn thủ tục.</p>
        </section>
      )}
    </div>
  );
}

async function checksum(file: File) {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('');
}

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));
const escapeHtml = (value: string) => value.replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch] as string));

function mapExtractedToDraftValues(fields: ExtractedField[], schema: ProcedureFormSchema): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of fields) {
    const value = (field.normalized_value || field.raw_value || '').trim();
    if (!value) continue;
    const target = schema.fields.find(item =>
      item.key === field.field_key || item.ocr_sources.some(source => source.split('.').pop() === field.field_key)
    );
    const key = target?.key;
    if (key && !values[key]) values[key] = value;
  }
  return values;
}

type TemplateSource = { label: string; links: { title: string; url: string }[] };
function buildDynamicFormHtml(schema: ProcedureFormSchema, values: Record<string, string>): string {
  const rows = schema.fields.map(field => {
    const value = values[field.key]?.trim();
    const rendered = value ? `<strong>${escapeHtml(value)}</strong>` : `[${'.'.repeat(42)}]`;
    return `<p>${escapeHtml(field.label)}${field.required ? ' <em>(bắt buộc)</em>' : ''}: ${rendered}</p>`;
  }).join('\n');
  return `<h2>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<br/>Độc lập - Tự do - Hạnh phúc</h2>
<h1>${escapeHtml(schema.title.toUpperCase())}</h1>
${rows}
<p><em>Bản nháp điện tử được dựng từ schema đã kiểm duyệt. Cơ quan có thẩm quyền quyết định việc tiếp nhận.</em></p>`;
}

type OcrPhase = 'idle' | 'upload' | 'prep' | 'recognize' | 'compose' | 'ready';
const PHASE_ORDER: OcrPhase[] = ['idle', 'upload', 'prep', 'recognize', 'compose', 'ready'];
const OCR_STAGES: { id: OcrPhase; label: string; hint: string }[] = [
  { id: 'upload', label: 'Tải lên & xác thực', hint: 'Kiểm tra định dạng và checksum' },
  { id: 'prep', label: 'Làm phẳng & chính diện', hint: 'Nắn phối cảnh, khử nghiêng, tăng tương phản' },
  { id: 'recognize', label: 'Nhận dạng OCR', hint: 'Bóc tách trường dữ liệu + bounding box' },
  { id: 'compose', label: 'Soạn văn bản DOCX', hint: 'Điền dữ liệu vào biểu mẫu đã kiểm duyệt' },
];
const PREP_STEP_LABELS: Record<string, string> = {
  original: 'Ảnh gốc (chuẩn hoá xoay EXIF)',
  perspective_correction: 'Làm thẳng góc chính diện',
  deskew: 'Làm phẳng — khử độ nghiêng',
  clahe_contrast: 'Tăng tương phản CLAHE',
};

function OcrPipelinePane({ phase, prepSteps, prepIndex, previewUrl, fields }: { phase: OcrPhase; prepSteps: PreprocessStep[]; prepIndex: number; previewUrl?: string; fields?: ExtractedField[] }) {
  const phaseRank = PHASE_ORDER.indexOf(phase);
  const visibleSteps = phase === 'prep' ? prepSteps.slice(0, prepIndex + 1) : prepSteps;
  const finalSnapshot = prepSteps[prepSteps.length - 1];
  const boxed = fields?.filter(item => item.bounding_box) ?? [];
  return (
    <aside className="ocr-pipeline-pane">
      <div className="pipeline-heading"><span className="eyebrow">XỬ LÝ TÀI LIỆU</span><h3>Theo dõi từng bước</h3></div>
      <ol className="pipeline-stages">
        {OCR_STAGES.map(stage => {
          const rank = PHASE_ORDER.indexOf(stage.id);
          const state = phase === 'ready' || phaseRank > rank ? 'done' : phaseRank === rank ? 'current' : 'todo';
          return (
            <li key={stage.id} className={state}>
              <i>{state === 'done' ? <Check size={12}/> : state === 'current' ? <span className="stage-spinner"/> : null}</i>
              <div>
                <b>{stage.label}</b><small>{stage.hint}</small>
                {stage.id === 'prep' && visibleSteps.length > 0 && (
                  <ul className="prep-substeps">
                    {visibleSteps.map((step, index) => (
                      <li key={step.name} className={phase !== 'prep' || index < prepIndex ? 'done' : 'current'}><Check size={10}/>{PREP_STEP_LABELS[step.name] ?? step.name}</li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {phase === 'ready' && (
        <figure className="stage-viewer">
          {finalSnapshot || previewUrl ? (
            <div className="stage-image">
              <img src={finalSnapshot?.image ?? previewUrl} alt="Tài liệu đã xử lý"/>
              {boxed.map(item => item.bounding_box && (
                <div key={item.id ?? item.field_key} className="bbox-overlay labeled" style={{ left: `${item.bounding_box[0] * 100}%`, top: `${item.bounding_box[1] * 100}%`, width: `${item.bounding_box[2] * 100}%`, height: `${item.bounding_box[3] * 100}%` }}>
                  <label>{humanizeStatus(item.field_key)} · {Math.round(item.confidence * 100)}%</label>
                </div>
              ))}
            </div>
          ) : <div className="stage-image empty">Chưa có ảnh</div>}
          <figcaption>{boxed.length ? `Đã khoanh vùng ${boxed.length} trường tại vị trí văn bản gốc` : 'Tài liệu đã tiền xử lý'}</figcaption>
        </figure>
      )}
    </aside>
  );
}

function ScanStage({ phase, image, fields }: { phase: OcrPhase; image?: string; fields?: ExtractedField[] }) {
  const boxed = fields?.filter(item => item.bounding_box) ?? [];
  const caption =
    phase === 'upload' ? 'Đang tải tài liệu lên…'
    : phase === 'prep' ? 'Tiền xử lý: làm thẳng chính diện và tăng tương phản'
    : phase === 'recognize' ? 'Đang quét nhận dạng nội dung…'
    : `Đã nhận dạng ${boxed.length} vùng văn bản — đang điền vào mẫu DOCX…`;
  return (
    <div className="scan-stage">
      <div className="scan-frame">
        {image ? <img key={image} src={image} alt="Tài liệu đang xử lý"/> : <div className="scan-empty">Đang chuẩn bị bản xem trước…</div>}
        {phase === 'recognize' && <div className="scan-beam"/>}
        {phase === 'compose' && boxed.map((item, index) => item.bounding_box && (
          <div key={item.id ?? item.field_key} className="bbox-overlay pop" style={{ left: `${item.bounding_box[0] * 100}%`, top: `${item.bounding_box[1] * 100}%`, width: `${item.bounding_box[2] * 100}%`, height: `${item.bounding_box[3] * 100}%`, animationDelay: `${index * 130}ms` }}>
            <label>{humanizeStatus(item.field_key)} · {Math.round(item.confidence * 100)}%</label>
          </div>
        ))}
      </div>
      <p className="scan-caption">{phase !== 'compose' && phase !== 'upload' && <span className="stage-spinner inline"/>}{caption}</p>
    </div>
  );
}

function WordWorkspace({ content, fileName, onSelectionChange, onContentChange, onDownload, downloading, statusHint, source }: { content: string; fileName: string; onSelectionChange?: (text: string) => void; onContentChange?: (html: string) => void; onDownload?: (html: string) => void; downloading?: boolean; statusHint?: string; source?: TemplateSource }) {
  const [zoom, setZoom] = useState(100);
  const editor = useEditor({
    extensions: [StarterKit],
    content,
    onSelectionUpdate: ({ editor }) => {
      if (!onSelectionChange) return;
      const { from, to } = editor.state.selection;
      onSelectionChange(from !== to ? editor.state.doc.textBetween(from, to, ' ') : '');
    },
    onUpdate: ({ editor }) => onContentChange?.(editor.getHTML()),
  });
  useEffect(() => {
    if (editor && content !== editor.getHTML()) editor.commands.setContent(content);
  }, [editor, content]);
  const words = editor ? editor.getText().trim().split(/\s+/).filter(Boolean).length : 0;
  const markClass = (name: 'bold' | 'italic' | 'strike' | 'bulletList') => editor?.isActive(name) ? 'active' : '';
  return (
    <div className="word-app">
      <div className="word-titlebar">
        <span className="word-logo">W</span>
        <div className="word-file"><b>{fileName}</b><small>Tự động lưu khi nộp · Bản nháp</small></div>
        {onDownload && <button className="word-download" onClick={() => onDownload(editor?.getHTML() ?? content)} disabled={downloading}><Download size={14}/>{downloading ? 'Đang tạo DOCX…' : 'Tải xuống DOCX'}</button>}
      </div>
      <div className="word-ribbon">{['Tệp', 'Trang đầu', 'Chèn', 'Bố cục', 'Tham chiếu', 'Xem lại', 'Xem'].map(tab => <span key={tab} className={tab === 'Trang đầu' ? 'active' : ''}>{tab}</span>)}</div>
      <div className="word-toolbar">
        <span className="word-font">Times New Roman</span>
        <span className="word-size">13</span>
        <i className="word-sep"/>
        <button className={markClass('bold')} aria-label="Đậm" onClick={() => editor?.chain().focus().toggleBold().run()}><Bold size={14}/></button>
        <button className={markClass('italic')} aria-label="Nghiêng" onClick={() => editor?.chain().focus().toggleItalic().run()}><Italic size={14}/></button>
        <button className={markClass('strike')} aria-label="Gạch ngang" onClick={() => editor?.chain().focus().toggleStrike().run()}><Strikethrough size={14}/></button>
        <i className="word-sep"/>
        <button className={markClass('bulletList')} aria-label="Danh sách" onClick={() => editor?.chain().focus().toggleBulletList().run()}><ListIcon size={14}/></button>
        <button aria-label="In" onClick={() => window.print()}><Printer size={14}/></button>
      </div>
      {source && (
        <div className="word-source-bar">
          <span>⚖ {source.label}</span>
          <span className="word-source-links">{source.links.map(link => <a key={link.url} href={link.url} target="_blank" rel="noreferrer">{link.title} ↗</a>)}</span>
        </div>
      )}
      <div className="word-ruler">{Array.from({ length: 17 }, (_, index) => <i key={index}/>)}</div>
      <div className="word-canvas">
        <div className="word-page" style={{ transform: `scale(${zoom / 100})` }}>
          <div className="word-watermark">DỰ THẢO — KHÔNG CÓ GIÁ TRỊ PHÁP LÝ</div>
          <EditorContent editor={editor}/>
        </div>
      </div>
      <div className="word-statusbar">
        <span>Trang 1/1 · {words} từ · Tiếng Việt (Việt Nam)</span>
        {statusHint && <span className="word-hint">{statusHint}</span>}
        <span className="word-zoom"><button aria-label="Thu nhỏ" onClick={() => setZoom(value => Math.max(60, value - 10))}>−</button>{zoom}%<button aria-label="Phóng to" onClick={() => setZoom(value => Math.min(150, value + 10))}>+</button></span>
      </div>
    </div>
  );
}


function CitizenPortal() {
  const [logged, setLogged] = useState(!!token()); const [cases, setCases] = useState<CaseRecord[]>([]); const [current, setCurrent] = useState<CaseRecord | null>(null);
  const [file, setFile] = useState<File>(); const [consent, setConsent] = useState(false);
  const [notice, setNotice] = useState(''); const [busy, setBusy] = useState('');
  const [procedures, setProcedures] = useState<ProcedureSummary[]>([]);
  const [procedureCapabilities, setProcedureCapabilities] = useState<Record<string, ProcedureCapabilities>>({});
  const [formSchema, setFormSchema] = useState<ProcedureFormSchema>();
  const [capabilities, setCapabilities] = useState<ProcedureCapabilities>();
  
  const [started, setStarted] = useState(false);
  const [docContent, setDocContent] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [extractedFields, setExtractedFields] = useState<ExtractedField[]>();
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [ocrPhase, setOcrPhase] = useState<OcrPhase>('idle');
  const [prepSteps, setPrepSteps] = useState<PreprocessStep[]>([]);
  const [prepIndex, setPrepIndex] = useState(0);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const requiredFields = formSchema?.fields.filter(field => field.required) ?? [];
  const readiness = requiredFields.length ? Math.round(requiredFields.filter(field => draftValues[field.key]?.trim()).length / requiredFields.length * 100) : 0;
  const reviewCount = extractedFields?.filter(item => item.confidence < 0.85).length ?? 0;
  const updateDraftValue = (key: string, value: string) => setDraftValues(current => {
    const next = { ...current, [key]: value };
    if (formSchema) setDocContent(buildDynamicFormHtml(formSchema, next));
    return next;
  });

  const refresh = async () => setCases(await api<CaseRecord[]>('/citizen/cases'));
  useEffect(() => {
    if (!logged) return;
    Promise.all([refresh(), api<ProcedureSummary[]>('/procedures').then(async items => {
      rememberProcedureNames(items); setProcedures(items);
      const pairs = await Promise.all(items.map(async item => [item.id, await api<ProcedureCapabilities>(`/procedures/${item.id}/capabilities`)] as const));
      setProcedureCapabilities(Object.fromEntries(pairs));
    })])
      .catch(cause => setNotice((cause as Error).message));
  }, [logged]);
  if (!logged) return <Login role="citizen" onSuccess={() => setLogged(true)}/>;
  
  const run = async (name: string, work: () => Promise<void>) => { setBusy(name); setNotice(''); try { await work(); } catch (cause) { setNotice((cause as Error).message); } finally { setBusy(''); } };
  
  // Một luồng duy nhất: mở tờ khai mẫu để tự điền, OCR là bước "AI điền hộ" tùy chọn.
  const startCase = (procedure: ProcedureSummary) => {
    run('create', async () => {
      const [schema, caps] = await Promise.all([
        api<ProcedureFormSchema>(`/procedures/${procedure.id}/form-schema`),
        api<ProcedureCapabilities>(`/procedures/${procedure.id}/capabilities`),
      ]);
      setStarted(true);
      setFormSchema(schema);
      setCapabilities(caps);
      setDocContent(buildDynamicFormHtml(schema, {}));
      setExtractedFields(undefined);
      setPreviewUrl(undefined);
      setOcrPhase('idle');
      setPrepSteps([]);
      setPrepIndex(0);
      setDraftValues({});
      const item = await api<CaseRecord>('/citizen/cases', { method: 'POST', body: JSON.stringify({ procedure_id: procedure.id, locality_code: procedure.locality_code }) });
      setCurrent(item);
      setNotice('Đã khởi tạo tờ khai. Điền trực tiếp hoặc tải giấy tờ để AI điền tự động.');
      await refresh();
    });
  };

  const upload = () => current && file && run('upload', async () => {
    setOcrPhase('upload'); setPrepSteps([]); setPrepIndex(0); setExtractedFields(undefined);
    setPreviewUrl(URL.createObjectURL(file));

    const intent = await api<{ document_id: string; upload_url: string }>(`/citizen/cases/${current.id}/documents/upload-intents`, { method: 'POST', body: JSON.stringify({ filename: file.name, content_type: file.type, size_bytes: file.size }) });
    const uploaded = await fetch(intent.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': 'application/octet-stream', Authorization: `Bearer ${token()}` } });
    if (!uploaded.ok) throw new Error('Không thể tải file lên');

    setOcrPhase('prep');
    // OCR (LLM) chạy song song trong lúc minh hoạ các bước tiền xử lý
    const completePromise = api<{ document: CaseDocument, fields: ExtractedField[] }>(`/citizen/documents/${intent.document_id}/complete`, { method: 'POST', body: JSON.stringify({ sha256: await checksum(file) }) });
    completePromise.catch(() => undefined);
    try {
      const prep = await api<PreprocessResult>(`/citizen/documents/${intent.document_id}/preprocess`, { method: 'POST' });
      if (prep.steps.length) {
        setPrepSteps(prep.steps);
        for (let index = 0; index < prep.steps.length; index += 1) { setPrepIndex(index); await sleep(450); }
      }
    } catch { /* tiền xử lý chỉ minh hoạ — lỗi không chặn OCR */ }
    setOcrPhase('recognize');
    let completeResp: { document: CaseDocument, fields: ExtractedField[] };
    try { completeResp = await completePromise; } catch (cause) { setOcrPhase('idle'); throw cause; }
    setExtractedFields(completeResp.fields);
    setOcrPhase('compose');
    // Trường đã điền trước đó (OCR lần trước) được giữ nguyên — OCR mới chỉ điền chỗ trống.
    if (!formSchema) throw new Error('Chưa tải được schema biểu mẫu');
    const merged = { ...mapExtractedToDraftValues(completeResp.fields, formSchema), ...draftValues };
    setDraftValues(merged);
    setDocContent(buildDynamicFormHtml(formSchema, merged));
    await sleep(1400); // giữ màn bounding box đủ lâu để thấy các vùng nhận dạng trước khi chuyển sang DOCX
    setOcrPhase('ready');
    setNotice(`AI đã nhận dạng ${completeResp.fields.length} trường và điền vào tờ khai.`);
    await refreshCurrent(current.id);
  });

  // Xuất DOCX từ chính HTML đang hiển thị trong editor (WYSIWYG — cách làm của C2):
  // người dân sửa gì trong tờ khai thì file tải xuống có đúng nội dung đó.
  const downloadDocx = (html: string) => run('docx', async () => {
    const filename = `${formSchema?.procedure_id ?? 'to-khai'}.docx`;
    const blob = await apiBlob('/drafts/export.docx', { method: 'POST', body: JSON.stringify({ html, filename }) });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = filename; anchor.click();
    URL.revokeObjectURL(url);
    setNotice('Đã tải xuống bản nháp DOCX.');
  });
  
  const submit = () => current && run('submit', async () => { 
    if (!consent) throw new Error('Vui lòng xác nhận đồng ý xử lý dữ liệu trước khi nộp.'); 
    const latest = await api<{ case: CaseRecord }>(`/citizen/cases/${current.id}`); 
    const updated = await api<CaseRecord>(`/citizen/cases/${current.id}`, { method: 'PATCH', body: JSON.stringify({ expected_version: latest.case.version, form_data: { ...draftValues, _draft_html: docContent, _readiness_score: readiness } }) });
    const item = await api<CaseRecord>(`/citizen/cases/${current.id}/submit`, { method: 'POST', headers: { 'Idempotency-Key': idempotency() }, body: JSON.stringify({ expected_version: updated.version, consent_version: 'privacy-v1', consent_accepted: true }) });
    setCurrent(item); 
    setNotice('Hồ sơ đã được chuyển tới cán bộ tiếp nhận.'); 
    await refresh(); 
  });
  const refreshCurrent = async (id: string) => { const detail = await api<{case: CaseRecord}>(`/citizen/cases/${id}`); setCurrent(detail.case); await refresh(); };
  const handleChecklist = async (caseId: string) => { await refreshCurrent(caseId); setStarted(true); setNotice('Đã nhận danh sách giấy tờ. Vui lòng chuẩn bị và tải lên.'); };
  const startProcedureFromChat = (procedureId: string) => {
    const procedure = procedures.find(item => item.id === procedureId);
    if (!procedure) { setNotice('Thủ tục này mới hỗ trợ hỏi đáp, chưa có biểu mẫu được duyệt.'); return; }
    startCase(procedure);
  };

  return (
    <Shell role="citizen">
      <main className="citizen-page document-centric">
        <div className="page-title">
          <div>
            <span className="eyebrow">CỔNG DỊCH VỤ CÔNG</span>
            <h1>Xin chào, công dân</h1>
            <p>Khởi tạo thủ tục qua biểu mẫu điện tử hoặc tải lên tài liệu có sẵn.</p>
          </div>
          <button className="ghost compact" onClick={() => { setToken('', 'citizen'); setLogged(false); }}>Đăng xuất</button>
        </div>
        
        <div className="document-workspace">
           {!started && !current && (
              <div className="procedure-selector">
                 <h2>Chọn thủ tục cần soạn</h2>
                 <div className="selector-cards">
                   {procedures.map(procedure => (
                     <button key={procedure.id} onClick={() => startCase(procedure)} className="selector-card" disabled={!procedureCapabilities[procedure.id]?.dynamic_form}>
                       <FileText size={32} />
                       <h3>{procedure.name}</h3>
                       <p>{procedure.agency}{procedure.national_code ? ` · Mã ${procedure.national_code}` : ''}{!procedureCapabilities[procedure.id]?.dynamic_form ? ' · Chỉ hỗ trợ chat' : ''}</p>
                     </button>
                   ))}
                   {!procedures.length && <p>Chưa có thủ tục với biểu mẫu đã công bố.</p>}
                 </div>
              </div>
           )}

           {(started || current) && (
              <div className="editor-container">
                 <div className="editor-main">
                    {ocrPhase !== 'idle' && ocrPhase !== 'ready' ? (
                      <div className="ocr-studio">
                        <OcrPipelinePane phase={ocrPhase} prepSteps={prepSteps} prepIndex={prepIndex} previewUrl={previewUrl} fields={extractedFields}/>
                        <ScanStage
                          phase={ocrPhase}
                          image={ocrPhase === 'prep' ? (prepSteps[Math.min(prepIndex, prepSteps.length - 1)]?.image ?? previewUrl) : (prepSteps[prepSteps.length - 1]?.image ?? previewUrl)}
                          fields={extractedFields}
                        />
                      </div>
                    ) : (
                      <WordWorkspace
                        content={docContent}
                        fileName={`${formSchema?.procedure_id ?? 'to-khai'}.docx`}
                        onSelectionChange={setSelectedText}
                        onContentChange={setDocContent}
                        onDownload={downloadDocx}
                        downloading={busy === 'docx'}
                        statusHint={`${formSchema?.fields.filter(field => draftValues[field.key]).length ?? 0} trường đã điền · ${formSchema?.fields.filter(field => !draftValues[field.key]).length ?? 0} trường còn trống`}
                      />
                    )}
                 </div>
                 
                 <div className="document-sidebar">
                   {!current ? (
                     <div className="sidebar-block">
                       <h3>Đang khởi tạo...</h3>
                       <div className="skeleton-loader"><div className="skeleton-line"></div></div>
                     </div>
                   ) : (
                     <div className="sidebar-block">
                        <div className="current-case">
                         <span>Hồ sơ đang làm</span>
                         <strong>{current.case_code || 'Chưa cấp mã'}</strong>
                         <Status value={current.status}/>
                        </div>

                        <div className="readiness-card">
                          <div><span>Mức sẵn sàng</span><strong>{readiness}%</strong></div>
                          <div className="readiness-track"><i style={{ width: `${readiness}%` }}/></div>
                          <small>{requiredFields.filter(field => draftValues[field.key]?.trim()).length}/{requiredFields.length} trường bắt buộc · {reviewCount} trường cần xác minh</small>
                        </div>

                        <details className="structured-fields" open={!!extractedFields?.length}>
                          <summary>Dữ liệu dùng để nộp</summary>
                          {formSchema?.fields.map(field => (
                            <label key={field.key}>{field.label}{field.required ? ' *' : ''}<input type={field.type === 'date' ? 'date' : field.type === 'number' ? 'number' : 'text'} value={draftValues[field.key] ?? ''} onChange={event => updateDraftValue(field.key, event.target.value)} placeholder="Chưa có dữ liệu"/></label>
                          ))}
                        </details>
                       
                       {current.checklist && Object.keys(current.checklist).length > 0 && (
                         <div className="checklist-display">
                           <h3>Danh sách giấy tờ cần thiết</h3>
                           <ul className="checklist-items">
                             {Object.entries(current.checklist).map(([key, status]) => (
                               <li key={key} className={`checklist-item ${status}`}>
                                 <span className="check-icon">{status === 'uploaded' || status === 'verified' ? '✓' : '○'}</span>
                                 <div className="check-text">
                                   <strong>{humanizeStatus(key)}</strong>
                                   <small>{humanizeStatus(String(status))}</small>
                                 </div>
                               </li>
                             ))}
                           </ul>
                         </div>
                       )}
                       
                       {ocrPhase === 'ready' && prepSteps.length > 0 && (
                         <div className="sidebar-doc">
                           <h3>Giấy tờ đã xử lý</h3>
                           <div className="stage-image">
                             <img src={prepSteps[prepSteps.length - 1].image} alt="Tài liệu đã tiền xử lý"/>
                             {extractedFields?.map(item => item.bounding_box && (
                               <div key={item.id ?? item.field_key} className="bbox-overlay labeled" style={{ left: `${item.bounding_box[0] * 100}%`, top: `${item.bounding_box[1] * 100}%`, width: `${item.bounding_box[2] * 100}%`, height: `${item.bounding_box[3] * 100}%` }}>
                                 <label>{humanizeStatus(item.field_key)} · {Math.round(item.confidence * 100)}%</label>
                               </div>
                             ))}
                           </div>
                           <small className="muted">Đã khoanh vùng {extractedFields?.filter(item => item.bounding_box).length ?? 0} trường tại vị trí văn bản gốc</small>
                         </div>
                       )}

                       {capabilities?.ocr_autofill && <div className="upload-block">
                         <h3 style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--navy)' }}>AI điền tự động từ giấy tờ</h3>
                         <label className="dropzone">
                           <input type="file" accept="image/jpeg,image/png" onChange={event => setFile(event.target.files?.[0])}/>
                           <b>{file ? file.name : 'Chọn bản chụp giấy tờ'}</b>
                           <span>JPG hoặc PNG · tối đa 10 MB</span>
                         </label>
                         <button className="secondary wide" onClick={upload} disabled={!file || !!busy}>{busy === 'upload' ? 'Đang xử lý OCR…' : 'Tải lên & điền tự động'}</button>
                       </div>}
                       
                       <div className="submit-block">
                         <label className="check-row">
                           <input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)}/>
                           <span>Tôi đồng ý để cơ quan tiếp nhận và xử lý dữ liệu.</span>
                         </label>
                         <button className="primary wide" onClick={submit} disabled={!!busy || !consent || readiness < 60}>{busy === 'submit' ? 'Đang gửi…' : readiness < 60 ? 'Cần điền thêm dữ liệu' : 'Nộp hồ sơ tiền kiểm'}</button>
                       </div>
                       <button className="text-button" onClick={() => { setCurrent(null); setStarted(false); setFormSchema(undefined); setCapabilities(undefined); setOcrPhase('idle'); setPrepSteps([]); setPrepIndex(0); setExtractedFields(undefined); setPreviewUrl(undefined); setFile(undefined); setDraftValues({}); setDocContent(''); }}>Tạo hồ sơ khác</button>
                     </div>
                   )}
                   
                   {notice && <div className={`alert ${notice.includes('Đã') || notice.includes('đã') ? 'success' : 'error'}`} role="status">{notice}</div>}
                 </div>
              </div>
           )}
        </div>
        
        <CitizenAssistant activeCaseId={current?.id} onChecklist={handleChecklist} onStartProcedure={startProcedureFromChat} selectedContext={selectedText} />
      </main>
    </Shell>
  );
}

function Status({ value }: { value: string }) { return <span className={`status status-${value}`}>{humanizeStatus(value)}</span>; }
function Empty({ title, text }: { title: string; text: string }) { return <div className="empty-state"><span>◇</span><h3>{title}</h3><p>{text}</p></div>; }

function OfficerPortal() {
  const [logged, setLogged] = useState(!!token()); const [cases, setCases] = useState<CaseRecord[]>([]); const [summary, setSummary] = useState<DashboardSummary>(); const [selected, setSelected] = useState<CaseDetail>();
  const [search, setSearch] = useState(''); const [filter, setFilter] = useState(''); const [sort, setSort] = useState('priority_desc'); const [loading, setLoading] = useState(true); const [detailLoading, setDetailLoading] = useState(false); const [notice, setNotice] = useState('');
  const loadQueue = async () => { setLoading(true); try { const [queue, dashboard, catalogItems] = await Promise.all([api<CaseRecord[]>(`/officer/cases?${buildCaseQuery(search, filter, sort)}`), api<DashboardSummary>('/officer/dashboard/summary'), api<ProcedureSummary[]>('/procedures')]); rememberProcedureNames(catalogItems); setCases(queue); setSummary(dashboard); } catch (cause) { handleError(cause); } finally { setLoading(false); } };
  const handleError = (cause: unknown) => { const error = cause as Error; if (error instanceof ApiError && error.status === 401) { setToken('', 'officer'); setLogged(false); } setNotice(error.message); };
  useEffect(() => { if (!logged) return; const timer = window.setTimeout(loadQueue, 250); return () => window.clearTimeout(timer); }, [logged, search, filter, sort]);
  useEffect(() => { if (!logged) return; const timer = window.setInterval(loadQueue, 30000); return () => window.clearInterval(timer); }, [logged, search, filter, sort]);
  if (!logged) return <Login role="officer" onSuccess={() => setLogged(true)}/>;
  const open = async (id: string) => { setDetailLoading(true); setNotice(''); try { setSelected(await api<CaseDetail>(`/officer/cases/${id}`)); } catch (cause) { handleError(cause); } finally { setDetailLoading(false); } };
  const refreshSelected = async () => { if (selected) await open(selected.case.id); await loadQueue(); };
  return <Shell role="officer"><main className="officer-page"><div className="page-title officer-title"><div><span className="eyebrow">TRUNG TÂM ĐIỀU HÀNH</span><h1>Xử lý hồ sơ tiền kiểm</h1><p>Dữ liệu cập nhật tự động mỗi 30 giây.</p></div><div className="title-actions"><button className="ghost compact" onClick={loadQueue}>↻ Làm mới</button><button className="ghost compact" onClick={() => { setToken('', 'officer'); setLogged(false); }}>Đăng xuất</button></div></div><Dashboard summary={summary} active={filter} onFilter={setFilter}/>{notice && <div className="alert error dismissible" role="alert">{notice}<button onClick={() => setNotice('')}>×</button></div>}<div className="officer-workspace"><aside className="queue-panel"><div className="queue-heading"><div><span className="eyebrow">HÀNG ĐỢI</span><h2>{summary?.total ?? 0} hồ sơ</h2></div><span className="live-dot">Trực tuyến</span></div><label className="search-box"><span>⌕</span><input aria-label="Tìm hồ sơ" value={search} onChange={event => setSearch(event.target.value)} placeholder="Tìm mã hồ sơ, thủ tục…"/></label><div className="queue-filters"><select aria-label="Lọc trạng thái" value={filter} onChange={event => setFilter(event.target.value)}><option value="">Mọi trạng thái</option><option value="awaiting_officer_review">Chờ tiếp nhận</option><option value="in_officer_review">Đang thẩm tra</option><option value="needs_citizen_update">Chờ bổ sung</option><option value="precheck_ready">Đạt tiền kiểm</option></select><select aria-label="Sắp xếp" value={sort} onChange={event => setSort(event.target.value)}><option value="priority_desc">Ưu tiên cao</option><option value="newest">Mới cập nhật</option><option value="oldest">Cũ nhất</option></select></div><div className="case-list">{loading ? [1,2,3].map(item => <div className="case-skeleton" key={item}/>) : cases.length ? cases.map(item => <button className={`queue-case ${selected?.case.id === item.id ? 'active' : ''}`} key={item.id} onClick={() => open(item.id)}><span className="priority-line"><b>{item.case_code}</b>{(item.priority ?? 0) >= 70 && <i>Ưu tiên</i>}</span><strong>{procedureNames[item.procedure_id] ?? item.procedure_id}</strong><span className="case-meta"><Status value={item.status}/><small>{formatDate(item.updated_at)}</small></span></button>) : <Empty title="Không có hồ sơ" text="Thử thay đổi bộ lọc hoặc từ khóa."/>}</div></aside><section className="review-shell">{detailLoading ? <div className="detail-loading"><i/><p>Đang tải hồ sơ…</p></div> : selected ? <ReviewWorkspace detail={selected} onRefresh={refreshSelected} onError={handleError}/> : <div className="welcome-review"><div className="welcome-art"><span>✓</span></div><span className="eyebrow">KHÔNG GIAN THẨM TRA</span><h2>Chọn một hồ sơ để bắt đầu</h2><p>Đối chiếu tài liệu gốc, dữ liệu OCR và kết quả kiểm tra trên cùng một màn hình.</p><div className="welcome-features"><span><i>1</i>Xem căn cứ</span><span><i>2</i>Xác minh OCR</span><span><i>3</i>Ra quyết định</span></div></div>}</section></div></main></Shell>;
}

function Dashboard({ summary, active, onFilter }: { summary?: DashboardSummary; active: string; onFilter: (value: string) => void }) {
  const cards = [
    { label: 'Tổng hồ sơ', value: summary?.total, filter: '', tone: 'navy', icon: '▦' },
    { label: 'Chờ tiếp nhận', value: summary?.awaiting_review, filter: 'awaiting_officer_review', tone: 'blue', icon: '◷' },
    { label: 'Đang thẩm tra', value: summary?.in_review, filter: 'in_officer_review', tone: 'teal', icon: '⌁' },
    { label: 'Chờ bổ sung', value: summary?.needs_citizen_update, filter: 'needs_citizen_update', tone: 'gold', icon: '!' },
  ];
  return <section className="dashboard-cards" aria-label="Tổng quan hồ sơ">{cards.map(card => <button key={card.label} className={`dashboard-card ${card.tone} ${active === card.filter ? 'active' : ''}`} onClick={() => onFilter(active === card.filter && card.filter ? '' : card.filter)}><span className="stat-icon">{card.icon}</span><span><small>{card.label}</small><strong>{card.value ?? '—'}</strong></span><i>→</i></button>)}</section>;
}

function ReviewWorkspace({ detail, onRefresh, onError }: { detail: CaseDetail; onRefresh: () => Promise<void>; onError: (cause: unknown) => void }) {
  const [documentId, setDocumentId] = useState(detail.documents[0]?.id ?? ''); const [fields, setFields] = useState<ExtractedField[]>([]); const [previewUrl, setPreviewUrl] = useState(''); const [previewError, setPreviewError] = useState(''); const [busy, setBusy] = useState(''); const [supplement, setSupplement] = useState(''); const [selectedFindings, setSelectedFindings] = useState<string[]>(detail.findings.filter(isActiveFinding).map(item => item.id)); const [reasons, setReasons] = useState<Record<string, string>>({});
  const activeDocument = detail.documents.find(item => item.id === documentId);
  useEffect(() => { setDocumentId(detail.documents[0]?.id ?? ''); setSelectedFindings(detail.findings.filter(isActiveFinding).map(item => item.id)); }, [detail.case.id]);
  useEffect(() => {
    if (!documentId) { setFields([]); setPreviewUrl(''); return; }
    let objectUrl = '';
    api<ExtractedField[]>(`/officer/documents/${documentId}/fields`).then(setFields).catch(onError);
    apiBlob(`/officer/documents/${documentId}/content`).then(blob => { objectUrl = URL.createObjectURL(blob); setPreviewUrl(objectUrl); setPreviewError(''); }).catch(cause => { setPreviewUrl(''); setPreviewError((cause as Error).message); });
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [documentId]);
  const action = async (name: string, work: () => Promise<unknown>) => { setBusy(name); try { await work(); await onRefresh(); } catch (cause) { onError(cause); } finally { setBusy(''); } };
  const claim = () => action('claim', () => api(`/officer/cases/${detail.case.id}/claim`, { method: 'POST' }));
  const decide = (finding: Finding, decision: 'accept' | 'dismiss' | 'escalate') => action(`${decision}-${finding.id}`, () => api(`/officer/findings/${finding.id}/${decision}`, { method: 'POST', body: decision === 'accept' ? undefined : JSON.stringify({ reason: reasons[finding.id] || (decision === 'dismiss' ? 'Đã đối chiếu tài liệu gốc.' : 'Cần ý kiến chuyên môn.') }) }));
  const transition = (target_status: string) => action(target_status, () => api(`/officer/cases/${detail.case.id}/transition`, { method: 'POST', body: JSON.stringify({ target_status }) }));
  const requestSupplement = () => action('supplement', () => api(`/officer/cases/${detail.case.id}/supplement-requests`, { method: 'POST', body: JSON.stringify({ public_message: supplement, finding_ids: selectedFindings }) }));
  const rerun = () => action('rerun', () => api(`/officer/cases/${detail.case.id}/rerun-validation`, { method: 'POST' }));
  return <div className="review-workspace"><div className="review-header"><div><div className="case-code"><span>{detail.case.case_code}</span><Status value={detail.case.status}/></div><h2>{procedureNames[detail.case.procedure_id] ?? detail.case.procedure_id}</h2><p>Phiên bản hồ sơ {detail.submission.version} · Bộ quy tắc {detail.submission.procedure_rule_version}</p></div><div className="review-header-actions">{detail.case.status === 'awaiting_officer_review' && <button className="primary" onClick={claim} disabled={!!busy}>{busy === 'claim' ? 'Đang nhận…' : 'Nhận xử lý'}</button>}<button className="icon-button" aria-label="Làm mới hồ sơ" onClick={onRefresh}>↻</button></div></div><div className="progress-line"><span className="done">Đã nộp</span><span className="done">Tiền kiểm AI</span><span className={detail.case.status === 'awaiting_officer_review' ? 'current' : 'done'}>Tiếp nhận</span><span className={detail.case.status === 'in_officer_review' ? 'current' : ''}>Thẩm tra</span><span className={detail.case.status === 'precheck_ready' ? 'done' : ''}>Hoàn tất</span></div><div className="review-columns"><EvidencePanel documents={detail.documents} activeId={documentId} onSelect={setDocumentId} active={activeDocument} previewUrl={previewUrl} previewError={previewError} fields={fields}/><DataPanel submission={detail.submission.form_data} fields={fields} editable={detail.case.status === 'in_officer_review'} onSaved={async () => { if (documentId) setFields(await api<ExtractedField[]>(`/officer/documents/${documentId}/fields`)); }} onError={onError}/><FindingsPanel findings={detail.findings} busy={busy} reasons={reasons} setReasons={setReasons} onDecide={decide}/></div><div className="review-bottom"><details><summary>Lịch sử xử lý <span>{detail.timeline.length}</span></summary><ol className="timeline">{detail.timeline.length ? detail.timeline.map(item => <li key={item.id}><i/><div><b>{humanizeStatus(item.event_type)}</b><small>{formatDate(item.created_at)} · {item.actor_id}</small></div></li>) : <li>Chưa có hoạt động.</li>}</ol></details>{detail.case.status === 'in_officer_review' && <section className="decision-box"><div><span className="eyebrow">HÀNH ĐỘNG XỬ LÝ</span><h3>Yêu cầu công dân bổ sung</h3></div><textarea value={supplement} onChange={event => setSupplement(event.target.value)} maxLength={5000} placeholder="Mô tả rõ thông tin hoặc giấy tờ cần bổ sung…"/><div className="finding-selector">{detail.findings.filter(isActiveFinding).map(item => <label key={item.id}><input type="checkbox" checked={selectedFindings.includes(item.id)} onChange={() => setSelectedFindings(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id])}/><span>{item.message}</span></label>)}</div><div className="decision-actions"><button className="warning-button" disabled={!supplement.trim() || !selectedFindings.length || !!busy} onClick={requestSupplement}>Yêu cầu bổ sung</button><button className="ghost" disabled={!!busy} onClick={() => transition('escalated')}>Chuyển chuyên môn</button><button className="ghost" disabled={!!busy} onClick={rerun}>{busy === 'rerun' ? 'Đang kiểm tra…' : 'Chạy lại kiểm tra'}</button><button className="success-button" disabled={!!busy || detail.findings.some(item => item.severity === 'error' && isActiveFinding(item))} onClick={() => transition('precheck_ready')}>Đạt tiền kiểm</button></div></section>}</div></div>;
}

function EvidencePanel({ documents, activeId, onSelect, active, previewUrl, previewError, fields }: { documents: CaseDocument[]; activeId: string; onSelect: (id: string) => void; active?: CaseDocument; previewUrl: string; previewError: string; fields?: ExtractedField[] }) {
  return <section className="review-panel evidence-panel"><div className="column-heading"><span>TÀI LIỆU & CĂN CỨ</span><b>{documents.length}</b></div><div className="document-tabs">{documents.map(item => <button key={item.id} className={activeId === item.id ? 'active' : ''} onClick={() => onSelect(item.id)}><span>▤</span><div><b>{item.original_filename ?? item.document_type}</b><small>{formatBytes(item.size_bytes)}</small></div><Status value={item.ocr_status}/></button>)}</div>{active ? <div className="document-viewer">{previewUrl ? active.content_type === 'application/pdf' ? <iframe title={active.original_filename ?? 'Tài liệu'} src={previewUrl}/> : <div className="image-preview-container"><img alt={active.original_filename ?? 'Tài liệu'} src={previewUrl}/>{fields?.map(f => f.bounding_box && (<div key={f.id} className="bbox-overlay" style={{ left: `${f.bounding_box[0]*100}%`, top: `${f.bounding_box[1]*100}%`, width: `${f.bounding_box[2]*100}%`, height: `${f.bounding_box[3]*100}%` }} title={`${f.field_key}: ${f.normalized_value || f.raw_value}`}/>))}</div> : <div className="document-placeholder"><div className="paper-lines"><i/><i/><i/><i/><i/></div><span>▧</span><b>Chưa có bản xem trước</b><small>{previewError || 'Tài liệu được bảo vệ và chỉ mở khi được cấp quyền.'}</small></div>}<div className="viewer-meta"><span>{active.ocr_engine ? `OCR: ${active.ocr_engine}` : 'Chưa có OCR'}</span><Status value={active.ocr_status}/></div></div> : <Empty title="Chưa có tài liệu" text="Hồ sơ này chưa đính kèm giấy tờ."/>}</section>;
}

function DataPanel({ submission, fields, editable, onSaved, onError }: { submission: Record<string, unknown>; fields: ExtractedField[]; editable: boolean; onSaved: () => Promise<void>; onError: (cause: unknown) => void }) {
  const [editing, setEditing] = useState<string>(); const [value, setValue] = useState(''); const [busy, setBusy] = useState(false);
  const save = async (field: ExtractedField) => { setBusy(true); try { await api(`/officer/extracted-fields/${field.id}`, { method: 'PATCH', body: JSON.stringify({ normalized_value: value, reason: 'Cán bộ đối chiếu tài liệu gốc' }) }); setEditing(undefined); await onSaved(); } catch (cause) { onError(cause); } finally { setBusy(false); } };
  const rows = Object.entries(submission);
  return <section className="review-panel data-panel"><div className="column-heading"><span>DỮ LIỆU CÓ CẤU TRÚC</span><b>{rows.length + fields.length}</b></div><div className="data-section"><h3>Thông tin người khai</h3>{rows.length ? rows.map(([key, item]) => <div className="data-row" key={key}><span>{humanizeStatus(key)}</span><strong>{String(item || '—')}</strong><small className="verified">✓ Đã khai</small></div>) : <p className="empty">Không có dữ liệu biểu mẫu.</p>}</div><div className="data-section"><div className="section-title"><h3>Kết quả OCR</h3>{fields.some(item => item.review_status === 'needs_human_review') && <span className="needs-review">Cần xác minh</span>}</div>{fields.length ? fields.map(field => <div className={`ocr-row ${field.review_status === 'needs_human_review' ? 'low-confidence' : ''}`} key={field.id}><div><span>{humanizeStatus(field.field_key)}</span><small>Độ tin cậy {Math.round(field.confidence * 100)}%</small></div>{editing === field.id ? <div className="edit-field"><input value={value} onChange={event => setValue(event.target.value)} autoFocus/><button onClick={() => save(field)} disabled={busy}>Lưu</button><button className="text-button" onClick={() => setEditing(undefined)}>Hủy</button></div> : <div className="field-value"><strong>{field.normalized_value || field.raw_value || '—'}</strong>{editable && <button aria-label={`Sửa ${field.field_key}`} onClick={() => { setEditing(field.id); setValue(field.normalized_value || field.raw_value); }}>✎</button>}</div>}</div>) : <p className="empty">Chọn tài liệu có dữ liệu OCR để xem.</p>}</div></section>;
}

function FindingsPanel({ findings, busy, reasons, setReasons, onDecide }: { findings: Finding[]; busy: string; reasons: Record<string, string>; setReasons: React.Dispatch<React.SetStateAction<Record<string, string>>>; onDecide: (finding: Finding, decision: 'accept' | 'dismiss' | 'escalate') => void }) {
  const openCount = findings.filter(isActiveFinding).length;
  return <section className="review-panel findings-panel"><div className="column-heading"><span>KẾT QUẢ KIỂM TRA</span><b>{openCount}</b></div><div className="finding-summary"><span><i className="red"/>{findings.filter(item => item.severity === 'error' && isActiveFinding(item)).length} lỗi</span><span><i className="gold"/>{findings.filter(item => item.severity === 'warning' && isActiveFinding(item)).length} cảnh báo</span></div>{findings.length ? findings.map(item => <article className={`finding-card ${item.severity} ${!isActiveFinding(item) ? 'resolved' : ''}`} key={item.id}><div className="finding-title"><span>{item.severity === 'error' ? '!' : item.severity === 'warning' ? '△' : 'i'}</span><div><b>{item.severity === 'error' ? 'Cần xử lý' : item.severity === 'warning' ? 'Cần lưu ý' : 'Thông tin'}</b><small>{item.source === 'rule' ? 'Quy tắc nghiệp vụ' : 'Gợi ý AI'}</small></div><Status value={item.status}/></div><p>{item.message}</p>{item.suggestion && <small className="suggestion-text">Gợi ý: {item.suggestion}</small>}{item.status === 'open' && <><input className="reason-input" value={reasons[item.id] ?? ''} onChange={event => setReasons(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Lý do xử lý (nếu cần)"/><div className="finding-actions"><button onClick={() => onDecide(item, 'accept')} disabled={!!busy}>Ghi nhận lỗi</button><button onClick={() => onDecide(item, 'dismiss')} disabled={!!busy}>Bỏ qua có lý do</button><button onClick={() => onDecide(item, 'escalate')} disabled={!!busy}>Chuyển cấp</button></div></>}</article>) : <Empty title="Không có cảnh báo" text="Chưa phát hiện vấn đề trong phiên bản hiện tại."/>}</section>;
}

function App() { return location.pathname.startsWith('/officer') ? <OfficerPortal/> : <CitizenPortal/>; }
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);

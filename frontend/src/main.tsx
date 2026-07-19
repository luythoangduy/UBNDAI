import React, { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowSquareOut, ArrowUp, ChatCircle as MessageCircle, Check, CheckCircle, ClipboardText, Clock, DownloadSimple as Download, FileMagnifyingGlass, FileText, Image as ImageUp, List as Menu, ListBullets as ListIcon, MagnifyingGlass, NotePencil as SquarePen, Printer, Scales, Sparkle, TextB as Bold, TextItalic as Italic, TextStrikethrough as Strikethrough, Warning, X } from '@phosphor-icons/react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { api, apiBlob, ApiError, idempotency, setToken, token } from './api';
import type { CaseDetail, CaseDocument, CaseRecord, ChatAction, ChatHistoryResponse, ChatResponse, ChatStarterResponse, DashboardSummary, DraftRevision, DraftTemplateInfo, ExtractedField, Finding, GeneratedDraft, ImageFormatReview, PortalRole, PreprocessResult, PreprocessStep, ProcedureCapabilities, ProcedureFormSchema, ProcedureRequirement, ProcedureSummary } from './types';
import { clarificationControlFor, latestInteractiveMessageIndex, messagesFromHistory, type ChatMessage } from './chat-flow';
import { diffDraftBlocks, type DiffBlock } from './draft-diff';
import { buildCaseQuery, clarificationAnswerEntries, formatBytes, formatDate, formatSubmissionValue, humanizeStatus, visibleSubmissionEntries } from './utils';
import { draftValuesFromCase, isMissingAnswer, validateClarifyingAnswers, type ClarifyingAnswers } from './citizen-form';
import { SignatureField } from './components/SignatureField';
import { PortalShell } from './components/PortalShell';
import { ThemeSelector } from './components/ThemeSelector';
import { ThemeProvider } from './theme/ThemeProvider';
import { composeSignedDocumentHtml } from './signature';
import './styles.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/primitives.css';
import './styles/citizen-premium.css';
import './styles/application-management.css';
import { isApplicationManagementPath, legacyReviewCaseId } from './application-management-routing';

const ApplicationManagementRouter = React.lazy(() => import('./app/AppRouter').then(module => ({ default: module.ApplicationManagementRouter })));
const ManagedReviewWorkspace = React.lazy(() => import('./features/officer-review/ReviewWorkspace').then(module => ({ default: module.ReviewWorkspace })));

const procedureNames: Record<string, string> = {};
const rememberProcedureNames = (items: ProcedureSummary[]) => items.forEach(item => { procedureNames[item.id] = item.name; });
const activeFindingStatuses = new Set<Finding['status']>(['open', 'accepted', 'escalated']);
const isActiveFinding = (finding: Finding) => activeFindingStatuses.has(finding.status);

function Shell({ children, role }: { children: React.ReactNode; role: PortalRole }) {
  return <PortalShell role={role} themeControl={<ThemeSelector compact />}>{children}</PortalShell>;
}

function Login({ role, onSuccess }: { role: PortalRole; onSuccess: () => void }) {
  const [username, setUsername] = useState(role === 'citizen' ? 'citizen.demo' : 'officer.demo');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    if (password.length < 8) { setError('Mật khẩu cần tối thiểu 8 ký tự.'); setBusy(false); return; }
    try {
      const result = await api<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
      setToken(result.access_token, role); onSuccess();
    } catch (cause) {
      const apiError = cause as ApiError;
      setError(apiError.status === 401 ? 'Tên đăng nhập hoặc mật khẩu không đúng.' : apiError.message || 'Không thể đăng nhập, vui lòng thử lại.');
    } finally { setBusy(false); }
  };
  const showDemoCredentials = import.meta.env.VITE_SHOW_DEMO_CREDENTIALS === 'true';
  return <Shell role={role}>
    <main id="main-content" className="login-page">
      <section className="login-story" aria-labelledby="login-story-title">
        <span className="eyebrow">Dịch vụ công thông minh</span>
        <h1 id="login-story-title">{role === 'citizen' ? 'Chuẩn bị hồ sơ đúng ngay từ lần đầu.' : 'Một không gian làm việc, toàn bộ căn cứ cần thiết.'}</h1>
        <p>{role === 'citizen' ? 'Được hướng dẫn từng bước, kiểm tra giấy tờ và theo dõi hồ sơ minh bạch.' : 'Tiếp nhận, đối chiếu OCR, xử lý cảnh báo và lưu vết mọi quyết định.'}</p>
        <div className="trust-row" aria-label="Cam kết dịch vụ">
          <span><CheckCircle aria-hidden="true" />Dữ liệu riêng tư</span>
          <span><CheckCircle aria-hidden="true" />Có căn cứ</span>
          <span><CheckCircle aria-hidden="true" />Có người kiểm tra</span>
        </div>
      </section>
      <form className="login-card" onSubmit={submit} aria-labelledby="login-title">
        <div className="login-icon" aria-hidden="true">{role === 'citizen' ? 'CN' : 'CB'}</div>
        <span className="eyebrow">{role === 'citizen' ? 'Cổng công dân' : 'Dành cho cán bộ'}</span>
        <h2 id="login-title">Đăng nhập hệ thống</h2>
        <p className="muted">Sử dụng tài khoản được cấp để tiếp tục.</p>
        <label>Tên đăng nhập<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} /></label>
        <label>Mật khẩu<input autoComplete="current-password" type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Nhập mật khẩu" /></label>
        {error && <div className="alert error" role="alert">{error}</div>}
        <button className="primary wide" disabled={busy}>{busy ? 'Đang xác thực…' : 'Đăng nhập'}</button>
        {showDemoCredentials && <small className="demo-hint">Tài khoản demo dùng mật khẩu <code>ChangeMe123!</code></small>}
      </form>
    </main>
  </Shell>;
}

type ReviewedImage = { file: File; review: ImageFormatReview };

function ClarificationPrompt({ questions, disabled, onPrepareAnswer }: { questions: string[]; disabled: boolean; onPrepareAnswer: (value: string) => void }) {
  const question = questions[0];
  const control = clarificationControlFor(question);
  return <div className="clarifying-block">
    <div className="clarifying-progress">Bước 2/3 · Cá nhân hóa hồ sơ</div>
    {questions.map((item, index) => <p key={item} className="clarifying-question">{index + 1}. {item}</p>)}
    {control === 'boolean' ? <div className="answer-chips" aria-label={`Trả lời: ${question}`}><button onClick={() => onPrepareAnswer('Có')} disabled={disabled}>Có</button><button onClick={() => onPrepareAnswer('Không')} disabled={disabled}>Không</button><button onClick={() => onPrepareAnswer('Tôi chưa rõ')} disabled={disabled}>Chưa rõ</button></div> : <label className="clarifying-answer-field"><span>{control === 'number' ? 'Nhập số' : control === 'date' ? 'Chọn ngày' : 'Câu trả lời của bạn'}</span><input type={control} min={control === 'number' ? 0 : undefined} onChange={event => onPrepareAnswer(event.target.value)} disabled={disabled} placeholder={control === 'number' ? 'Ví dụ: 5' : control === 'text' ? 'Nhập câu trả lời…' : undefined}/></label>}
    {questions.length > 1 && <small className="clarifying-hint">Bạn có thể trả lời thêm các câu còn lại trong cùng tin nhắn.</small>}
  </div>;
}

function DocumentReviewMessage({ item, onContinue, showProcedurePicker, procedures, onSelectProcedure }: { item: ReviewedImage; onContinue: () => void; showProcedurePicker?: boolean; procedures: ProcedureSummary[]; onSelectProcedure: (procedureId: string) => void }) {
  const [procedureId, setProcedureId] = useState('');
  const issues = item.review.layout_findings;
  return <section className="chat-document-review">
    <div className="chat-document-review__heading"><span>AI</span><div><b>Đã rà soát ảnh giấy tờ</b><small>{item.file.name} · {item.review.width} × {item.review.height} px</small></div></div>
    <div className="chat-review-brief"><b>{issues.length ? `Có ${issues.length} cảnh báo chất lượng ảnh` : 'Ảnh sẵn sàng để AI hỗ trợ điền'}</b><p>{issues.length ? issues[0].message : 'Bạn có thể tiếp tục sang biểu mẫu để kiểm tra và bổ sung thông tin.'}</p><small>Cảnh báo ảnh không chặn việc tiếp tục.</small></div>
    {showProcedurePicker ? <form className="chat-repair-form" onSubmit={event => { event.preventDefault(); if (procedureId) onSelectProcedure(procedureId); }}><label>Chọn biểu mẫu cần điền<select value={procedureId} onChange={event => setProcedureId(event.target.value)}><option value="">Chọn biểu mẫu</option>{procedures.map(procedure => <option key={procedure.id} value={procedure.id}>{procedure.name}</option>)}</select></label><button className="primary" disabled={!procedureId}>Đi tới phần điền →</button></form> : <button className="primary chat-document-review__action" onClick={onContinue}>Điền thông tin →</button>}
  </section>;
}

function CitizenAssistant({ activeCaseId, resetKey, onCaseChanged, onChecklist, onStartProcedure, onSelectTemplate, onReviewImage, reviewedImage, onRepairImage, showRepairForm, reviewProcedures = [], onSelectRepairProcedure, selectedContext }: { activeCaseId?: string; resetKey: number; onCaseChanged?: (caseId: string) => void | Promise<void>; onChecklist?: (caseId: string) => void; onStartProcedure?: (procedureId: string) => void; onSelectTemplate?: (procedureId: string, templateId: string) => void; onReviewImage?: () => void; reviewedImage?: ReviewedImage; onRepairImage?: () => void; showRepairForm?: boolean; reviewProcedures?: ProcedureSummary[]; onSelectRepairProcedure?: (procedureId: string) => void; selectedContext?: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: 'Đang kết nối kho thủ tục và nguồn chính thức…' }]);
  const [message, setMessage] = useState(''); const [caseId, setCaseId] = useState<string | undefined>(activeCaseId); const [busy, setBusy] = useState(false);
  // Responses render atomically: the previous simulated typing animation made
  // the conversation feel blocked and could leave controls disabled.
  const [streamedText] = useState('');
  const [streaming, setStreaming] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const followChatRef = useRef(true);
  const requestGenerationRef = useRef(0);
  const requestInFlightRef = useRef(false);
  const locallyCreatedCaseRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (followChatRef.current) logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);
  // Textarea tự giãn theo nội dung tới trần 200px rồi mới cuộn — CSS thuần không
  // làm được vì phải đọc scrollHeight sau mỗi lần nội dung đổi.
  useEffect(() => {
    const element = inputRef.current;
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }, [message]);
  useEffect(() => {
    if (activeCaseId && locallyCreatedCaseRef.current === activeCaseId) {
      locallyCreatedCaseRef.current = undefined;
      return;
    }
    const generation = ++requestGenerationRef.current;
    const controller = new AbortController();
    requestInFlightRef.current = false;
    setBusy(false); setStreaming(false); setMessage(''); setCaseId(activeCaseId);
    setMessages([{ role: 'assistant', text: activeCaseId ? 'Đang tải cuộc trò chuyện…' : 'Đang kết nối kho thủ tục và nguồn chính thức…' }]);
    const load = activeCaseId
      ? api<ChatHistoryResponse>(`/chat/${activeCaseId}/messages`, { signal: controller.signal }).then(history => {
          const restored = messagesFromHistory(history);
          return restored.length ? restored : [{ role: 'assistant' as const, text: 'Cuộc trò chuyện này chưa có tin nhắn. Bạn có thể tiếp tục ngay.' }];
        })
      : api<ChatStarterResponse>('/chat/starter', { signal: controller.signal }).then(response => [{ role: 'assistant' as const, text: response.reply, response }]);
    load.then(restored => { if (requestGenerationRef.current === generation) setMessages(restored); })
      .catch(cause => {
        if (controller.signal.aborted || requestGenerationRef.current !== generation) return;
        setMessages([{ role: 'assistant', text: activeCaseId
          ? `Chưa tải được lịch sử trò chuyện: ${(cause as Error).message}. Bạn có thể thử chọn lại cuộc trò chuyện.`
          : 'Xin chào! Bạn cần thực hiện thủ tục gì? Hãy mô tả bằng lời của bạn.' }]);
      });
    return () => controller.abort();
  }, [activeCaseId, resetKey]);
  const submitMessage = async (rawValue: string) => {
    const value = rawValue.trim(); if (!value || requestInFlightRef.current) return;
    const generation = requestGenerationRef.current;
    const submittingCaseId = caseId;
    requestInFlightRef.current = true;
    followChatRef.current = true;
    setMessages(current => [...current, { role: 'user', text: value }]); setMessage(''); setBusy(true);
    try {
      const payloadMessage = selectedContext ? `${value}\n\n[Ngữ cảnh đang chọn]: "${selectedContext}"` : value;
      const response = await api<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ message: payloadMessage, ...(submittingCaseId ? { case_id: submittingCaseId } : {}) }) });
      if (requestGenerationRef.current !== generation) return;
      const responseCaseId = response.case_id ?? submittingCaseId;
      setCaseId(responseCaseId);
      if (!submittingCaseId && responseCaseId) locallyCreatedCaseRef.current = responseCaseId;
      if (responseCaseId) await onCaseChanged?.(responseCaseId);
      if (requestGenerationRef.current !== generation) return;
      setMessages(current => [...current, { role: 'assistant', text: response.reply, response }]);
      if (response.kind === 'checklist' && onChecklist && response.case_id) onChecklist(response.case_id);
    } catch (cause) {
      if (requestGenerationRef.current === generation) setMessages(current => [...current, { role: 'assistant', text: `Chưa thể kết nối trợ lý: ${(cause as Error).message}` }]);
    } finally {
      if (requestGenerationRef.current === generation) { requestInFlightRef.current = false; setBusy(false); setStreaming(false); }
    }
  };
  const send = (event: FormEvent) => { event.preventDefault(); void submitMessage(message); };
  const submitOnEnter = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (event.currentTarget.value.trim() && !busy) event.currentTarget.form?.requestSubmit();
  };
  const runAction = (action: ChatAction) => {
    if (busy) return;
    if (action.kind === 'send_message') void submitMessage(action.value);
    else if (action.kind === 'start_form') onStartProcedure?.(action.value);
    else window.open(action.value, '_blank', 'noopener,noreferrer');
  };
  const iconFor = (icon: ChatAction['icon']) => {
    const props = { size: 20, weight: 'bold' as const, 'aria-hidden': true };
    if (icon === 'search') return <MagnifyingGlass {...props}/>;
    if (icon === 'checklist') return <ClipboardText {...props}/>;
    if (icon === 'clock') return <Clock {...props}/>;
    if (icon === 'template') return <FileText {...props}/>;
    if (icon === 'form') return <Sparkle {...props}/>;
    return <ArrowSquareOut {...props}/>;
  };
  const chooseTemplate = (response: ChatMessage['response'], templateId: string) => {
    if (response?.procedure_id) onSelectTemplate?.(response.procedure_id, templateId);
  };
  const latestInteractiveIndex = latestInteractiveMessageIndex(messages);
  // Rail nguồn hiển thị căn cứ của câu trả lời mới nhất (pattern Perplexity/NotebookLM):
  // tách metadata khỏi dòng đọc để hội thoại liền mạch.
  const latestEvidence = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const evidence = messages[index].response?.evidence;
      if (evidence?.length) return evidence;
    }
    return undefined;
  }, [messages]);
  return (
    <div className="chat-dock open">
      <section className="assistant-card docked" aria-label="Trợ lý hồ sơ AI">
        <div className="panel-heading">
          <h2>Chuẩn bị hồ sơ bằng một cuộc trò chuyện</h2>
          <span className="online"><i/>Đang trực tuyến</span>
        </div>
          <div className="chat-log" ref={logRef} aria-live="polite" onScroll={event => { const element = event.currentTarget; followChatRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 72; }}>
            {messages.map((item, index) => <article key={item.id ?? index} className={`bubble ${item.role}`}><span>{item.role === 'assistant' ? 'AI' : 'Bạn'}</span><div><p>{item.text}</p>{!!item.response?.evidence?.length && <div className="source-trace"><div className="trace-heading"><b>Đã kiểm chứng nguồn</b></div>{item.response.evidence.map(step => <a key={`${step.id}-${step.detail}`} className={`trace-step ${step.status}`} href={step.source_url || undefined} target={step.source_url ? '_blank' : undefined} rel="noreferrer"><i>{step.status === 'ready' || step.status === 'cache_hit' ? '✓' : '!'}</i><span><b>{step.label}</b><small>{step.detail}</small></span></a>)}</div>}{index === latestInteractiveIndex && !!item.response?.actions?.length && <div className={`chat-actions${item.response.actions.every(action => action.icon === 'search') ? ' as-cards' : ''}`}>{item.response.actions.map(action => <button key={action.id} className={action.primary ? 'featured' : ''} onClick={() => runAction(action)} disabled={busy || streaming}><i>{iconFor(action.icon)}</i><span><b>{action.label}</b><small>{action.description}</small></span></button>)}</div>}{index === latestInteractiveIndex && !!item.response?.templates?.length && <div className="template-results"><div className="template-heading"><b>Biểu mẫu phù hợp</b><small>đã đối chiếu nguồn</small></div>{item.response.templates.map((template, templateIndex) => <article key={template.template_id} className={`template-card ${templateIndex === 0 && template.field_count > 0 ? 'recommended' : ''}`}><div><span className={template.official_source ? 'official-mark' : 'source-mark'}>{templateIndex === 0 && template.field_count > 0 ? '★ ĐỀ XUẤT · ' : ''}{template.official_source ? 'NGUỒN CHÍNH PHỦ' : 'NGUỒN THAM KHẢO'}</span><h4>{template.title}</h4><p>{template.field_count ? `${template.field_count} trường · ` : ''}{template.source_label}</p></div>{template.field_count > 0 && item.response?.procedure_id ? <button className="use-template" onClick={() => chooseTemplate(item.response, template.template_id)} disabled={busy || streaming}>Dùng mẫu này →</button> : <a href={template.source_url} target="_blank" rel="noreferrer">Mở mẫu ↗</a>}<details><summary>{template.citations.length} căn cứ nguồn</summary>{template.citations.map(source => <a key={`${source.document_number}-${source.source_url}`} href={source.source_url} target="_blank" rel="noreferrer"><b>{source.document_number}</b><span>{source.issuing_authority} · {source.role}</span></a>)}</details></article>)}</div>}{index === latestInteractiveIndex && !!item.response?.clarifying_questions?.length && <ClarificationPrompt questions={item.response.clarifying_questions} disabled={busy || streaming} onPrepareAnswer={setMessage}/>} {!!item.response?.citations?.length && <details><summary>{item.response.citations.length} nguồn tham khảo</summary>{item.response.citations.map(citation => <p key={citation.index} className="citation">[{citation.index}] {citation.section ?? citation.excerpt ?? 'Nguồn thủ tục'}{citation.source_url && <> · <a href={citation.source_url} target="_blank" rel="noreferrer">Xem nguồn chính thức ↗</a></>}</p>)}</details>}</div></article>)}
            {reviewedImage && onRepairImage && onSelectRepairProcedure && <article className="bubble assistant document-review-bubble"><span>AI</span><div><DocumentReviewMessage item={reviewedImage} onContinue={onRepairImage} showProcedurePicker={showRepairForm} procedures={reviewProcedures} onSelectProcedure={onSelectRepairProcedure}/></div></article>}
            {busy && <article className="bubble assistant"><span>AI</span><div className="skeleton-loader"><div className="skeleton-line"></div><div className="skeleton-line short"></div></div></article>}
            {streamedText && <article className="bubble assistant"><span>AI</span><div><p>{streamedText}<span className="cursor">|</span></p></div></article>}
          </div>
          <form className="chat-input" onSubmit={send}>
            {selectedContext && <div className="chat-context-banner"><strong>Đang chọn:</strong> "{selectedContext.length > 40 ? selectedContext.substring(0, 40) + '...' : selectedContext}"</div>}
            <div className="composer">
              <button type="button" className="composer-attach" onClick={onReviewImage} title="Rà soát ảnh giấy tờ" aria-label="Rà soát ảnh giấy tờ"><ImageUp size={17}/></button>
              <textarea ref={inputRef} aria-label="Nội dung cần hỏi" rows={1} maxLength={4000} enterKeyHint="send" value={message} onChange={event => setMessage(event.target.value)} onKeyDown={submitOnEnter} placeholder="Mô tả thủ tục hành chính bạn cần hỗ trợ…"/>
              <button className="composer-send" disabled={!message.trim() || busy || streaming} aria-label="Gửi câu hỏi"><ArrowUp size={17}/></button>
            </div>
          </form>
          <p className="ai-note">Enter để gửi · Shift + Enter để xuống dòng · Bạn luôn duyệt trước khi dùng</p>
        </section>
        {!!latestEvidence?.length && (
          <aside className="evidence-rail" aria-label="Nguồn đã kiểm chứng cho câu trả lời mới nhất">
            <div className="evidence-rail-head">
              <b>Căn cứ cho câu trả lời</b>
              <small>Căn cứ của câu trả lời mới nhất</small>
            </div>
            <div className="evidence-rail-body">
              {latestEvidence.map(step => {
                const verified = step.status === 'ready' || step.status === 'cache_hit';
                return (
                  <a
                    key={`${step.id}-${step.detail}`}
                    className={`trace-step ${step.status}`}
                    href={step.source_url || undefined}
                    target={step.source_url ? '_blank' : undefined}
                    rel="noreferrer"
                  >
                    <i aria-hidden="true">{verified ? <Check size={14} weight="bold"/> : <Warning size={14} weight="fill"/>}</i>
                    <span>
                      <b>{step.label}</b>
                      <small>{step.detail}</small>
                    </span>
                  </a>
                );
              })}
            </div>
          </aside>
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

function renderGeneratedDraftHtml(text: string): string {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  return lines.map((line, index) => {
    const escaped = escapeHtml(line).replace(
      /\[CHƯA CÓ: ([^\]]+)\]/g,
      '<strong>⚠ CẦN BỔ SUNG: $1</strong>',
    );
    if (index === 0 || (line === line.toUpperCase() && line.length < 100)) return `<h2>${escaped}</h2>`;
    return `<p>${escaped}</p>`;
  }).join('\n');
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

function WordWorkspace({ content, fileName, signature, onSignatureChange, signerName, onSignerNameChange, onSelectionChange, onContentChange, onDownload, onDownloadOfficial, downloading, downloadingOfficial, statusHint, source }: { content: string; fileName: string; signature: string; onSignatureChange: (value: string) => void; signerName: string; onSignerNameChange: (value: string) => void; onSelectionChange?: (text: string) => void; onContentChange?: (html: string) => void; onDownload?: (html: string) => void; onDownloadOfficial?: () => void; downloading?: boolean; downloadingOfficial?: boolean; statusHint?: string; source?: TemplateSource }) {
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
        {onDownload && <button className="word-download" onClick={() => onDownload(composeSignedDocumentHtml(editor?.getHTML() ?? content, signature, signerName))} disabled={downloading}><Download size={14}/>{downloading ? 'Đang tạo DOCX…' : 'Tải xuống DOCX'}</button>}
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
          <span><Scales size={15} weight="bold" aria-hidden="true"/> {source.label}</span>
          <span className="word-source-links">{source.links.map(link => <a key={link.url} href={link.url} target="_blank" rel="noreferrer">{link.title} <ArrowSquareOut size={13} aria-hidden="true"/></a>)}</span>
        </div>
      )}
      <div className="word-ruler">{Array.from({ length: 17 }, (_, index) => <i key={index}/>)}</div>
      <div className="word-canvas">
        <div className="word-page" style={{ transform: `scale(${zoom / 100})` }}>
          <div className="word-watermark">DỰ THẢO — KHÔNG CÓ GIÁ TRỊ PHÁP LÝ</div>
          <EditorContent editor={editor}/>
          <SignatureField value={signature} onChange={onSignatureChange} signerName={signerName} onSignerNameChange={onSignerNameChange}/>
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


function ImageFormatReviewDialog({ onClose, onContinue }: { onClose: () => void; onContinue: (file: File, review: ImageFormatReview) => void }) {
  const [file, setFile] = useState<File>();
  const [preview, setPreview] = useState('');
  const [review, setReview] = useState<ImageFormatReview>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const inspect = async () => {
    if (!file) return;
    setBusy(true); setError(''); setReview(undefined);
    try {
      const body = new FormData();
      body.append('file', file);
      const result = await api<ImageFormatReview>('/citizen/format-review', { method: 'POST', body });
      setReview(result);
      // A capture warning is advisory: move straight into the chat workflow
      // instead of making the citizen confirm a second, blocking step.
      onContinue(file, result);
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  };

  return <div className="image-review-modal" role="dialog" aria-modal="true" aria-labelledby="image-review-title">
    <section className="image-review-dialog">
      <header><div><span className="eyebrow">KIỂM TRA TRƯỚC KHI OCR</span><h2 id="image-review-title">Rà soát ảnh giấy tờ</h2><p>Ảnh chỉ được phân tích chất lượng, không lưu lại và không dùng để kết luận tính hợp lệ của hồ sơ.</p></div><button className="close-btn" aria-label="Đóng" onClick={onClose}><X size={18}/></button></header>
      <div className="image-review-content">
        <label className={`image-review-dropzone ${file ? 'has-file' : ''}`}>
          <input type="file" accept="image/jpeg,image/png" onChange={event => { setFile(event.target.files?.[0]); setReview(undefined); setError(''); }}/>
          {preview ? <img src={preview} alt="Bản xem trước ảnh giấy tờ"/> : <><ImageUp size={28}/><b>Chọn ảnh giấy tờ</b><small>Hỗ trợ JPEG hoặc PNG, tối đa 10 MB</small></>}
        </label>
        {file && <div className="image-review-file"><span><b>{file.name}</b><small>{formatBytes(file.size)} · {file.type || 'không xác định'}</small></span><button className="ghost compact" onClick={() => { setFile(undefined); setReview(undefined); }}>Đổi ảnh</button></div>}
        {error && <p className="image-review-error" role="alert">{error}</p>}
        {review && <section className={`image-review-result ${review.layout_findings.length ? 'needs_attention' : review.status}`} aria-live="polite"><div><span>{review.layout_findings.length ? '!' : '✓'}</span><div><b>{review.layout_findings.length ? 'Có cảnh báo ảnh — vẫn có thể tiếp tục' : 'Ảnh sẵn sàng để OCR'}</b><small>{review.width} × {review.height} px · {formatBytes(review.file_size_bytes)}</small></div></div><ul>{review.checks.filter(check => check.code !== 'resolution_low').map(check => <li key={check.code} className={check.status}><i>{check.status === 'pass' ? '✓' : '!'}</i>{check.message}</li>)}</ul></section>}
      </div>
      <footer><button className="ghost" onClick={onClose}>Đóng</button><button className="primary" onClick={inspect} disabled={!file || busy}>{busy ? 'Đang rà soát…' : 'Rà soát định dạng'}</button></footer>
    </section>
  </div>;
}

function ProcedureForImageDialog({ file, procedures, onSelect, onClose }: { file: File; procedures: ProcedureSummary[]; onSelect: (procedureId: string) => void; onClose: () => void }) {
  return <div className="image-review-modal" role="dialog" aria-modal="true" aria-labelledby="procedure-for-image-title">
    <section className="image-review-dialog procedure-for-image-dialog">
      <header><div><span className="eyebrow">BƯỚC 2 · CHỌN THỦ TỤC</span><h2 id="procedure-for-image-title">AI sẽ điền ảnh này vào hồ sơ nào?</h2><p><b>{file.name}</b> đã sẵn sàng. Chọn thủ tục để hệ thống dùng đúng mẫu và trường OCR; sau đó OCR sẽ tự chạy.</p></div><button className="close-btn" aria-label="Đóng" onClick={onClose}><X size={18}/></button></header>
      <div className="procedure-for-image-list">{procedures.map(procedure => <button key={procedure.id} onClick={() => onSelect(procedure.id)}><FileText size={19}/><span><b>{procedure.name}</b><small>{procedure.agency}</small></span><i>→</i></button>)}</div>
      <footer><button className="ghost" onClick={onClose}>Để sau</button></footer>
    </section>
  </div>;
}

function ChatPortal() {
  const [logged, setLogged] = useState(!!token()); const [cases, setCases] = useState<CaseRecord[]>([]); const [current, setCurrent] = useState<CaseRecord | null>(null);
  const [conversationResetKey, setConversationResetKey] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [file, setFile] = useState<File>(); const [consent, setConsent] = useState(false);
  const [notice, setNotice] = useState(''); const [busy, setBusy] = useState('');
  const [imageReviewOpen, setImageReviewOpen] = useState(false);
  const [reviewedImage, setReviewedImage] = useState<ReviewedImage>();
  const [procedureForImageOpen, setProcedureForImageOpen] = useState(false);
  const [pendingOcrFile, setPendingOcrFile] = useState<File>();
  const [procedures, setProcedures] = useState<ProcedureSummary[]>([]);
  const [formSchema, setFormSchema] = useState<ProcedureFormSchema>();
  const [capabilities, setCapabilities] = useState<ProcedureCapabilities>();
  const [selectedTemplate, setSelectedTemplate] = useState<DraftTemplateInfo>();
  const [generatedDraft, setGeneratedDraft] = useState<GeneratedDraft>();
  const [draftStage, setDraftStage] = useState<'collect' | 'generating' | 'ready'>('collect');
  const [panelOpen, setPanelOpen] = useState(() => localStorage.getItem('ubndai.draft.panel') !== 'closed');
  const [revisionInstruction, setRevisionInstruction] = useState('');
  const [proposedRevision, setProposedRevision] = useState<DraftRevision>();
  const [diffBlocks, setDiffBlocks] = useState<DiffBlock[]>([]);
  const [docContent, setDocContent] = useState('');
  const [signature, setSignature] = useState('');
  const [signerName, setSignerName] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [extractedFields, setExtractedFields] = useState<ExtractedField[]>();
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [ocrPhase, setOcrPhase] = useState<OcrPhase>('idle');
  const [prepSteps, setPrepSteps] = useState<PreprocessStep[]>([]);
  const [prepIndex, setPrepIndex] = useState(0);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const caseSelectionRef = useRef(0);
  const requiredFields = formSchema?.fields.filter(field => field.required) ?? [];
  const readiness = requiredFields.length ? Math.round(requiredFields.filter(field => draftValues[field.key]?.trim()).length / requiredFields.length * 100) : 0;
  const reviewCount = extractedFields?.filter(item => item.confidence < 0.85).length ?? 0;
  const missingFields = Array.from(new Set([
    ...requiredFields.filter(field => !draftValues[field.key]?.trim()).map(field => field.key),
    ...(generatedDraft?.missing_required_fields ?? []).filter(key => !draftValues[key]?.trim()),
  ]));
  const updateDraftValue = (key: string, value: string) => setDraftValues(values => ({ ...values, [key]: value }));
  const setDraftPanelOpen = (open: boolean) => { setPanelOpen(open); localStorage.setItem('ubndai.draft.panel', open ? 'open' : 'closed'); };

  useEffect(() => {
    const expired = () => { setLogged(false); setNotice('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.'); };
    window.addEventListener('citizen-session-expired', expired);
    return () => window.removeEventListener('citizen-session-expired', expired);
  }, []);

  // Drawer lịch sử là lớp phủ — Esc phải đóng được để không nhốt người dùng bằng bàn phím.
  useEffect(() => {
    if (!historyOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setHistoryOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [historyOpen]);

  const refresh = async () => setCases(await api<CaseRecord[]>('/citizen/cases'));
  useEffect(() => {
    if (!logged) return;
    Promise.all([refresh(), api<ProcedureSummary[]>('/procedures').then(items => { rememberProcedureNames(items); setProcedures(items); })])
      .catch(cause => setNotice((cause as Error).message));
  }, [logged]);
  const run = async (name: string, work: () => Promise<void>) => { setBusy(name); setNotice(''); try { await work(); } catch (cause) { setNotice((cause as Error).message); } finally { setBusy(''); } };
  
  const startDraftFromTemplate = (procedureId: string, templateId?: string, sourceUrl?: string, sourceTitle?: string) => {
    run('create', async () => {
      const procedure = procedures.find(item => item.id === procedureId);
      const imported = sourceUrl ? await api<DraftTemplateInfo>('/drafts/templates/import', { method: 'POST', body: JSON.stringify({ procedure_id: procedureId, source_url: sourceUrl, title: sourceTitle ?? 'Biểu mẫu từ nguồn chính thức' }) }) : undefined;
      const [templates, caps, schema] = await Promise.all([
        imported ? Promise.resolve([imported]) : api<DraftTemplateInfo[]>(`/drafts/templates/${procedureId}`),
        api<ProcedureCapabilities>(`/procedures/${procedureId}/capabilities`),
        api<ProcedureFormSchema>(`/procedures/${procedureId}/form-schema`),
      ]);
      const template = imported ?? templates.find(item => item.id === templateId) ?? templates[0];
      if (!template) throw new Error('Mẫu này chỉ có trên nguồn ngoài và chưa hỗ trợ sinh tự động.');

      const item = current?.procedure_id === procedureId ? current : await api<CaseRecord>('/citizen/cases', { method: 'POST', body: JSON.stringify({ procedure_id: procedureId, locality_code: procedure?.locality_code ?? 'national' }) });
      const currentValues = draftValuesFromCase(template.fields, item.form_data);
      setCurrent(item);
      setSelectedTemplate(template);
      setFormSchema(schema);
      setCapabilities(caps);
      setDraftValues(currentValues);
      setGeneratedDraft(undefined);
      setDraftStage('collect');
      setDocContent('');
      setSignature('');
      setSignerName('');
      setProposedRevision(undefined);
      setDiffBlocks([]);
      setRevisionInstruction('');
      setSelectedText('');
      setDraftPanelOpen(true);
      setNotice('Đã mở biểu mẫu. Bạn có thể bổ sung dữ liệu rồi sinh bản nháp để rà soát.');
      await refresh();
    });
  };

  const generateDraft = () => selectedTemplate && run('generate', async () => {
    setDraftStage('generating'); setProposedRevision(undefined); setDiffBlocks([]); setPanelOpen(true);
    try {
      const [draft] = await Promise.all([
        api<GeneratedDraft>('/drafts/generate', { method: 'POST', body: JSON.stringify({ procedure_id: selectedTemplate.procedure_id, template_id: selectedTemplate.id, values: draftValues, allow_incomplete: true }) }),
        sleep(650),
      ]);
      setGeneratedDraft(draft); setDocContent(renderGeneratedDraftHtml(draft.rendered_text)); setDraftStage('ready');
      setNotice(draft.ready_for_review ? 'Bản nháp đã sẵn sàng để rà soát.' : `Đã sinh bản nháp với ${draft.missing_required_fields.length} chỗ cần bổ sung.`);
    } catch (cause) { setDraftStage('collect'); throw cause; }
  });

  const reviseDraft = () => run('revise', async () => {
    if (!docContent || !revisionInstruction.trim()) return;
    const revision = await api<DraftRevision>('/drafts/revise', { method: 'POST', body: JSON.stringify({ html: docContent, instruction: revisionInstruction, selected_text: selectedText || undefined }) });
    setProposedRevision(revision); setDiffBlocks(diffDraftBlocks(docContent, revision.revised_html));
  });

  const applyRevision = () => {
    if (!proposedRevision) return;
    setDocContent(proposedRevision.revised_html); setProposedRevision(undefined); setDiffBlocks([]); setRevisionInstruction(''); setSelectedText('');
    setNotice('Đã áp dụng thay đổi AI sau khi bạn duyệt diff.');
  };

  const upload = (selectedFile?: File | React.MouseEvent<HTMLButtonElement>) => {
    const imageFile = selectedFile instanceof File ? selectedFile : file;
    return current && imageFile && run('upload', async () => {
    setOcrPhase('upload'); setPrepSteps([]); setPrepIndex(0); setExtractedFields(undefined);
    setPreviewUrl(URL.createObjectURL(imageFile));

    const intent = await api<{ document_id: string; upload_url: string }>(`/citizen/cases/${current.id}/documents/upload-intents`, { method: 'POST', body: JSON.stringify({ filename: imageFile.name, content_type: imageFile.type, size_bytes: imageFile.size }) });
    const uploaded = await fetch(intent.upload_url, { method: 'PUT', body: imageFile, headers: { 'Content-Type': 'application/octet-stream', Authorization: `Bearer ${token()}` } });
    if (!uploaded.ok) throw new Error('Không thể tải file lên');

    setOcrPhase('prep');
    // OCR (LLM) chạy song song trong lúc minh hoạ các bước tiền xử lý
    const completePromise = api<{ document: CaseDocument, fields: ExtractedField[] }>(`/citizen/documents/${intent.document_id}/complete`, { method: 'POST', body: JSON.stringify({ sha256: await checksum(imageFile) }) });
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
    if (selectedTemplate) {
      const draft = await api<GeneratedDraft>('/drafts/generate', { method: 'POST', body: JSON.stringify({ procedure_id: selectedTemplate.procedure_id, template_id: selectedTemplate.id, values: merged, allow_incomplete: true }) });
      setGeneratedDraft(draft); setDocContent(renderGeneratedDraftHtml(draft.rendered_text)); setDraftStage('ready');
    } else {
      setDocContent(buildDynamicFormHtml(formSchema, merged));
    }
    await sleep(1400); // giữ màn bounding box đủ lâu để thấy các vùng nhận dạng trước khi chuyển sang DOCX
    setOcrPhase('ready');
    setNotice(`AI đã nhận dạng ${completeResp.fields.length} trường và điền vào tờ khai.`);
    await refreshCurrent(current.id);
    });
  };

  useEffect(() => {
    if (!pendingOcrFile || !current || !selectedTemplate || !formSchema || busy) return;
    setPendingOcrFile(undefined);
    void upload(pendingOcrFile);
  }, [pendingOcrFile, current, selectedTemplate, formSchema, busy]);

  if (!logged) return <Login role="citizen" onSuccess={() => setLogged(true)}/>;

  // Xuất DOCX từ chính HTML đang hiển thị trong editor (WYSIWYG — cách làm của C2):
  // người dân sửa gì trong tờ khai thì file tải xuống có đúng nội dung đó.
  const downloadDocx = (html: string) => run('docx', async () => {
    const filename = `${formSchema?.procedure_id ?? 'to-khai'}.docx`;
    const blob = selectedTemplate
      ? await apiBlob('/drafts/generate.docx', { method: 'POST', body: JSON.stringify({ procedure_id: selectedTemplate.procedure_id, template_id: selectedTemplate.id, values: draftValues, allow_incomplete: true }) })
      : await apiBlob('/drafts/export.docx', { method: 'POST', body: JSON.stringify({ html, filename }) });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = filename; anchor.click();
    URL.revokeObjectURL(url);
    setNotice('Đã tải xuống bản nháp DOCX.');
  });
  
  const submit = () => current && run('submit', async () => { 
    if (!consent) throw new Error('Vui lòng xác nhận đồng ý xử lý dữ liệu trước khi nộp.'); 
    const latest = await api<{ case: CaseRecord }>(`/citizen/cases/${current.id}`); 
    const updated = await api<CaseRecord>(`/citizen/cases/${current.id}`, { method: 'PATCH', body: JSON.stringify({ expected_version: latest.case.version, form_data: { ...draftValues, _signer_name: signerName.trim(), _draft_html: composeSignedDocumentHtml(docContent, signature, signerName), _readiness_score: readiness } }) });
    const item = await api<CaseRecord>(`/citizen/cases/${current.id}/submit`, { method: 'POST', headers: { 'Idempotency-Key': idempotency() }, body: JSON.stringify({ expected_version: updated.version, consent_version: 'privacy-v1', consent_accepted: true }) });
    setCurrent(item); 
    setNotice('Hồ sơ đã được chuyển tới cán bộ tiếp nhận.'); 
    await refresh(); 
  });
  const refreshCurrent = async (id: string) => { const detail = await api<{case: CaseRecord}>(`/citizen/cases/${id}`); setCurrent(detail.case); await refresh(); return detail.case; };
  const syncChatCase = async (caseId: string) => {
    const selection = ++caseSelectionRef.current;
    const detail = await api<{case: CaseRecord}>(`/citizen/cases/${caseId}`);
    if (caseSelectionRef.current !== selection) return;
    setCurrent(detail.case);
    await refresh();
  };
  const selectConversation = (item: CaseRecord) => {
    const selection = ++caseSelectionRef.current;
    setCurrent(item);
    setNotice('');
    api<{case: CaseRecord}>(`/citizen/cases/${item.id}`)
      .then(detail => { if (caseSelectionRef.current === selection) setCurrent(detail.case); })
      .catch(cause => { if (caseSelectionRef.current === selection) setNotice((cause as Error).message); });
  };
  const startNewConversation = () => {
    caseSelectionRef.current += 1;
    setCurrent(null); setConversationResetKey(value => value + 1); setNotice('');
    setSelectedTemplate(undefined); setFormSchema(undefined); setCapabilities(undefined); setGeneratedDraft(undefined);
    setDraftValues({}); setDocContent(''); setSignature(''); setSignerName(''); setProposedRevision(undefined); setDiffBlocks([]);
    setRevisionInstruction(''); setSelectedText(''); setReviewedImage(undefined); setPendingOcrFile(undefined); setFile(undefined);
    setProcedureForImageOpen(false); setDraftPanelOpen(false);
  };
  const handleChecklist = () => { setNotice('Đã tạo checklist theo trường hợp của bạn. Khi sẵn sàng, chọn mẫu ngay trong cuộc trò chuyện.'); };
  const startProcedureFromChat = (procedureId: string) => startDraftFromTemplate(procedureId);
  const source: TemplateSource | undefined = selectedTemplate ? {
    label: `${selectedTemplate.output_name} · bản ${selectedTemplate.version}`,
    links: selectedTemplate.legal_sources.map(item => ({ title: item.document_number, url: item.source_url })),
  } : undefined;
  const changeCount = diffBlocks.filter(block => block.type !== 'same').length;
  const continueWithReviewedImage = (reviewedFile: File, review: ImageFormatReview) => {
    setFile(reviewedFile);
    setReviewedImage({ file: reviewedFile, review });
    setPendingOcrFile(reviewedFile);
    setImageReviewOpen(false);
    
    // Auto-advance so the user doesn't feel the flow is "blocked"
    if (selectedTemplate) {
      setDraftPanelOpen(true);
    } else {
      setProcedureForImageOpen(true);
    }
  };

  return (
    <Shell role="citizen">
      <main id="main-content" className="citizen-page chat-first-page">
        <div className="chat-topline">
          <button type="button" className="history-toggle" aria-label="Lịch sử" aria-expanded={historyOpen} aria-controls="chat-history-drawer" onClick={() => setHistoryOpen(open => !open)}>
            <Menu size={17}/><span>Lịch sử</span>
          </button>
          <button type="button" className="topline-new" aria-label="Cuộc trò chuyện mới" onClick={() => { setHistoryOpen(false); startNewConversation(); }}><SquarePen size={15}/><span>Cuộc trò chuyện mới</span></button>
          <h1>Trợ lý thủ tục hành chính</h1>
          <div className="chat-first-meta"><span><i/>Nguồn chính thức</span><button className="ghost compact" onClick={() => { setToken('', 'citizen'); setLogged(false); }}>Đăng xuất</button></div>
        </div>
        {notice && <div className={`workspace-notice ${notice.includes('Đã') || notice.includes('đã') ? 'success' : ''}`} role="status">{notice}<button aria-label="Đóng thông báo" onClick={() => setNotice('')}>×</button></div>}
        <div className={`chat-first-workspace ${selectedTemplate && panelOpen ? 'with-draft' : ''}`}>
          {historyOpen && <div className="history-backdrop" onClick={() => setHistoryOpen(false)}/>}
          <aside id="chat-history-drawer" className={`history-sidebar ${historyOpen ? 'open' : ''}`} aria-hidden={!historyOpen} aria-label="Lịch sử trò chuyện">
            <div className="history-header">
              <span>Lịch sử trò chuyện</span>
              <button type="button" className="history-close" aria-label="Đóng lịch sử" onClick={() => setHistoryOpen(false)}><X size={16}/></button>
            </div>
            <div className="history-list">
              {cases.length === 0 ? <p className="muted" style={{ fontSize: 11, textAlign: 'center', marginTop: 20 }}>Chưa có lịch sử</p> : cases.map(c => {
                const title = c.procedure_id && c.procedure_id !== 'pending_guidance' ? procedures.find(p => p.id === c.procedure_id)?.name || c.procedure_id : 'Tư vấn thủ tục mới';
                return (
                  <button
                    key={c.id}
                    className={`history-item ${current?.id === c.id ? 'active' : ''}`}
                    tabIndex={historyOpen ? 0 : -1}
                    onClick={() => { selectConversation(c); setHistoryOpen(false); }}
                  >
                    {title}
                    <small>{formatDate(c.created_at)}</small>
                  </button>
                );
              })}
            </div>
          </aside>
          <CitizenAssistant activeCaseId={current?.id} resetKey={conversationResetKey} onCaseChanged={syncChatCase} onChecklist={handleChecklist} onStartProcedure={startProcedureFromChat} onSelectTemplate={startDraftFromTemplate} onReviewImage={() => setImageReviewOpen(true)} reviewedImage={reviewedImage} onRepairImage={() => { if (selectedTemplate) { setDraftPanelOpen(true); } else { setProcedureForImageOpen(true); } }} showRepairForm={procedureForImageOpen} reviewProcedures={procedures} onSelectRepairProcedure={procedureId => { setProcedureForImageOpen(false); startDraftFromTemplate(procedureId); }} selectedContext={selectedText}/>

          {selectedTemplate && !panelOpen && <button className="draft-launcher" onClick={() => setDraftPanelOpen(true)}><FileText size={18}/><span><b>Mở lại bản nháp</b><small>{readiness}% dữ liệu · {missingFields.length} chỗ thiếu</small></span><span>←</span></button>}

          {selectedTemplate && panelOpen && <aside className="draft-drawer" aria-label="Không gian sinh văn bản">
            <header className="draft-drawer-header">
              <div><span className="draft-status"><i/>BẢN NHÁP ĐANG LÀM</span><h2>{selectedTemplate.output_name}</h2><p>Mẫu {selectedTemplate.version} · kiểm tra {formatDate(selectedTemplate.source_checked_on)}</p></div>
              <button className="close-btn" aria-label="Đóng bản nháp" onClick={() => setDraftPanelOpen(false)}><X size={18}/></button>
            </header>
            <div className="draft-source-strip"><span>⚖ Đã đối chiếu {selectedTemplate.legal_sources.length} căn cứ</span>{selectedTemplate.legal_sources.slice(0, 2).map(item => <a key={item.source_url} href={item.source_url} target="_blank" rel="noreferrer">{item.document_number} ↗</a>)}</div>

            {draftStage === 'generating' ? <div className="draft-generating"><div className="generation-orbit"><FileText size={28}/><i/></div><span className="eyebrow">AI ĐANG SOẠN VĂN BẢN</span><h3>Đang ghép dữ liệu vào mẫu đã kiểm duyệt</h3><ol><li className="done">✓ Đọc cấu trúc biểu mẫu</li><li className="done">✓ Kiểm tra nguồn và phiên bản</li><li className="current">Ghép {Object.values(draftValues).filter(Boolean).length} trường dữ liệu…</li><li>Tạo bản nháp để rà soát</li></ol></div> : <div className={`draft-drawer-body ${draftStage === 'ready' ? 'has-editor' : ''}`}>
              <section className="draft-field-rail">
                <div className="field-progress"><div><span>Thông tin cần có</span><strong>{readiness}%</strong></div><div className="readiness-track"><i style={{ width: `${readiness}%` }}/></div><small>{requiredFields.filter(field => draftValues[field.key]?.trim()).length}/{requiredFields.length} bắt buộc đã có{reviewCount ? ` · ${reviewCount} cần xác minh` : ''}</small></div>
                <div className="field-list">
                  {selectedTemplate.fields.map(field => {
                    const missing = field.required && !draftValues[field.key]?.trim();
                    return <label key={field.key} className={missing ? 'missing' : draftValues[field.key] ? 'filled' : ''}><span><b>{field.label}{field.required ? ' *' : ''}</b><small>{missing ? '⚠ Còn thiếu' : draftValues[field.key] ? '✓ Đã có' : 'Không bắt buộc'}</small></span>{field.allowed_values.length ? <select value={draftValues[field.key] ?? ''} onChange={event => updateDraftValue(field.key, event.target.value)}><option value="">Chọn giá trị</option>{field.allowed_values.map(value => <option key={value}>{value}</option>)}</select> : <input type={field.input_type === 'date' ? 'date' : field.input_type === 'year' ? 'number' : 'text'} value={draftValues[field.key] ?? ''} onChange={event => updateDraftValue(field.key, event.target.value)} placeholder={missing ? 'Cần bổ sung' : 'Nhập nếu có'}/>}</label>;
                  })}
                </div>
                {capabilities?.ocr_autofill && <div className="field-ocr"><label><input type="file" accept="image/jpeg,image/png" onChange={event => setFile(event.target.files?.[0])}/><span>✦ {file ? file.name : 'AI điền từ giấy tờ'}</span></label><button onClick={upload} disabled={!file || !!busy}>{busy === 'upload' ? 'Đang nhận dạng…' : 'Điền tự động'}</button></div>}
                <button className="primary wide generate-draft" onClick={generateDraft} disabled={!!busy}>{busy === 'generate' ? 'Đang sinh…' : generatedDraft ? 'Cập nhật bản nháp' : missingFields.length ? `Sinh nháp · giữ ${missingFields.length} chỗ trống` : 'Sinh bản nháp hoàn chỉnh'} <span>→</span></button>
                {missingFields.length > 0 && <p className="force-note">Các chỗ thiếu sẽ được đánh dấu để bạn không bỏ sót.</p>}
              </section>

              {draftStage === 'ready' && <section className="draft-editor-area">
                {proposedRevision ? <div className="revision-review">
                  <div className="revision-heading"><div><span className="eyebrow">DUYỆT THAY ĐỔI AI</span><h3>{proposedRevision.summary}</h3></div><span className="review-badge">{changeCount} thay đổi · chờ duyệt</span></div>
                  <div className="diff-legend"><span className="removed">− Nội dung cũ</span><span className="added">+ Nội dung mới</span><span>Phần không đổi được thu gọn</span></div>
                  <div className="diff-view">{diffBlocks.map((block, index) => <div key={`${block.type}-${index}`} className={`diff-block ${block.type}`}>{block.type !== 'same' && <b>{block.type === 'added' ? '+' : '−'}</b>}<div dangerouslySetInnerHTML={{ __html: block.html }}/></div>)}</div>
                  <div className="revision-actions"><button className="ghost" onClick={() => { setProposedRevision(undefined); setDiffBlocks([]); }}>Bỏ đề xuất</button><button className="primary" onClick={applyRevision}><Check size={15}/> Áp dụng thay đổi đã duyệt</button></div>
                </div> : <>
                  <WordWorkspace content={docContent} fileName={`${formSchema?.procedure_id ?? 'van-ban'}.docx`} signature={signature} onSignatureChange={setSignature} signerName={signerName} onSignerNameChange={setSignerName} source={source} onSelectionChange={setSelectedText} onContentChange={setDocContent} onDownload={downloadDocx} downloading={busy === 'docx'} statusHint={`${missingFields.length} chỗ cần bổ sung`}/>
                  <div className="ai-revise-bar"><div><span>✦</span><input aria-label="Yêu cầu AI sửa bản nháp" value={revisionInstruction} onChange={event => setRevisionInstruction(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && revisionInstruction.trim()) reviseDraft(); }} placeholder={selectedText ? `Sửa đoạn đã chọn: “${selectedText.slice(0, 42)}…”` : 'Yêu cầu AI sửa: rút gọn, trang trọng hơn…'}/><button onClick={reviseDraft} disabled={!revisionInstruction.trim() || busy === 'revise'}>{busy === 'revise' ? 'Đang sửa…' : 'Tạo đề xuất'}</button></div><small>AI không tự áp dụng. Bạn sẽ thấy diff và duyệt trước.</small></div>
                </>}
              </section>}
            </div>}

            {draftStage === 'ready' && <footer className="draft-submit-footer"><label><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)}/> Tôi đồng ý xử lý dữ liệu để tiền kiểm hồ sơ.</label><button className="primary" onClick={submit} disabled={!!busy || !consent || missingFields.length > 0}>{missingFields.length ? `Còn ${missingFields.length} trường bắt buộc` : 'Nộp hồ sơ tiền kiểm'}</button></footer>}
          </aside>}
        </div>
        {imageReviewOpen && <ImageFormatReviewDialog onClose={() => setImageReviewOpen(false)} onContinue={continueWithReviewedImage}/>}
      </main>
    </Shell>
  );
}

function CitizenPortal() {
  const [logged, setLogged] = useState(!!token()); const [cases, setCases] = useState<CaseRecord[]>([]); const [current, setCurrent] = useState<CaseRecord | null>(null);
  const [file, setFile] = useState<File>(); const [consent, setConsent] = useState(false);
  const [notice, setNotice] = useState(''); const [busy, setBusy] = useState('');
  const [procedures, setProcedures] = useState<ProcedureSummary[]>([]);
  const [procedureCapabilities, setProcedureCapabilities] = useState<Record<string, ProcedureCapabilities>>({});
  const [directoryStatus, setDirectoryStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [formSchema, setFormSchema] = useState<ProcedureFormSchema>();
  const [capabilities, setCapabilities] = useState<ProcedureCapabilities>();
  const [requirements, setRequirements] = useState<ProcedureRequirement[]>([]);
  const [caseDocuments, setCaseDocuments] = useState<CaseDocument[]>([]);
  const [activeRequirement, setActiveRequirement] = useState<string | null>(null);

  const [started, setStarted] = useState(false);
  const [docContent, setDocContent] = useState('');
  const [signature, setSignature] = useState('');
  const [signerName, setSignerName] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [extractedFields, setExtractedFields] = useState<ExtractedField[]>();
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [ocrPhase, setOcrPhase] = useState<OcrPhase>('idle');
  const [prepSteps, setPrepSteps] = useState<PreprocessStep[]>([]);
  const [prepIndex, setPrepIndex] = useState(0);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [answers, setAnswers] = useState<ClarifyingAnswers>({});
  const [answersDirty, setAnswersDirty] = useState(false);
  const requiredFields = formSchema?.fields.filter(field => field.required) ?? [];
  const clarifyingQuestions = formSchema?.clarifying_questions ?? [];
  const answerErrors = useMemo(() => validateClarifyingAnswers(clarifyingQuestions, answers), [clarifyingQuestions, answers]);
  const unansweredQuestions = clarifyingQuestions.filter(question => isMissingAnswer(answers[question.key]));
  const hasAnswerErrors = Object.keys(answerErrors).length > 0;
  const readiness = requiredFields.length ? Math.round(requiredFields.filter(field => draftValues[field.key]?.trim()).length / requiredFields.length * 100) : 0;
  const reviewCount = extractedFields?.filter(item => item.confidence < 0.85).length ?? 0;
  const checklistItems = Object.entries(current?.checklist ?? {}).filter(([, status]) => status !== 'not_applicable');
  const foldName = (value: string) => value.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().trim();
  // Requirement trùng tên với biểu mẫu đang soạn = chính tờ khai — mở editor thay vì panel upload.
  const isFormRequirement = (requirement: ProcedureRequirement) =>
    !!formSchema && foldName(requirement.name).startsWith(foldName(formSchema.title));
  const activeRequirementInfo = activeRequirement ? requirements.find(item => item.code === activeRequirement) : undefined;
  const documentsForRequirement = (requirement: ProcedureRequirement) =>
    caseDocuments.filter(document => requirement.accepted_doc_types.includes(document.document_type));
  const updateDraftValue = (key: string, value: string) => setDraftValues(current => {
    const next = { ...current, [key]: value };
    if (formSchema) setDocContent(buildDynamicFormHtml(formSchema, next));
    return next;
  });

  useEffect(() => {
    const expired = () => { setLogged(false); setNotice('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.'); };
    window.addEventListener('citizen-session-expired', expired);
    return () => window.removeEventListener('citizen-session-expired', expired);
  }, []);
  const refresh = async () => setCases(await api<CaseRecord[]>('/citizen/cases'));
  const loadDirectory = async () => {
    setDirectoryStatus('loading');
    try {
      const items = await api<ProcedureSummary[]>('/procedures');
      rememberProcedureNames(items); setProcedures(items);
      setDirectoryStatus('ready');
      const pairs = await Promise.all(items.map(async item => [item.id, await api<ProcedureCapabilities>(`/procedures/${item.id}/capabilities`)] as const));
      setProcedureCapabilities(Object.fromEntries(pairs));
    } catch (cause) {
      setDirectoryStatus('error');
      setNotice((cause as Error).message);
    }
  };
  useEffect(() => {
    if (!logged) return;
    refresh().catch(cause => setNotice((cause as Error).message));
    void loadDirectory();
  }, [logged]);
  if (!logged) return <Login role="citizen" onSuccess={() => setLogged(true)}/>;

  const run = async (name: string, work: () => Promise<void>) => { setBusy(name); setNotice(''); try { await work(); } catch (cause) { setNotice((cause as Error).message); } finally { setBusy(''); } };

  // Một luồng duy nhất: mở tờ khai mẫu để tự điền, OCR là bước "AI điền hộ" tùy chọn.
  const startCase = (procedure: ProcedureSummary) => {
    run('create', async () => {
      const [schema, caps, detail, item] = await Promise.all([
        api<ProcedureFormSchema>(`/procedures/${procedure.id}/form-schema`),
        api<ProcedureCapabilities>(`/procedures/${procedure.id}/capabilities`),
        api<{ requirements: ProcedureRequirement[] }>(`/procedures/${procedure.id}`),
        api<CaseRecord>('/citizen/cases', { method: 'POST', body: JSON.stringify({ procedure_id: procedure.id, locality_code: procedure.locality_code }) }),
      ]);
      setStarted(true);
      setFormSchema(schema);
      setCapabilities(caps);
      setRequirements(detail.requirements);
      setCaseDocuments([]);
      setActiveRequirement(null);
      setDocContent(buildDynamicFormHtml(schema, {}));
      setSignature('');
      setSignerName('');
      setExtractedFields(undefined);
      setPreviewUrl(undefined);
      setOcrPhase('idle');
      setPrepSteps([]);
      setPrepIndex(0);
      setDraftValues({});
      setAnswers({});
      setAnswersDirty(schema.clarifying_questions.length > 0);
      setCurrent(item);
      setNotice('Đã khởi tạo tờ khai. Điền trực tiếp hoặc tải giấy tờ để AI điền tự động.');
      await refresh();
    });
  };
  const updateAnswer = (key: string, value: string | number | boolean) => {
    setAnswers(currentAnswers => ({ ...currentAnswers, [key]: value }));
    setAnswersDirty(true);
  };
  const saveAnswers = () => current && run('answers', async () => {
    if (hasAnswerErrors) throw new Error('Vui lòng kiểm tra lại phần thông tin xác định trường hợp.');
    const latest = await api<{ case: CaseRecord }>(`/citizen/cases/${current.id}`);
    const updated = await api<CaseRecord>(`/citizen/cases/${current.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ expected_version: latest.case.version, answers }),
    });
    setCurrent(updated);
    setAnswersDirty(false);
    setNotice('Đã cập nhật danh sách giấy tờ theo trường hợp của bạn.');
  });

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
    if (hasAnswerErrors || answersDirty) throw new Error('Vui lòng hoàn tất và áp dụng phần thông tin xác định trường hợp.');
    const latest = await api<{ case: CaseRecord }>(`/citizen/cases/${current.id}`);
    const updated = await api<CaseRecord>(`/citizen/cases/${current.id}`, { method: 'PATCH', body: JSON.stringify({ expected_version: latest.case.version, answers, form_data: { ...draftValues, _signer_name: signerName.trim(), _draft_html: composeSignedDocumentHtml(docContent, signature, signerName), _readiness_score: readiness } }) });
    const item = await api<CaseRecord>(`/citizen/cases/${current.id}/submit`, { method: 'POST', headers: { 'Idempotency-Key': idempotency() }, body: JSON.stringify({ expected_version: updated.version, consent_version: 'privacy-v1', consent_accepted: true }) });
    setCurrent(item);
    setNotice('Hồ sơ đã được chuyển tới cán bộ tiếp nhận.');
    await refresh();
  });
  const refreshCurrent = async (id: string) => {
    const detail = await api<{ case: CaseRecord; documents: CaseDocument[] }>(`/citizen/cases/${id}`);
    setCurrent(detail.case);
    setCaseDocuments(detail.documents ?? []);
    if (detail.case.procedure_id && detail.case.procedure_id !== formSchema?.procedure_id) {
      const info = await api<{ requirements: ProcedureRequirement[] }>(`/procedures/${detail.case.procedure_id}`).catch(() => null);
      if (info) setRequirements(info.requirements);
    }
    await refresh();
  };
  return (
    <Shell role="citizen">
      <main id="main-content" className="citizen-page document-centric">
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
                   {procedures.map(procedure => {
                     // Chưa tải xong capabilities (undefined) → coi như hỗ trợ, tránh khoá nút vĩnh viễn nếu request capabilities chậm/lỗi.
                     const chatOnly = procedureCapabilities[procedure.id]?.dynamic_form === false;
                     if (chatOnly) {
                       return (
                         <a key={procedure.id} href="/chat" className="selector-card selector-card-chat-only">
                           <FileText size={32} />
                           <h3>{procedure.name}</h3>
                           <p>{procedure.agency}{procedure.national_code ? ` · Mã ${procedure.national_code}` : ''} · Chỉ hỗ trợ qua Trợ lý AI →</p>
                         </a>
                       );
                     }
                     return (
                       <button key={procedure.id} onClick={() => startCase(procedure)} className="selector-card" disabled={!!busy}>
                         <FileText size={32} />
                         <h3>{procedure.name}</h3>
                         <p>{procedure.agency}{procedure.national_code ? ` · Mã ${procedure.national_code}` : ''}</p>
                       </button>
                     );
                   })}
                   {!procedures.length && directoryStatus === 'loading' && <div className="skeleton-loader"><div className="skeleton-line"></div><div className="skeleton-line short"></div></div>}
                   {!procedures.length && directoryStatus === 'error' && <p>Chưa kết nối được máy chủ để tải danh mục thủ tục. <button className="text-button" onClick={() => void loadDirectory()}>Thử lại</button></p>}
                   {!procedures.length && directoryStatus === 'ready' && <p>Chưa có thủ tục với biểu mẫu đã công bố.</p>}
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
                    ) : activeRequirementInfo ? (
                      <section className="requirement-pane">
                        <button className="text-button" onClick={() => setActiveRequirement(null)}>← Quay lại tờ khai</button>
                        <h2>{activeRequirementInfo.name}</h2>
                        <p className="muted">
                          {activeRequirementInfo.condition_label ?? (activeRequirementInfo.original_required ? 'Giấy tờ bắt buộc của thủ tục.' : 'Giấy tờ không bắt buộc.')}
                          {activeRequirementInfo.notes ? ` ${activeRequirementInfo.notes}` : ''}
                        </p>
                        <div className="requirement-docs">
                          <h3>Bản chụp đã tải lên</h3>
                          {documentsForRequirement(activeRequirementInfo).length ? (
                            <ul>
                              {documentsForRequirement(activeRequirementInfo).map(document => (
                                <li key={document.id}>
                                  <strong>{document.original_filename ?? document.document_type}</strong>
                                  <Status value={document.ocr_status}/>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="muted">Chưa có bản chụp nào cho giấy tờ này. Tải lên bên dưới — hệ thống tự nhận dạng loại giấy tờ và tích ✓ vào danh sách.</p>
                          )}
                        </div>
                        <label className="dropzone">
                          <input type="file" accept="image/jpeg,image/png,application/pdf" onChange={event => setFile(event.target.files?.[0])}/>
                          <b>{file ? file.name : 'Chọn bản chụp giấy tờ'}</b>
                          <span>JPG, PNG hoặc PDF · tối đa 10 MB</span>
                        </label>
                        <button className="secondary wide" onClick={upload} disabled={!file || !!busy}>{busy === 'upload' ? 'Đang xử lý…' : 'Tải lên & kiểm tra'}</button>
                      </section>
                    ) : (
                      <WordWorkspace
                        content={docContent}
                        fileName={`${formSchema?.procedure_id ?? 'to-khai'}.docx`}
                        signature={signature}
                        onSignatureChange={setSignature}
                        signerName={signerName}
                        onSignerNameChange={setSignerName}
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
                            <label key={field.key} className={field.type === 'checkbox' ? 'checkbox-field' : ''}>{field.label}{field.required ? ' *' : ''}{field.type === 'select' ? <select value={draftValues[field.key] ?? ''} onChange={event => updateDraftValue(field.key, event.target.value)}><option value="">Chọn giá trị</option>{(field.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}</select> : field.type === 'checkbox' ? <input type="checkbox" checked={draftValues[field.key] === 'true'} onChange={event => updateDraftValue(field.key, String(event.target.checked))}/> : <input type={field.type === 'date' ? 'date' : field.type === 'number' ? 'number' : 'text'} value={draftValues[field.key] ?? ''} onChange={event => updateDraftValue(field.key, event.target.value)} placeholder="Chưa có dữ liệu"/>}</label>
                          ))}
                        </details>

                        {!!formSchema?.clarifying_questions.length && (
                          <div className="clarifying-fields">
                            <h3>Thông tin xác định trường hợp</h3>
                            <p>Trả lời để hệ thống chỉ yêu cầu đúng giấy tờ áp dụng.</p>
                            <div className="clarifying-progress" aria-live="polite">{unansweredQuestions.length ? `Còn ${unansweredQuestions.length} câu cần trả lời` : hasAnswerErrors ? 'Có câu trả lời chưa hợp lệ' : answersDirty ? 'Sẵn sàng áp dụng vào hồ sơ' : 'Đã áp dụng vào hồ sơ'}</div>
                            {formSchema.clarifying_questions.map(question => {
                              const value = answers[question.key];
                              const renderedValue = value === undefined ? '' : String(value);
                              const error = answerErrors[question.key];
                              return <label key={question.key}><span>{question.text}</span>{question.answer_type === 'boolean' ? <select aria-invalid={!!error} value={renderedValue} onChange={event => updateAnswer(question.key, event.target.value === '' ? '' : event.target.value === 'true')}><option value="">Chọn câu trả lời</option><option value="true">Có</option><option value="false">Không</option></select> : question.answer_type === 'choice' ? <select aria-invalid={!!error} value={renderedValue} onChange={event => updateAnswer(question.key, event.target.value)}><option value="">Chọn câu trả lời</option>{(question.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}</select> : <input aria-invalid={!!error} type={question.answer_type === 'integer' ? 'number' : 'text'} step={question.answer_type === 'integer' ? 1 : undefined} min={question.minimum ?? undefined} max={question.maximum ?? undefined} value={renderedValue} onChange={event => updateAnswer(question.key, question.answer_type === 'integer' && event.target.value !== '' ? Number(event.target.value) : event.target.value)} placeholder="Nhập câu trả lời"/>}{error && !isMissingAnswer(value) && <small className="field-error">{error}</small>}</label>;
                            })}
                            <button className="secondary wide" onClick={saveAnswers} disabled={hasAnswerErrors || !answersDirty || !!busy}>{busy === 'answers' ? 'Đang cập nhật…' : answersDirty ? 'Áp dụng cho hồ sơ' : 'Đã áp dụng'}</button>
                          </div>
                        )}

                       {checklistItems.length > 0 && (
                         <div className="checklist-display">
                           <h3>Danh sách giấy tờ cần thiết <small>Đã cá nhân hóa</small></h3>
                           <ul className="checklist-items">
                             {checklistItems.map(([key, status]) => {
                               const requirement = requirements.find(item => item.code === key);
                               const isForm = requirement ? isFormRequirement(requirement) : false;
                               const selected = isForm ? activeRequirement === null : activeRequirement === key;
                               return (
                                 <li key={key} className={`checklist-item ${status}`}>
                                   <button className={`checklist-item-button ${selected ? 'selected' : ''}`} onClick={() => setActiveRequirement(isForm ? null : key)} title={isForm ? 'Mở tờ khai trong trình soạn thảo' : 'Xem và tải lên giấy tờ này'}>
                                     <span className="check-icon">{status === 'uploaded' || status === 'verified' ? <Check size={12}/> : status === 'uncertain' ? '!' : null}</span>
                                     <div className="check-text">
                                       <strong>{requirement?.name ?? humanizeStatus(key)}</strong>
                                       <small>{humanizeStatus(String(status))}{isForm ? ' · soạn trực tiếp' : ''}</small>
                                     </div>
                                   </button>
                                 </li>
                               );
                             })}
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
                          <button className="primary wide" onClick={submit} disabled={!!busy || !consent || readiness < 60 || hasAnswerErrors || answersDirty}>{busy === 'submit' ? 'Đang gửi…' : hasAnswerErrors || answersDirty ? 'Cần xác định trường hợp' : readiness < 60 ? 'Cần điền thêm dữ liệu' : 'Nộp hồ sơ tiền kiểm'}</button>
                        </div>
                        <button className="text-button" onClick={() => { setCurrent(null); setStarted(false); setFormSchema(undefined); setCapabilities(undefined); setOcrPhase('idle'); setPrepSteps([]); setPrepIndex(0); setExtractedFields(undefined); setPreviewUrl(undefined); setFile(undefined); setDraftValues({}); setAnswers({}); setAnswersDirty(false); setDocContent(''); setSignature(''); setSignerName(''); }}>Tạo hồ sơ khác</button>
                     </div>
                   )}

                   {notice && <div className={`alert ${notice.includes('Đã') || notice.includes('đã') ? 'success' : 'error'}`} role="status">{notice}</div>}
                 </div>
              </div>
           )}
        </div>

      </main>
    </Shell>
  );
}

function Status({ value }: { value: string }) { return <span className={`status status-${value}`}>{humanizeStatus(value)}</span>; }
function Empty({ title, text }: { title: string; text: string }) { return <div className="empty-state"><FileMagnifyingGlass size={32} weight="duotone" aria-hidden="true"/><h3>{title}</h3><p>{text}</p></div>; }

function OfficerPortal() {
  const [logged, setLogged] = useState(!!token()); const [cases, setCases] = useState<CaseRecord[]>([]); const [summary, setSummary] = useState<DashboardSummary>(); const [selected, setSelected] = useState<CaseDetail>();
  const [search, setSearch] = useState(''); const [filter, setFilter] = useState(''); const [sort, setSort] = useState('priority_desc'); const [loading, setLoading] = useState(true); const [detailLoading, setDetailLoading] = useState(false); const [notice, setNotice] = useState('');
  useEffect(() => { const expired = () => setLogged(false); window.addEventListener('officer-session-expired', expired); return () => window.removeEventListener('officer-session-expired', expired); }, []);
  const loadQueue = async () => { setLoading(true); try { const [queue, dashboard, catalogItems] = await Promise.all([api<CaseRecord[]>(`/officer/cases?${buildCaseQuery(search, filter, sort)}`), api<DashboardSummary>('/officer/dashboard/summary'), api<ProcedureSummary[]>('/procedures')]); rememberProcedureNames(catalogItems); setCases(queue); setSummary(dashboard); } catch (cause) { handleError(cause); } finally { setLoading(false); } };
  const handleError = (cause: unknown) => { const error = cause as Error; if (error instanceof ApiError && error.status === 401) { setToken('', 'officer'); setLogged(false); } setNotice(error.message); };
  useEffect(() => { if (!logged) return; const timer = window.setTimeout(loadQueue, 250); return () => window.clearTimeout(timer); }, [logged, search, filter, sort]);
  useEffect(() => { if (!logged) return; const timer = window.setInterval(loadQueue, 30000); return () => window.clearInterval(timer); }, [logged, search, filter, sort]);
  useEffect(() => { const caseId = legacyReviewCaseId(location.pathname); if (logged && caseId) void open(caseId); }, [logged]);
  if (!logged) return <Login role="officer" onSuccess={() => setLogged(true)}/>;
  const open = async (id: string) => { setDetailLoading(true); setNotice(''); try { setSelected(await api<CaseDetail>(`/officer/cases/${id}`)); } catch (cause) { handleError(cause); } finally { setDetailLoading(false); } };
  const refreshSelected = async () => { if (selected) await open(selected.case.id); await loadQueue(); };
  return <Shell role="officer"><main className="officer-page"><div className="page-title officer-title"><div><span className="eyebrow">TRUNG TÂM ĐIỀU HÀNH</span><h1>Xử lý hồ sơ tiền kiểm</h1><p>Dữ liệu cập nhật tự động mỗi 30 giây.</p></div><div className="title-actions"><button className="ghost compact" onClick={loadQueue}>↻ Làm mới</button><button className="ghost compact" onClick={() => { setToken('', 'officer'); setLogged(false); }}>Đăng xuất</button></div></div><Dashboard summary={summary} active={filter} onFilter={setFilter}/>{notice && <div className="alert error dismissible" role="alert">{notice}<button onClick={() => setNotice('')}>×</button></div>}<div className="officer-workspace"><aside className="queue-panel"><div className="queue-heading"><div><span className="eyebrow">HÀNG ĐỢI</span><h2>{summary?.total ?? 0} hồ sơ</h2></div><span className="live-dot">Trực tuyến</span></div><label className="search-box"><span>⌕</span><input aria-label="Tìm hồ sơ" value={search} onChange={event => setSearch(event.target.value)} placeholder="Tìm mã hồ sơ, thủ tục…"/></label><div className="queue-filters"><select aria-label="Lọc trạng thái" value={filter} onChange={event => setFilter(event.target.value)}><option value="">Mọi trạng thái</option><option value="awaiting_officer_review">Chờ tiếp nhận</option><option value="in_officer_review">Đang thẩm tra</option><option value="needs_citizen_update">Chờ bổ sung</option><option value="precheck_ready">Đạt tiền kiểm</option></select><select aria-label="Sắp xếp" value={sort} onChange={event => setSort(event.target.value)}><option value="priority_desc">Ưu tiên cao</option><option value="newest">Mới cập nhật</option><option value="oldest">Cũ nhất</option></select></div><div className="case-list">{loading ? [1,2,3].map(item => <div className="case-skeleton" key={item}/>) : cases.length ? cases.map(item => <button className={`queue-case ${selected?.case.id === item.id ? 'active' : ''}`} key={item.id} onClick={() => open(item.id)}><span className="priority-line"><b>{item.case_code}</b>{(item.priority ?? 0) >= 70 && <i>Ưu tiên</i>}</span><strong>{procedureNames[item.procedure_id] ?? item.procedure_id}</strong><span className="case-meta"><Status value={item.status}/><small>{formatDate(item.updated_at)}</small></span></button>) : <Empty title="Không có hồ sơ" text="Thử thay đổi bộ lọc hoặc từ khóa."/>}</div></aside><section className="review-shell">{detailLoading ? <div className="detail-loading"><i/><p>Đang tải hồ sơ…</p></div> : selected ? <ManagedReviewWorkspace detail={selected} onRefresh={refreshSelected} onError={handleError}/> : <div className="welcome-review"><div className="welcome-art"><span>✓</span></div><span className="eyebrow">KHÔNG GIAN THẨM TRA</span><h2>Chọn một hồ sơ để bắt đầu</h2><p>Đối chiếu tài liệu gốc, dữ liệu OCR và kết quả kiểm tra trên cùng một màn hình.</p><div className="welcome-features"><span><i>1</i>Xem căn cứ</span><span><i>2</i>Xác minh OCR</span><span><i>3</i>Ra quyết định</span></div></div>}</section></div></main></Shell>;
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
  const rows = visibleSubmissionEntries(submission);
  const answerRows = clarificationAnswerEntries(submission);
  return <section className="review-panel data-panel"><div className="column-heading"><span>DỮ LIỆU CÓ CẤU TRÚC</span><b>{rows.length + answerRows.length + fields.length}</b></div><div className="data-section"><h3>Thông tin người khai</h3>{rows.length ? rows.map(([key, item]) => <div className="data-row" key={key}><span>{humanizeStatus(key)}</span><strong>{formatSubmissionValue(item)}</strong><small className="verified">✓ Đã khai</small></div>) : <p className="empty">Không có dữ liệu biểu mẫu.</p>}</div>{answerRows.length > 0 && <div className="data-section"><h3>Thông tin xác định trường hợp</h3>{answerRows.map(([key, item]) => <div className="data-row" key={key}><span>{humanizeStatus(key)}</span><strong>{formatSubmissionValue(item)}</strong><small className="verified">✓ Đã áp dụng</small></div>)}</div>}<div className="data-section"><div className="section-title"><h3>Kết quả OCR</h3>{fields.some(item => item.review_status === 'needs_human_review') && <span className="needs-review">Cần xác minh</span>}</div>{fields.length ? fields.map(field => <div className={`ocr-row ${field.review_status === 'needs_human_review' ? 'low-confidence' : ''}`} key={field.id}><div><span>{humanizeStatus(field.field_key)}</span><small>Độ tin cậy {Math.round(field.confidence * 100)}%</small></div>{editing === field.id ? <div className="edit-field"><input value={value} onChange={event => setValue(event.target.value)} autoFocus/><button onClick={() => save(field)} disabled={busy}>Lưu</button><button className="text-button" onClick={() => setEditing(undefined)}>Hủy</button></div> : <div className="field-value"><strong>{field.normalized_value || field.raw_value || '—'}</strong>{editable && <button aria-label={`Sửa ${field.field_key}`} onClick={() => { setEditing(field.id); setValue(field.normalized_value || field.raw_value); }}>✎</button>}</div>}</div>) : <p className="empty">Chọn tài liệu có dữ liệu OCR để xem.</p>}</div></section>;
}

function FindingsPanel({ findings, busy, reasons, setReasons, onDecide }: { findings: Finding[]; busy: string; reasons: Record<string, string>; setReasons: React.Dispatch<React.SetStateAction<Record<string, string>>>; onDecide: (finding: Finding, decision: 'accept' | 'dismiss' | 'escalate') => void }) {
  const openCount = findings.filter(isActiveFinding).length;
  return <section className="review-panel findings-panel"><div className="column-heading"><span>KẾT QUẢ KIỂM TRA</span><b>{openCount}</b></div><div className="finding-summary"><span><i className="red"/>{findings.filter(item => item.severity === 'error' && isActiveFinding(item)).length} lỗi</span><span><i className="gold"/>{findings.filter(item => item.severity === 'warning' && isActiveFinding(item)).length} cảnh báo</span></div>{findings.length ? findings.map(item => <article className={`finding-card ${item.severity} ${!isActiveFinding(item) ? 'resolved' : ''}`} key={item.id}><div className="finding-title"><span>{item.severity === 'error' ? '!' : item.severity === 'warning' ? '△' : 'i'}</span><div><b>{item.severity === 'error' ? 'Cần xử lý' : item.severity === 'warning' ? 'Cần lưu ý' : 'Thông tin'}</b><small>{item.source === 'rule' ? 'Quy tắc nghiệp vụ' : 'Gợi ý AI'}</small></div><Status value={item.status}/></div><p>{item.message}</p>{item.suggestion && <small className="suggestion-text">Gợi ý: {item.suggestion}</small>}{item.status === 'open' && <><input className="reason-input" value={reasons[item.id] ?? ''} onChange={event => setReasons(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Lý do xử lý (nếu cần)"/><div className="finding-actions"><button onClick={() => onDecide(item, 'accept')} disabled={!!busy}>Ghi nhận lỗi</button><button onClick={() => onDecide(item, 'dismiss')} disabled={!!busy}>Bỏ qua có lý do</button><button onClick={() => onDecide(item, 'escalate')} disabled={!!busy}>Chuyển cấp</button></div></>}</article>) : <Empty title="Không có cảnh báo" text="Chưa phát hiện vấn đề trong phiên bản hiện tại."/>}</section>;
}

function App() {
  const isManagementRoute = isApplicationManagementPath(location.pathname);
  if (isManagementRoute || location.pathname.startsWith('/officer')) {
    return <React.Suspense fallback={<div className="route-loading" role="status">Đang tải không gian cán bộ…</div>}>
      {isManagementRoute ? <ApplicationManagementRouter/> : <OfficerPortal/>}
    </React.Suspense>;
  }
  return location.pathname.startsWith('/chat') ? <ChatPortal/> : <CitizenPortal/>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><ThemeProvider><App/></ThemeProvider></React.StrictMode>);

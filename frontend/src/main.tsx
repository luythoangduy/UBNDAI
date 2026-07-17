import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MessageCircle, X, FileText, UploadCloud } from 'lucide-react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { api, apiBlob, ApiError, idempotency, setToken, token } from './api';
import type { CaseDetail, CaseDocument, CaseRecord, ChatResponse, DashboardSummary, ExtractedField, Finding, PortalRole } from './types';
import { buildCaseQuery, formatBytes, formatDate, humanizeStatus } from './utils';
import './styles.css';

const procedureNames: Record<string, string> = { khai_sinh: 'Đăng ký khai sinh' };

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

type ChatMessage = { role: 'user' | 'assistant'; text: string; response?: ChatResponse };
function CitizenAssistant({ activeCaseId, onChecklist, selectedContext }: { activeCaseId?: string; onChecklist?: (caseId: string) => void; selectedContext?: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: 'Xin chào! Bạn cần thực hiện thủ tục gì? Hãy mô tả bằng lời của bạn.' }]);
  const [message, setMessage] = useState(''); const [caseId, setCaseId] = useState<string | undefined>(activeCaseId); const [busy, setBusy] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  useEffect(() => { if (activeCaseId) setCaseId(activeCaseId); }, [activeCaseId]);
  const send = async (event: FormEvent) => {
    event.preventDefault(); const value = message.trim(); if (!value || busy) return;
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
            {messages.map((item, index) => <article key={index} className={`bubble ${item.role}`}><span>{item.role === 'assistant' ? 'AI' : 'Bạn'}</span><div><p>{item.text}</p>{item.response?.clarifying_questions?.map((question, questionIndex) => <button key={questionIndex} className="suggestion" onClick={() => setMessage(question)}>{question}</button>)}{!!item.response?.citations?.length && <details><summary>{item.response.citations.length} nguồn tham khảo</summary>{item.response.citations.map(citation => <p key={citation.index} className="citation">[{citation.index}] {citation.section ?? citation.excerpt ?? 'Nguồn thủ tục'}</p>)}</details>}</div></article>)}
            {busy && <article className="bubble assistant"><span>AI</span><div className="skeleton-loader"><div className="skeleton-line"></div><div className="skeleton-line short"></div></div></article>}
            {streamedText && <article className="bubble assistant"><span>AI</span><div><p>{streamedText}<span className="cursor">|</span></p></div></article>}
          </div>
          <form className="chat-input" onSubmit={send}>
            {selectedContext && <div className="chat-context-banner"><strong>Đang chọn:</strong> "{selectedContext.length > 40 ? selectedContext.substring(0, 40) + '...' : selectedContext}"</div>}
            <textarea aria-label="Nội dung cần hỏi" rows={2} maxLength={4000} value={message} onChange={event => setMessage(event.target.value)} placeholder="Ví dụ: Tôi muốn đăng ký khai sinh cho con…"/>
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

function TiptapDocument({ initialContent, onSelectionChange }: { initialContent: string; onSelectionChange: (text: string) => void }) {
  const editor = useEditor({
    extensions: [StarterKit],
    content: initialContent,
    onSelectionUpdate: ({ editor }) => {
      const { from, to } = editor.state.selection;
      if (from !== to) {
        const text = editor.state.doc.textBetween(from, to, ' ');
        onSelectionChange(text);
      } else {
        onSelectionChange('');
      }
    }
  });

  useEffect(() => {
    if (editor && initialContent !== editor.getHTML()) {
      editor.commands.setContent(initialContent);
    }
  }, [editor, initialContent]);

  return (
    <div className="document-paper tiptap-wrapper">
      <EditorContent editor={editor} />
    </div>
  );
}

function CitizenPortal() {
  const [logged, setLogged] = useState(!!token()); const [cases, setCases] = useState<CaseRecord[]>([]); const [current, setCurrent] = useState<CaseRecord | null>(null);
  const [file, setFile] = useState<File>(); const [consent, setConsent] = useState(false);
  const [notice, setNotice] = useState(''); const [busy, setBusy] = useState('');
  
  const [procedureType, setProcedureType] = useState<'none' | 'rule_based' | 'ocr'>('none');
  const [docContent, setDocContent] = useState('<h2>Đơn đề nghị</h2><p>Vui lòng điền thông tin hoặc tải tài liệu lên để tiếp tục.</p>');
  const [selectedText, setSelectedText] = useState('');

  const refresh = async () => setCases(await api<CaseRecord[]>('/citizen/cases'));
  useEffect(() => { if (logged) refresh().catch(cause => setNotice((cause as Error).message)); }, [logged]);
  if (!logged) return <Login role="citizen" onSuccess={() => setLogged(true)}/>;
  const run = async (name: string, work: () => Promise<void>) => { setBusy(name); setNotice(''); try { await work(); } catch (cause) { setNotice((cause as Error).message); } finally { setBusy(''); } };
  
  const khaiSinhTemplate = `<h2 style="text-align: center;">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<br/>Độc lập - Tự do - Hạnh phúc</h2>
<h1 style="text-align: center;">TỜ KHAI ĐĂNG KÝ KHAI SINH</h1>
<p>Kính gửi: Ủy ban nhân dân [....................................................................]</p>
<p>Họ, chữ đệm, tên người yêu cầu: [....................................................................]</p>
<p>Nơi cư trú: [....................................................................]</p>
<p>Giấy tờ tùy thân: [....................................................................]</p>
<p>Quan hệ với người được khai sinh: [....................................................................]</p>
<p><strong>Đề nghị đăng ký khai sinh cho người dưới đây:</strong></p>
<p>Họ, chữ đệm, tên: [....................................................................]</p>
<p>Giới tính: [.......................] Ngày, tháng, năm sinh: [........................................]</p>
<p>Nơi sinh: [....................................................................]</p>
<p>Dân tộc: [.......................] Quốc tịch: [........................................]</p>
<p>Quê quán: [....................................................................]</p>
<p><strong>Thông tin người mẹ:</strong></p>
<p>Họ, chữ đệm, tên: [....................................................................]</p>
<p>Năm sinh: [.......................] Quốc tịch: [........................................]</p>
<p>Nơi cư trú: [....................................................................]</p>
<p><strong>Thông tin người cha:</strong></p>
<p>Họ, chữ đệm, tên: [....................................................................]</p>
<p>Năm sinh: [.......................] Quốc tịch: [........................................]</p>
<p>Nơi cư trú: [....................................................................]</p>`;

  const createRuleBased = () => {
    setProcedureType('rule_based');
    setDocContent(khaiSinhTemplate);
    run('create', async () => { 
      const item = await api<CaseRecord>('/citizen/cases', { method: 'POST', body: JSON.stringify({ procedure_id: 'khai_sinh', locality_code: '00001' }) }); 
      setCurrent(item); 
      setNotice('Đã khởi tạo đơn đề nghị.'); 
      await refresh(); 
    }); 
  };

  const createOcr = () => {
    setProcedureType('ocr');
    setDocContent(''); // Clear doc content to show dropzone
    run('create', async () => { 
      const item = await api<CaseRecord>('/citizen/cases', { method: 'POST', body: JSON.stringify({ procedure_id: 'khai_sinh', locality_code: '00001' }) }); 
      setCurrent(item); 
      setNotice('Đã tạo phiên OCR. Vui lòng tải tài liệu.'); 
      await refresh(); 
    }); 
  };

  const upload = () => current && file && run('upload', async () => { 
    const intent = await api<{ document_id: string; upload_url: string }>(`/citizen/cases/${current.id}/documents/upload-intents`, { method: 'POST', body: JSON.stringify({ filename: file.name, content_type: file.type, size_bytes: file.size }) }); 
    const uploaded = await fetch(intent.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': 'application/octet-stream', Authorization: `Bearer ${token()}` } }); 
    if (!uploaded.ok) throw new Error('Không thể tải file lên'); 
    await api(`/citizen/documents/${intent.document_id}/complete`, { method: 'POST', body: JSON.stringify({ sha256: await checksum(file) }) }); 
    setNotice('Đã tải và tiền kiểm giấy tờ. AI đã phân tích nội dung.'); 
    setDocContent(`<h2>Tài liệu đã số hóa: ${file.name}</h2><p>Dữ liệu này được AI nhận diện tự động. Vui lòng kiểm tra và chỉnh sửa nếu cần thiết.</p>`);
    await refreshCurrent(current.id); 
  });
  
  const submit = () => current && run('submit', async () => { 
    if (!consent) throw new Error('Vui lòng xác nhận đồng ý xử lý dữ liệu trước khi nộp.'); 
    const latest = await api<{ case: CaseRecord }>(`/citizen/cases/${current.id}`); 
    const item = await api<CaseRecord>(`/citizen/cases/${current.id}/submit`, { method: 'POST', headers: { 'Idempotency-Key': idempotency() }, body: JSON.stringify({ expected_version: latest.case.version, consent_version: 'privacy-v1', consent_accepted: true }) }); 
    setCurrent(item); 
    setNotice('Hồ sơ đã được chuyển tới cán bộ tiếp nhận.'); 
    await refresh(); 
  });
  const refreshCurrent = async (id: string) => { const detail = await api<{case: CaseRecord}>(`/citizen/cases/${id}`); setCurrent(detail.case); await refresh(); };
  const handleChecklist = async (caseId: string) => { await refreshCurrent(caseId); setProcedureType('ocr'); setNotice('Đã nhận danh sách giấy tờ. Vui lòng chuẩn bị và tải lên.'); };

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
           {procedureType === 'none' && !current && (
              <div className="procedure-selector">
                 <h2>Bạn muốn chuẩn bị hồ sơ bằng cách nào?</h2>
                 <div className="selector-cards">
                   <button onClick={createRuleBased} className="selector-card">
                     <FileText size={32} />
                     <h3>Điền theo Form mẫu</h3>
                     <p>Cung cấp thông tin trực tiếp vào biểu mẫu chuẩn.</p>
                   </button>
                   <button onClick={createOcr} className="selector-card">
                     <UploadCloud size={32} />
                     <h3>Tải lên giấy tờ (OCR)</h3>
                     <p>Tải lên bản chụp để AI tự động trích xuất thông tin.</p>
                   </button>
                 </div>
              </div>
           )}
           
           {(procedureType !== 'none' || current) && (
              <div className="editor-container">
                 <div className="editor-main">
                    {procedureType === 'ocr' && !docContent ? (
                      <div style={{ textAlign: 'center', width: '100%', paddingTop: 60, paddingBottom: 60 }}>
                         <h2 style={{ fontSize: 24, color: 'var(--navy)', marginBottom: 12 }}>Tải lên tài liệu của bạn</h2>
                         <p style={{ color: 'var(--muted)', marginBottom: 32 }}>Hệ thống sẽ tự động trích xuất thông tin bằng AI</p>
                         <div style={{ maxWidth: 400, margin: '0 auto' }}>
                           <label className="dropzone">
                             <input type="file" accept="application/pdf,image/jpeg,image/png" onChange={event => setFile(event.target.files?.[0])}/>
                             <UploadCloud size={48} style={{ color: 'var(--blue)', marginBottom: 16 }}/>
                             <b>{file ? file.name : 'Chọn hoặc kéo thả giấy tờ'}</b>
                             <span>PDF, JPG hoặc PNG · tối đa 20 MB</span>
                           </label>
                           <button className="secondary wide" onClick={upload} disabled={!file || !!busy}>{busy === 'upload' ? 'Đang phân tích OCR…' : 'Bắt đầu xử lý'}</button>
                         </div>
                      </div>
                    ) : (
                      <TiptapDocument initialContent={docContent} onSelectionChange={setSelectedText} />
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
                       
                       {procedureType === 'ocr' && docContent && (
                         <div className="upload-block">
                           <label className="dropzone">
                             <input type="file" accept="application/pdf,image/jpeg,image/png" onChange={event => setFile(event.target.files?.[0])}/>
                             <b>{file ? file.name : 'Tải thêm tài liệu'}</b>
                             <span>Tối đa 20 MB</span>
                           </label>
                           <button className="secondary wide" onClick={upload} disabled={!file || !!busy}>{busy === 'upload' ? 'Đang OCR…' : 'Tải giấy tờ lên'}</button>
                         </div>
                       )}
                       
                       <div className="submit-block">
                         <label className="check-row">
                           <input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)}/>
                           <span>Tôi đồng ý để cơ quan tiếp nhận và xử lý dữ liệu.</span>
                         </label>
                         <button className="primary wide" onClick={submit} disabled={!!busy || !consent}>{busy === 'submit' ? 'Đang gửi…' : 'Nộp hồ sơ tiền kiểm'}</button>
                       </div>
                       <button className="text-button" onClick={() => { setCurrent(null); setProcedureType('none'); }}>Tạo hồ sơ khác</button>
                     </div>
                   )}
                   
                   {notice && <div className={`alert ${notice.includes('Đã') || notice.includes('đã') ? 'success' : 'error'}`} role="status">{notice}</div>}
                 </div>
              </div>
           )}
        </div>
        
        <CitizenAssistant activeCaseId={current?.id} onChecklist={handleChecklist} selectedContext={selectedText} />
      </main>
    </Shell>
  );
}

function Status({ value }: { value: string }) { return <span className={`status status-${value}`}>{humanizeStatus(value)}</span>; }
function Empty({ title, text }: { title: string; text: string }) { return <div className="empty-state"><span>◇</span><h3>{title}</h3><p>{text}</p></div>; }

function OfficerPortal() {
  const [logged, setLogged] = useState(!!token()); const [cases, setCases] = useState<CaseRecord[]>([]); const [summary, setSummary] = useState<DashboardSummary>(); const [selected, setSelected] = useState<CaseDetail>();
  const [search, setSearch] = useState(''); const [filter, setFilter] = useState(''); const [sort, setSort] = useState('priority_desc'); const [loading, setLoading] = useState(true); const [detailLoading, setDetailLoading] = useState(false); const [notice, setNotice] = useState('');
  const loadQueue = async () => { setLoading(true); try { const [queue, dashboard] = await Promise.all([api<CaseRecord[]>(`/officer/cases?${buildCaseQuery(search, filter, sort)}`), api<DashboardSummary>('/officer/dashboard/summary')]); setCases(queue); setSummary(dashboard); } catch (cause) { handleError(cause); } finally { setLoading(false); } };
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
  const [documentId, setDocumentId] = useState(detail.documents[0]?.id ?? ''); const [fields, setFields] = useState<ExtractedField[]>([]); const [previewUrl, setPreviewUrl] = useState(''); const [previewError, setPreviewError] = useState(''); const [busy, setBusy] = useState(''); const [supplement, setSupplement] = useState(''); const [selectedFindings, setSelectedFindings] = useState<string[]>(detail.findings.filter(item => item.status === 'open').map(item => item.id)); const [reasons, setReasons] = useState<Record<string, string>>({});
  const activeDocument = detail.documents.find(item => item.id === documentId);
  useEffect(() => { setDocumentId(detail.documents[0]?.id ?? ''); setSelectedFindings(detail.findings.filter(item => item.status === 'open').map(item => item.id)); }, [detail.case.id]);
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
  return <div className="review-workspace"><div className="review-header"><div><div className="case-code"><span>{detail.case.case_code}</span><Status value={detail.case.status}/></div><h2>{procedureNames[detail.case.procedure_id] ?? detail.case.procedure_id}</h2><p>Phiên bản hồ sơ {detail.submission.version} · Bộ quy tắc {detail.submission.procedure_rule_version}</p></div><div className="review-header-actions">{detail.case.status === 'awaiting_officer_review' && <button className="primary" onClick={claim} disabled={!!busy}>{busy === 'claim' ? 'Đang nhận…' : 'Nhận xử lý'}</button>}<button className="icon-button" aria-label="Làm mới hồ sơ" onClick={onRefresh}>↻</button></div></div><div className="progress-line"><span className="done">Đã nộp</span><span className="done">Tiền kiểm AI</span><span className={detail.case.status === 'awaiting_officer_review' ? 'current' : 'done'}>Tiếp nhận</span><span className={detail.case.status === 'in_officer_review' ? 'current' : ''}>Thẩm tra</span><span className={detail.case.status === 'precheck_ready' ? 'done' : ''}>Hoàn tất</span></div><div className="review-columns"><EvidencePanel documents={detail.documents} activeId={documentId} onSelect={setDocumentId} active={activeDocument} previewUrl={previewUrl} previewError={previewError}/><DataPanel submission={detail.submission.form_data} fields={fields} editable={detail.case.status === 'in_officer_review'} onSaved={async () => { if (documentId) setFields(await api<ExtractedField[]>(`/officer/documents/${documentId}/fields`)); }} onError={onError}/><FindingsPanel findings={detail.findings} busy={busy} reasons={reasons} setReasons={setReasons} onDecide={decide}/></div><div className="review-bottom"><details><summary>Lịch sử xử lý <span>{detail.timeline.length}</span></summary><ol className="timeline">{detail.timeline.length ? detail.timeline.map(item => <li key={item.id}><i/><div><b>{humanizeStatus(item.event_type)}</b><small>{formatDate(item.created_at)} · {item.actor_id}</small></div></li>) : <li>Chưa có hoạt động.</li>}</ol></details>{detail.case.status === 'in_officer_review' && <section className="decision-box"><div><span className="eyebrow">HÀNH ĐỘNG XỬ LÝ</span><h3>Yêu cầu công dân bổ sung</h3></div><textarea value={supplement} onChange={event => setSupplement(event.target.value)} maxLength={5000} placeholder="Mô tả rõ thông tin hoặc giấy tờ cần bổ sung…"/><div className="finding-selector">{detail.findings.filter(item => item.status === 'open').map(item => <label key={item.id}><input type="checkbox" checked={selectedFindings.includes(item.id)} onChange={() => setSelectedFindings(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id])}/><span>{item.message}</span></label>)}</div><div className="decision-actions"><button className="warning-button" disabled={!supplement.trim() || !selectedFindings.length || !!busy} onClick={requestSupplement}>Yêu cầu bổ sung</button><button className="ghost" disabled={!!busy} onClick={() => transition('escalated')}>Chuyển chuyên môn</button><button className="ghost" disabled={!!busy} onClick={rerun}>{busy === 'rerun' ? 'Đang kiểm tra…' : 'Chạy lại kiểm tra'}</button><button className="success-button" disabled={!!busy || detail.findings.some(item => item.severity === 'error' && item.status === 'open')} onClick={() => transition('precheck_ready')}>Đạt tiền kiểm</button></div></section>}</div></div>;
}

function EvidencePanel({ documents, activeId, onSelect, active, previewUrl, previewError }: { documents: CaseDocument[]; activeId: string; onSelect: (id: string) => void; active?: CaseDocument; previewUrl: string; previewError: string }) {
  return <section className="review-panel evidence-panel"><div className="column-heading"><span>TÀI LIỆU & CĂN CỨ</span><b>{documents.length}</b></div><div className="document-tabs">{documents.map(item => <button key={item.id} className={activeId === item.id ? 'active' : ''} onClick={() => onSelect(item.id)}><span>▤</span><div><b>{item.original_filename ?? item.document_type}</b><small>{formatBytes(item.size_bytes)}</small></div><Status value={item.ocr_status}/></button>)}</div>{active ? <div className="document-viewer">{previewUrl ? active.content_type === 'application/pdf' ? <iframe title={active.original_filename ?? 'Tài liệu'} src={previewUrl}/> : <img alt={active.original_filename ?? 'Tài liệu'} src={previewUrl}/> : <div className="document-placeholder"><div className="paper-lines"><i/><i/><i/><i/><i/></div><span>▧</span><b>Chưa có bản xem trước</b><small>{previewError || 'Tài liệu được bảo vệ và chỉ mở khi được cấp quyền.'}</small></div>}<div className="viewer-meta"><span>{active.ocr_engine ? `OCR: ${active.ocr_engine}` : 'Chưa có OCR'}</span><Status value={active.ocr_status}/></div></div> : <Empty title="Chưa có tài liệu" text="Hồ sơ này chưa đính kèm giấy tờ."/>}</section>;
}

function DataPanel({ submission, fields, editable, onSaved, onError }: { submission: Record<string, unknown>; fields: ExtractedField[]; editable: boolean; onSaved: () => Promise<void>; onError: (cause: unknown) => void }) {
  const [editing, setEditing] = useState<string>(); const [value, setValue] = useState(''); const [busy, setBusy] = useState(false);
  const save = async (field: ExtractedField) => { setBusy(true); try { await api(`/officer/extracted-fields/${field.id}`, { method: 'PATCH', body: JSON.stringify({ normalized_value: value, reason: 'Cán bộ đối chiếu tài liệu gốc' }) }); setEditing(undefined); await onSaved(); } catch (cause) { onError(cause); } finally { setBusy(false); } };
  const rows = Object.entries(submission);
  return <section className="review-panel data-panel"><div className="column-heading"><span>DỮ LIỆU CÓ CẤU TRÚC</span><b>{rows.length + fields.length}</b></div><div className="data-section"><h3>Thông tin người khai</h3>{rows.length ? rows.map(([key, item]) => <div className="data-row" key={key}><span>{humanizeStatus(key)}</span><strong>{String(item || '—')}</strong><small className="verified">✓ Đã khai</small></div>) : <p className="empty">Không có dữ liệu biểu mẫu.</p>}</div><div className="data-section"><div className="section-title"><h3>Kết quả OCR</h3>{fields.some(item => item.review_status === 'needs_human_review') && <span className="needs-review">Cần xác minh</span>}</div>{fields.length ? fields.map(field => <div className={`ocr-row ${field.review_status === 'needs_human_review' ? 'low-confidence' : ''}`} key={field.id}><div><span>{humanizeStatus(field.field_key)}</span><small>Độ tin cậy {Math.round(field.confidence * 100)}%</small></div>{editing === field.id ? <div className="edit-field"><input value={value} onChange={event => setValue(event.target.value)} autoFocus/><button onClick={() => save(field)} disabled={busy}>Lưu</button><button className="text-button" onClick={() => setEditing(undefined)}>Hủy</button></div> : <div className="field-value"><strong>{field.normalized_value || field.raw_value || '—'}</strong>{editable && <button aria-label={`Sửa ${field.field_key}`} onClick={() => { setEditing(field.id); setValue(field.normalized_value || field.raw_value); }}>✎</button>}</div>}</div>) : <p className="empty">Chọn tài liệu có dữ liệu OCR để xem.</p>}</div></section>;
}

function FindingsPanel({ findings, busy, reasons, setReasons, onDecide }: { findings: Finding[]; busy: string; reasons: Record<string, string>; setReasons: React.Dispatch<React.SetStateAction<Record<string, string>>>; onDecide: (finding: Finding, decision: 'accept' | 'dismiss' | 'escalate') => void }) {
  const openCount = findings.filter(item => item.status === 'open').length;
  return <section className="review-panel findings-panel"><div className="column-heading"><span>KẾT QUẢ KIỂM TRA</span><b>{openCount}</b></div><div className="finding-summary"><span><i className="red"/>{findings.filter(item => item.severity === 'error' && item.status === 'open').length} lỗi</span><span><i className="gold"/>{findings.filter(item => item.severity === 'warning' && item.status === 'open').length} cảnh báo</span></div>{findings.length ? findings.map(item => <article className={`finding-card ${item.severity} ${item.status !== 'open' ? 'resolved' : ''}`} key={item.id}><div className="finding-title"><span>{item.severity === 'error' ? '!' : item.severity === 'warning' ? '△' : 'i'}</span><div><b>{item.severity === 'error' ? 'Cần xử lý' : item.severity === 'warning' ? 'Cần lưu ý' : 'Thông tin'}</b><small>{item.source === 'rule' ? 'Quy tắc nghiệp vụ' : 'Gợi ý AI'}</small></div><Status value={item.status}/></div><p>{item.message}</p>{item.suggestion && <small className="suggestion-text">Gợi ý: {item.suggestion}</small>}{item.status === 'open' && <><input className="reason-input" value={reasons[item.id] ?? ''} onChange={event => setReasons(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Lý do xử lý (nếu cần)"/><div className="finding-actions"><button onClick={() => onDecide(item, 'accept')} disabled={!!busy}>Xác nhận</button><button onClick={() => onDecide(item, 'dismiss')} disabled={!!busy}>Bỏ qua</button><button onClick={() => onDecide(item, 'escalate')} disabled={!!busy}>Chuyển cấp</button></div></>}</article>) : <Empty title="Không có cảnh báo" text="Chưa phát hiện vấn đề trong phiên bản hiện tại."/>}</section>;
}

function App() { return location.pathname.startsWith('/officer') ? <OfficerPortal/> : <CitizenPortal/>; }
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);

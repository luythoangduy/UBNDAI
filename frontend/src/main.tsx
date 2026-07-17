import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MessageCircle, X, FileText, Download, Check, Bold, Italic, Strikethrough, List as ListIcon, Printer } from 'lucide-react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { api, apiBlob, ApiError, idempotency, setToken, token } from './api';
import type { CaseDetail, CaseDocument, CaseRecord, ChatResponse, DashboardSummary, ExtractedField, Finding, PortalRole, PreprocessResult, PreprocessStep } from './types';
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

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));
const escapeHtml = (value: string) => value.replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch] as string));

// Trường của template DOCX khai_sinh.giay_khai_sinh (data/draft_templates/khai_sinh_giay_khai_sinh.json)
const DRAFT_TEMPLATE_KEYS = ['ho_ten_con', 'ngay_sinh', 'gioi_tinh', 'dan_toc', 'quoc_tich', 'noi_sinh', 'que_quan', 'so_dinh_danh_ca_nhan', 'ho_ten_me', 'nam_sinh_me', 'dan_toc_me', 'quoc_tich_me', 'noi_cu_tru_me', 'ho_ten_cha', 'nam_sinh_cha', 'dan_toc_cha', 'quoc_tich_cha', 'noi_cu_tru_cha', 'ho_ten_nguoi_di_dang_ky', 'giay_to_tuy_than_nguoi_di_dang_ky', 'noi_dang_ky', 'ngay_dang_ky', 'so', 'quyen_so', 'chuc_vu_nguoi_ky', 'ho_ten_nguoi_ky'];
const OCR_FIELD_ALIASES: Record<string, string> = {
  ho_ten: 'ho_ten_con', ho_va_ten: 'ho_ten_con',
  so_cccd: 'so_dinh_danh_ca_nhan', so_dinh_danh: 'so_dinh_danh_ca_nhan', so_can_cuoc: 'so_dinh_danh_ca_nhan',
  nguyen_quan: 'que_quan', noi_cu_tru: 'noi_cu_tru_me', noi_thuong_tru: 'noi_cu_tru_me', dia_chi: 'noi_cu_tru_me',
};

function mapExtractedToDraftValues(fields: ExtractedField[]): Record<string, string> {
  const known = new Set(DRAFT_TEMPLATE_KEYS);
  const values: Record<string, string> = {};
  for (const field of fields) {
    const value = (field.normalized_value || field.raw_value || '').trim();
    if (!value) continue;
    const key = known.has(field.field_key) ? field.field_key : OCR_FIELD_ALIASES[field.field_key];
    if (key && !values[key]) values[key] = value;
  }
  return values;
}

function fill(values: Record<string, string>, key: string, length = 46): string {
  const value = values[key];
  return value ? `<strong>${escapeHtml(value)}</strong>` : `[${'.'.repeat(length)}]`;
}

// Trường của tờ khai (kho template: data/draft_templates/khai_sinh_to_khai.json).
// Layout bám NGUYÊN VĂN mẫu Tờ khai đăng ký khai sinh ban hành kèm Thông tư
// 04/2024/TT-BTP (bản đang áp dụng) — văn bản NGƯỜI DÂN gửi cơ quan đăng ký.
const TO_KHAI_KEYS = ['noi_dang_ky', 'ho_ten_nguoi_yeu_cau', 'ngay_sinh_nguoi_yeu_cau', 'noi_cu_tru_nguoi_yeu_cau', 'giay_to_tuy_than_nguoi_yeu_cau', 'quan_he_voi_nguoi_duoc_khai_sinh', 'ho_ten_con', 'ngay_sinh', 'gioi_tinh', 'dan_toc', 'quoc_tich', 'noi_sinh', 'que_quan', 'ho_ten_me', 'nam_sinh_me', 'dan_toc_me', 'quoc_tich_me', 'noi_cu_tru_me', 'giay_to_tuy_than_me', 'ho_ten_cha', 'nam_sinh_cha', 'dan_toc_cha', 'quoc_tich_cha', 'noi_cu_tru_cha', 'giay_to_tuy_than_cha', 'so_gcn_ket_hon', 'quyen_so_gcn_ket_hon', 'ngay_dang_ky_ket_hon', 'noi_dang_ky_ket_hon'];

type TemplateSource = { label: string; links: { title: string; url: string }[] };
const TEMPLATE_SOURCE: TemplateSource = {
  label: 'Mẫu: Tờ khai đăng ký khai sinh — Phụ lục 05, Thông tư 04/2024/TT-BTP (Bộ Tư pháp), hiệu lực 16/8/2024',
  links: [
    { title: 'Văn bản Thông tư 04/2024/TT-BTP', url: 'https://luatvietnam.vn/tu-phap/thong-tu-04-2024-tt-btp-sua-doi-thong-tu-02-2020-tt-btp-thong-tu-04-2020-tt-btp-350235-d1.html' },
    { title: 'Mẫu đang áp dụng', url: 'https://luatvietnam.vn/bieu-mau/mau-to-khai-dang-ky-khai-sinh-571-26974-article.html' },
  ],
};

const VN_ONES = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín'];
function vnReadTwo(value: number): string {
  const tens = Math.floor(value / 10), unit = value % 10;
  if (tens === 0) return VN_ONES[unit];
  const prefix = tens === 1 ? 'mười' : `${VN_ONES[tens]} mươi`;
  if (unit === 0) return prefix;
  const unitWord = unit === 1 && tens > 1 ? 'mốt' : unit === 5 ? 'lăm' : VN_ONES[unit];
  return `${prefix} ${unitWord}`;
}
function vnReadNumber(value: number): string {
  if (value < 10) return VN_ONES[value];
  if (value < 100) return vnReadTwo(value);
  const readThree = (n: number, full: boolean): string => {
    const hundreds = Math.floor(n / 100), rest = n % 100;
    const parts: string[] = [];
    if (hundreds || full) parts.push(`${VN_ONES[hundreds]} trăm`);
    if (rest) {
      if (rest < 10 && (hundreds || full)) parts.push('linh');
      parts.push(vnReadTwo(rest));
    }
    return parts.join(' ');
  };
  if (value < 1000) return readThree(value, false);
  const thousands = Math.floor(value / 1000), rest = value % 1000;
  let result = `${VN_ONES[thousands]} nghìn`;
  if (rest) result += ' ' + readThree(rest, rest < 100);
  return result;
}
// "Ngày, tháng, năm sinh ... ghi bằng chữ" theo mẫu — chỉ đọc được khi OCR trả DD/MM/YYYY.
function vnDateInWords(raw?: string): string | undefined {
  const match = raw?.trim().match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
  if (!match) return undefined;
  return `Ngày ${vnReadNumber(Number(match[1]))} tháng ${vnReadNumber(Number(match[2]))} năm ${vnReadNumber(Number(match[3]))}`;
}

function buildToKhaiKhaiSinhHtml(values: Record<string, string>): string {
  const ngaySinhChu = vnDateInWords(values.ngay_sinh);
  return `<h2>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<br/>Độc lập - Tự do - Hạnh phúc</h2>
<h1>TỜ KHAI ĐĂNG KÝ KHAI SINH</h1>
<p>Kính gửi: (1) ${fill(values, 'noi_dang_ky', 40)}</p>
<p>Họ, chữ đệm, tên người yêu cầu: ${fill(values, 'ho_ten_nguoi_yeu_cau', 32)}</p>
<p>Ngày, tháng, năm sinh: ${fill(values, 'ngay_sinh_nguoi_yeu_cau', 36)}</p>
<p>Nơi cư trú: (2) ${fill(values, 'noi_cu_tru_nguoi_yeu_cau', 44)}</p>
<p>Giấy tờ tùy thân: (3) ${fill(values, 'giay_to_tuy_than_nguoi_yeu_cau', 40)}</p>
<p>Quan hệ với người được khai sinh: ${fill(values, 'quan_he_voi_nguoi_duoc_khai_sinh', 28)}</p>
<p><strong>Đề nghị cơ quan đăng ký khai sinh cho người dưới đây:</strong></p>
<p>Họ, chữ đệm, tên: ${fill(values, 'ho_ten_con', 40)}</p>
<p>Ngày, tháng, năm sinh: ${fill(values, 'ngay_sinh', 14)} ghi bằng chữ: ${ngaySinhChu ? `<strong>${escapeHtml(ngaySinhChu)}</strong>` : `[${'.'.repeat(24)}]`}</p>
<p>Giới tính: ${fill(values, 'gioi_tinh', 8)} Dân tộc: ${fill(values, 'dan_toc', 8)} Quốc tịch: ${fill(values, 'quoc_tich', 10)}</p>
<p>Nơi sinh: (4) ${fill(values, 'noi_sinh', 44)}</p>
<p>Quê quán: ${fill(values, 'que_quan', 44)}</p>
<p>Họ, chữ đệm, tên người mẹ: ${fill(values, 'ho_ten_me', 34)}</p>
<p>Năm sinh: (5) ${fill(values, 'nam_sinh_me', 6)} Dân tộc: (2) ${fill(values, 'dan_toc_me', 6)} Quốc tịch: (2) ${fill(values, 'quoc_tich_me', 8)}</p>
<p>Nơi cư trú: (2) ${fill(values, 'noi_cu_tru_me', 44)}</p>
<p>Giấy tờ tùy thân: (3) ${fill(values, 'giay_to_tuy_than_me', 40)}</p>
<p>Họ, chữ đệm, tên người cha: ${fill(values, 'ho_ten_cha', 34)}</p>
<p>Năm sinh: (5) ${fill(values, 'nam_sinh_cha', 6)} Dân tộc: (2) ${fill(values, 'dan_toc_cha', 6)} Quốc tịch: (2) ${fill(values, 'quoc_tich_cha', 8)}</p>
<p>Nơi cư trú: (2) ${fill(values, 'noi_cu_tru_cha', 44)}</p>
<p>Giấy tờ tùy thân: (3) ${fill(values, 'giay_to_tuy_than_cha', 40)}</p>
<p><em>Thông tin về Giấy chứng nhận kết hôn của cha, mẹ trẻ (nếu cha, mẹ trẻ đã đăng ký kết hôn):</em> Số: ${fill(values, 'so_gcn_ket_hon', 8)}, Quyển số: ${fill(values, 'quyen_so_gcn_ket_hon', 8)}, đăng ký ngày ${fill(values, 'ngay_dang_ky_ket_hon', 12)} tại ${fill(values, 'noi_dang_ky_ket_hon', 28)}</p>
<p>Tôi cam đoan nội dung đề nghị đăng ký khai sinh trên đây là đúng sự thật, được sự thỏa thuận nhất trí của các bên liên quan theo quy định pháp luật.</p>
<p>Tôi chịu hoàn toàn trách nhiệm trước pháp luật về nội dung cam đoan của mình.</p>
<p><em>Làm tại: [${'.'.repeat(18)}], ngày [......] tháng [......] năm [......]</em></p>
<p>Đề nghị cấp bản sao (6): Có ☐  Không ☐ — Số lượng: [......] bản</p>
<p><strong>Người yêu cầu</strong><br/><em>(Ký, ghi rõ họ, chữ đệm, tên)</em></p>
<p><br/></p>
<p><em>Chú thích:</em><br/>
<em>(1) Ghi rõ tên cơ quan đăng ký khai sinh.</em><br/>
<em>(2) Chỉ ghi trong trường hợp người có yêu cầu đăng ký hộ tịch chưa có/không cung cấp số định danh cá nhân/căn cước công dân/thẻ căn cước/chứng minh nhân dân; không cung cấp đầy đủ thông tin ngày, tháng, năm sinh. Nơi cư trú ghi theo nơi đăng ký thường trú; nếu không có thì ghi nơi đăng ký tạm trú; nếu không có cả hai thì ghi nơi ở hiện tại.</em><br/>
<em>(3) Ghi số định danh cá nhân/căn cước công dân/thẻ căn cước; trường hợp không có thì ghi giấy tờ hợp lệ thay thế.</em><br/>
<em>(4) Trường hợp sinh tại cơ sở y tế thì ghi tên cơ sở y tế và địa chỉ; sinh ngoài cơ sở y tế thì ghi địa danh hành chính.</em><br/>
<em>(5) Ghi đầy đủ ngày, tháng sinh của cha, mẹ (nếu có).</em><br/>
<em>(6) Đánh dấu X vào ô nếu có yêu cầu cấp bản sao và ghi rõ số lượng.</em></p>`;
}

type OcrPhase = 'idle' | 'upload' | 'prep' | 'recognize' | 'compose' | 'ready';
const PHASE_ORDER: OcrPhase[] = ['idle', 'upload', 'prep', 'recognize', 'compose', 'ready'];
const OCR_STAGES: { id: OcrPhase; label: string; hint: string }[] = [
  { id: 'upload', label: 'Tải lên & xác thực', hint: 'Kiểm tra định dạng và checksum' },
  { id: 'prep', label: 'Làm phẳng & chính diện', hint: 'Nắn phối cảnh, khử nghiêng, tăng tương phản' },
  { id: 'recognize', label: 'Nhận dạng OCR', hint: 'Bóc tách trường dữ liệu + bounding box' },
  { id: 'compose', label: 'Soạn văn bản DOCX', hint: 'Điền dữ liệu vào mẫu giấy khai sinh' },
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

function WordWorkspace({ content, fileName, onSelectionChange, onDownload, downloading, statusHint, source }: { content: string; fileName: string; onSelectionChange?: (text: string) => void; onDownload?: (html: string) => void; downloading?: boolean; statusHint?: string; source?: TemplateSource }) {
  const [zoom, setZoom] = useState(100);
  const editor = useEditor({
    extensions: [StarterKit],
    content,
    onSelectionUpdate: ({ editor }) => {
      if (!onSelectionChange) return;
      const { from, to } = editor.state.selection;
      onSelectionChange(from !== to ? editor.state.doc.textBetween(from, to, ' ') : '');
    }
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
        <div className="word-file"><b>{fileName}</b><small>Đã lưu vào hồ sơ · Bản nháp</small></div>
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
  
  const [started, setStarted] = useState(false);
  const [docContent, setDocContent] = useState(() => buildToKhaiKhaiSinhHtml({}));
  const [selectedText, setSelectedText] = useState('');
  const [extractedFields, setExtractedFields] = useState<ExtractedField[]>();
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [ocrPhase, setOcrPhase] = useState<OcrPhase>('idle');
  const [prepSteps, setPrepSteps] = useState<PreprocessStep[]>([]);
  const [prepIndex, setPrepIndex] = useState(0);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});

  const refresh = async () => setCases(await api<CaseRecord[]>('/citizen/cases'));
  useEffect(() => { if (logged) refresh().catch(cause => setNotice((cause as Error).message)); }, [logged]);
  if (!logged) return <Login role="citizen" onSuccess={() => setLogged(true)}/>;
  
  const run = async (name: string, work: () => Promise<void>) => { setBusy(name); setNotice(''); try { await work(); } catch (cause) { setNotice((cause as Error).message); } finally { setBusy(''); } };
  
  // Một luồng duy nhất: mở tờ khai mẫu để tự điền, OCR là bước "AI điền hộ" tùy chọn.
  const startCase = () => {
    setStarted(true);
    setDocContent(buildToKhaiKhaiSinhHtml({}));
    setExtractedFields(undefined);
    setPreviewUrl(undefined);
    setOcrPhase('idle');
    setPrepSteps([]);
    setPrepIndex(0);
    setDraftValues({});
    run('create', async () => {
      const item = await api<CaseRecord>('/citizen/cases', { method: 'POST', body: JSON.stringify({ procedure_id: 'khai_sinh', locality_code: '00001' }) });
      setCurrent(item);
      setNotice('Đã khởi tạo tờ khai. Điền trực tiếp hoặc tải giấy tờ để AI điền tự động.');
      await refresh();
    });
  };

  const upload = () => current && file && run('upload', async () => {
    const isPdf = file.type === 'application/pdf';
    setOcrPhase('upload'); setPrepSteps([]); setPrepIndex(0); setExtractedFields(undefined);
    setPreviewUrl(URL.createObjectURL(file));

    const intent = await api<{ document_id: string; upload_url: string }>(`/citizen/cases/${current.id}/documents/upload-intents`, { method: 'POST', body: JSON.stringify({ filename: file.name, content_type: file.type, size_bytes: file.size }) });
    const uploaded = await fetch(intent.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': 'application/octet-stream', Authorization: `Bearer ${token()}` } });
    if (!uploaded.ok) throw new Error('Không thể tải file lên');

    setOcrPhase('prep');
    // OCR (LLM) chạy song song trong lúc minh hoạ các bước tiền xử lý
    const completePromise = api<{ document: CaseDocument, fields: ExtractedField[] }>(`/citizen/documents/${intent.document_id}/complete`, { method: 'POST', body: JSON.stringify({ sha256: await checksum(file) }) });
    completePromise.catch(() => undefined);
    if (!isPdf) {
      try {
        const prep = await api<PreprocessResult>(`/citizen/documents/${intent.document_id}/preprocess`, { method: 'POST' });
        if (prep.steps.length) {
          setPrepSteps(prep.steps);
          for (let index = 0; index < prep.steps.length; index += 1) { setPrepIndex(index); await sleep(1100); }
        }
      } catch { /* tiền xử lý chỉ minh hoạ — lỗi không chặn OCR */ }
    }
    setOcrPhase('recognize');
    let completeResp: { document: CaseDocument, fields: ExtractedField[] };
    try { completeResp = await completePromise; } catch (cause) { setOcrPhase('idle'); throw cause; }
    setExtractedFields(completeResp.fields);
    setOcrPhase('compose');
    // Trường đã điền trước đó (OCR lần trước) được giữ nguyên — OCR mới chỉ điền chỗ trống.
    const merged = { ...mapExtractedToDraftValues(completeResp.fields), ...draftValues };
    setDraftValues(merged);
    setDocContent(buildToKhaiKhaiSinhHtml(merged));
    await sleep(2800); // giữ màn bounding box đủ lâu để thấy các vùng nhận dạng trước khi chuyển sang DOCX
    setOcrPhase('ready');
    setNotice(`AI đã nhận dạng ${completeResp.fields.length} trường và điền vào tờ khai.`);
    await refreshCurrent(current.id);
  });

  // Xuất DOCX từ chính HTML đang hiển thị trong editor (WYSIWYG — cách làm của C2):
  // người dân sửa gì trong tờ khai thì file tải xuống có đúng nội dung đó.
  const downloadDocx = (html: string) => run('docx', async () => {
    const blob = await apiBlob('/drafts/export.docx', { method: 'POST', body: JSON.stringify({ html, filename: 'to-khai-dang-ky-khai-sinh.docx' }) });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'to-khai-dang-ky-khai-sinh.docx'; anchor.click();
    URL.revokeObjectURL(url);
    setNotice('Đã tải xuống tờ khai đăng ký khai sinh (DOCX).');
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
  const handleChecklist = async (caseId: string) => { await refreshCurrent(caseId); setStarted(true); setNotice('Đã nhận danh sách giấy tờ. Vui lòng chuẩn bị và tải lên.'); };

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
                 <h2>Đăng ký khai sinh</h2>
                 <div className="selector-cards">
                   <button onClick={startCase} className="selector-card">
                     <FileText size={32} />
                     <h3>Tờ khai đăng ký khai sinh</h3>
                     <p>Soạn trực tiếp trên mẫu chuẩn Thông tư 04/2024/TT-BTP, hoặc tải bản chụp giấy tờ để AI điền tự động.</p>
                   </button>
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
                        fileName="to-khai-dang-ky-khai-sinh.docx"
                        onSelectionChange={setSelectedText}
                        onDownload={downloadDocx}
                        downloading={busy === 'docx'}
                        statusHint={`${TO_KHAI_KEYS.filter(key => draftValues[key]).length} trường đã điền từ OCR · ${TO_KHAI_KEYS.filter(key => !draftValues[key]).length} trường còn trống`}
                        source={TEMPLATE_SOURCE}
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

                       <div className="upload-block">
                         <h3 style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--navy)' }}>AI điền tự động từ giấy tờ</h3>
                         <label className="dropzone">
                           <input type="file" accept="application/pdf,image/jpeg,image/png" onChange={event => setFile(event.target.files?.[0])}/>
                           <b>{file ? file.name : 'Chọn bản chụp giấy tờ'}</b>
                           <span>PDF, JPG hoặc PNG · tối đa 20 MB</span>
                         </label>
                         <button className="secondary wide" onClick={upload} disabled={!file || !!busy}>{busy === 'upload' ? 'Đang xử lý OCR…' : 'Tải lên & điền tự động'}</button>
                       </div>
                       
                       <div className="submit-block">
                         <label className="check-row">
                           <input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)}/>
                           <span>Tôi đồng ý để cơ quan tiếp nhận và xử lý dữ liệu.</span>
                         </label>
                         <button className="primary wide" onClick={submit} disabled={!!busy || !consent}>{busy === 'submit' ? 'Đang gửi…' : 'Nộp hồ sơ tiền kiểm'}</button>
                       </div>
                       <button className="text-button" onClick={() => { setCurrent(null); setStarted(false); setOcrPhase('idle'); setPrepSteps([]); setPrepIndex(0); setExtractedFields(undefined); setPreviewUrl(undefined); setFile(undefined); setDraftValues({}); setDocContent(buildToKhaiKhaiSinhHtml({})); }}>Tạo hồ sơ khác</button>
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
  return <div className="review-workspace"><div className="review-header"><div><div className="case-code"><span>{detail.case.case_code}</span><Status value={detail.case.status}/></div><h2>{procedureNames[detail.case.procedure_id] ?? detail.case.procedure_id}</h2><p>Phiên bản hồ sơ {detail.submission.version} · Bộ quy tắc {detail.submission.procedure_rule_version}</p></div><div className="review-header-actions">{detail.case.status === 'awaiting_officer_review' && <button className="primary" onClick={claim} disabled={!!busy}>{busy === 'claim' ? 'Đang nhận…' : 'Nhận xử lý'}</button>}<button className="icon-button" aria-label="Làm mới hồ sơ" onClick={onRefresh}>↻</button></div></div><div className="progress-line"><span className="done">Đã nộp</span><span className="done">Tiền kiểm AI</span><span className={detail.case.status === 'awaiting_officer_review' ? 'current' : 'done'}>Tiếp nhận</span><span className={detail.case.status === 'in_officer_review' ? 'current' : ''}>Thẩm tra</span><span className={detail.case.status === 'precheck_ready' ? 'done' : ''}>Hoàn tất</span></div><div className="review-columns"><EvidencePanel documents={detail.documents} activeId={documentId} onSelect={setDocumentId} active={activeDocument} previewUrl={previewUrl} previewError={previewError} fields={fields}/><DataPanel submission={detail.submission.form_data} fields={fields} editable={detail.case.status === 'in_officer_review'} onSaved={async () => { if (documentId) setFields(await api<ExtractedField[]>(`/officer/documents/${documentId}/fields`)); }} onError={onError}/><FindingsPanel findings={detail.findings} busy={busy} reasons={reasons} setReasons={setReasons} onDecide={decide}/></div><div className="review-bottom"><details><summary>Lịch sử xử lý <span>{detail.timeline.length}</span></summary><ol className="timeline">{detail.timeline.length ? detail.timeline.map(item => <li key={item.id}><i/><div><b>{humanizeStatus(item.event_type)}</b><small>{formatDate(item.created_at)} · {item.actor_id}</small></div></li>) : <li>Chưa có hoạt động.</li>}</ol></details>{detail.case.status === 'in_officer_review' && <section className="decision-box"><div><span className="eyebrow">HÀNH ĐỘNG XỬ LÝ</span><h3>Yêu cầu công dân bổ sung</h3></div><textarea value={supplement} onChange={event => setSupplement(event.target.value)} maxLength={5000} placeholder="Mô tả rõ thông tin hoặc giấy tờ cần bổ sung…"/><div className="finding-selector">{detail.findings.filter(item => item.status === 'open').map(item => <label key={item.id}><input type="checkbox" checked={selectedFindings.includes(item.id)} onChange={() => setSelectedFindings(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id])}/><span>{item.message}</span></label>)}</div><div className="decision-actions"><button className="warning-button" disabled={!supplement.trim() || !selectedFindings.length || !!busy} onClick={requestSupplement}>Yêu cầu bổ sung</button><button className="ghost" disabled={!!busy} onClick={() => transition('escalated')}>Chuyển chuyên môn</button><button className="ghost" disabled={!!busy} onClick={rerun}>{busy === 'rerun' ? 'Đang kiểm tra…' : 'Chạy lại kiểm tra'}</button><button className="success-button" disabled={!!busy || detail.findings.some(item => item.severity === 'error' && item.status === 'open')} onClick={() => transition('precheck_ready')}>Đạt tiền kiểm</button></div></section>}</div></div>;
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
  const openCount = findings.filter(item => item.status === 'open').length;
  return <section className="review-panel findings-panel"><div className="column-heading"><span>KẾT QUẢ KIỂM TRA</span><b>{openCount}</b></div><div className="finding-summary"><span><i className="red"/>{findings.filter(item => item.severity === 'error' && item.status === 'open').length} lỗi</span><span><i className="gold"/>{findings.filter(item => item.severity === 'warning' && item.status === 'open').length} cảnh báo</span></div>{findings.length ? findings.map(item => <article className={`finding-card ${item.severity} ${item.status !== 'open' ? 'resolved' : ''}`} key={item.id}><div className="finding-title"><span>{item.severity === 'error' ? '!' : item.severity === 'warning' ? '△' : 'i'}</span><div><b>{item.severity === 'error' ? 'Cần xử lý' : item.severity === 'warning' ? 'Cần lưu ý' : 'Thông tin'}</b><small>{item.source === 'rule' ? 'Quy tắc nghiệp vụ' : 'Gợi ý AI'}</small></div><Status value={item.status}/></div><p>{item.message}</p>{item.suggestion && <small className="suggestion-text">Gợi ý: {item.suggestion}</small>}{item.status === 'open' && <><input className="reason-input" value={reasons[item.id] ?? ''} onChange={event => setReasons(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Lý do xử lý (nếu cần)"/><div className="finding-actions"><button onClick={() => onDecide(item, 'accept')} disabled={!!busy}>Xác nhận</button><button onClick={() => onDecide(item, 'dismiss')} disabled={!!busy}>Bỏ qua</button><button onClick={() => onDecide(item, 'escalate')} disabled={!!busy}>Chuyển cấp</button></div></>}</article>) : <Empty title="Không có cảnh báo" text="Chưa phát hiện vấn đề trong phiên bản hiện tại."/>}</section>;
}

function App() { return location.pathname.startsWith('/officer') ? <OfficerPortal/> : <CitizenPortal/>; }
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, PenLine, RotateCcw, X } from 'lucide-react';
import { isSignatureImage } from '../signature';

type SignatureFieldProps = {
  value: string;
  onChange: (value: string) => void;
  signerName: string;
  onSignerNameChange: (value: string) => void;
};

function SignatureDialog({ onClose, onSave }: { onClose: () => void; onSave: (value: string) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const drawing = useRef(false);
  const [hasInk, setHasInk] = useState(false);

  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const keydown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', keydown);
    return () => {
      window.removeEventListener('keydown', keydown);
      previousFocus.current?.focus();
    };
  }, [onClose]);

  const context = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return undefined;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineWidth = 4;
    ctx.strokeStyle = '#0d3158';
    return { canvas, ctx };
  };
  const point = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (canvas.width / rect.width),
      y: (event.clientY - rect.top) * (canvas.height / rect.height),
    };
  };
  const start = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    const state = context();
    if (!state) return;
    const next = point(event);
    drawing.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
    state.ctx.beginPath();
    state.ctx.moveTo(next.x, next.y);
  };
  const move = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const state = context();
    if (!state) return;
    const next = point(event);
    state.ctx.lineTo(next.x, next.y);
    state.ctx.stroke();
    setHasInk(true);
  };
  const stop = (event: React.PointerEvent<HTMLCanvasElement>) => {
    drawing.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const clear = () => {
    const state = context();
    if (state) state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
    setHasInk(false);
  };
  const save = () => {
    const canvas = canvasRef.current;
    if (canvas && hasInk) onSave(canvas.toDataURL('image/png'));
  };

  return createPortal(
    <div className="signature-modal" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="signature-dialog" role="dialog" aria-modal="true" aria-labelledby="signature-title" tabIndex={-1}>
        <header><div><span className="eyebrow">KÝ TRỰC TIẾP</span><h2 id="signature-title">Vẽ chữ ký bằng chuột hoặc cảm ứng</h2></div><button className="close-btn" aria-label="Đóng hộp ký" onClick={onClose}><X size={19}/></button></header>
        <p>Giữ chuột và kéo trong khung bên dưới. Chữ ký chỉ được gắn vào bản nháp sau khi bạn xác nhận.</p>
        <div className={`signature-canvas-wrap ${hasInk ? 'has-ink' : ''}`}><canvas ref={canvasRef} width={720} height={280} aria-label="Khung vẽ chữ ký" onPointerDown={start} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop} onPointerLeave={stop}/><span>Vẽ chữ ký tại đây</span></div>
        <footer><button className="ghost" onClick={clear} disabled={!hasInk}><RotateCcw size={15}/> Xóa và ký lại</button><div><button className="ghost" onClick={onClose}>Hủy</button><button className="primary" onClick={save} disabled={!hasInk}><Check size={15}/> Dùng chữ ký này</button></div></footer>
      </section>
    </div>,
    document.body,
  );
}

export function SignatureField({ value, onChange, signerName, onSignerNameChange }: SignatureFieldProps) {
  const [open, setOpen] = useState(false);
  const signed = isSignatureImage(value);
  return <>
    <section className={`document-signature ${signed ? 'signed' : ''}`} aria-label="Khu vực chữ ký người khai">
      <p>Ngày ký: {new Intl.DateTimeFormat('vi-VN').format(new Date())}</p>
      <strong>NGƯỜI KÝ</strong>
      <small>(Ký và ghi rõ họ tên)</small>
      <button className="signature-slot" type="button" onClick={() => setOpen(true)}>
        {signed ? <img src={value} alt="Chữ ký người khai"/> : <span><PenLine size={22}/><b>Bấm để ký trực tiếp</b><small>Dùng chuột hoặc màn hình cảm ứng</small></span>}
      </button>
      {signed && <div className="signature-controls"><span><Check size={13}/> Đã ký trên bản nháp</span><button type="button" onClick={() => setOpen(true)}>Ký lại</button><button type="button" onClick={() => onChange('')}>Xóa chữ ký</button></div>}
      <label className="signature-name-field">
        <span>Họ và tên người ký</span>
        <input type="text" value={signerName} onChange={event => onSignerNameChange(event.target.value)} maxLength={120} autoComplete="name" placeholder="Nhập đầy đủ họ và tên"/>
      </label>
    </section>
    {open && <SignatureDialog onClose={() => setOpen(false)} onSave={next => { onChange(next); setOpen(false); }}/>} 
  </>;
}

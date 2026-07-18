import { useEffect, useRef } from 'react';

export function DecisionDialog({ title, note, setNote, busy, valid, error, onClose, onConfirm }: { title: string; note: string; setNote: (value: string) => void; busy: boolean; valid: boolean; error?: string; onClose: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLElement>(null);
  const previous = useRef<HTMLElement | null>(null);
  useEffect(() => { previous.current = document.activeElement as HTMLElement; dialog.current?.focus(); return () => previous.current?.focus(); }, []);
  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape' && !busy) onClose();
    if (event.key === 'Tab' && dialog.current) {
      const elements = [...dialog.current.querySelectorAll<HTMLElement>('button, textarea, [href], input, select, [tabindex]:not([tabindex="-1"])')].filter(item => !item.hasAttribute('disabled'));
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  };
  return <div className="am-dialog-backdrop" onMouseDown={event => event.target === event.currentTarget && !busy && onClose()}><section ref={dialog} tabIndex={-1} className="am-dialog" role="dialog" aria-modal="true" aria-labelledby="decision-title" onKeyDown={onKeyDown}><h2 id="decision-title">{title}</h2><label>Ghi chú bắt buộc<textarea autoFocus value={note} maxLength={1000} onChange={event => setNote(event.target.value)} /></label><small>{note.length}/1000</small>{error && <p className="am-error" role="alert">{error}</p>}<div className="am-actions"><button disabled={busy} onClick={onClose}>Hủy</button><button className="am-button" disabled={busy || !valid} onClick={onConfirm}>{busy ? 'Đang lưu…' : 'Xác nhận'}</button></div></section></div>;
}

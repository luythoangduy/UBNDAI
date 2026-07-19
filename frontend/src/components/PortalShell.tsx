import { List, X } from '@phosphor-icons/react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PortalRole } from '../types';

type PortalShellProps = {
  children: ReactNode;
  role: PortalRole;
  path?: string;
  themeControl?: ReactNode;
};

export function Brand() {
  return (
    <a className="brand" href="/citizen">
      <span className="brand-mark">AI</span>
      <span><strong>UBNDAI</strong><small>Trợ lý thủ tục hành chính</small></span>
    </a>
  );
}

export function PortalShell({ children, role, path = location.pathname, themeControl }: PortalShellProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const shellRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMenuOpen(false);
  }, [path]);

  useEffect(() => {
    const main = shellRef.current?.querySelector('main');
    if (!main) return;
    if (!main.id) main.id = 'main-content';
    if (!main.hasAttribute('tabindex')) main.tabIndex = -1;
  }, [children]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        toggleRef.current?.focus();
      }
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [menuOpen]);

  const citizenCurrent = !path.startsWith('/chat') && role === 'citizen';
  const chatCurrent = path.startsWith('/chat');
  const officerCurrent = role === 'officer';

  return (
    <div ref={shellRef} className="app-shell">
      <a className="skip-link" href="#main-content">Bỏ qua điều hướng</a>
      <header className="topbar">
        <Brand />
        <nav id="primary-navigation" className={menuOpen ? 'open' : undefined} aria-label="Điều hướng chính">
          <a aria-current={citizenCurrent ? 'page' : undefined} className={citizenCurrent ? 'active' : undefined} href="/citizen">Dành cho công dân</a>
          <a aria-current={chatCurrent ? 'page' : undefined} className={chatCurrent ? 'active' : undefined} href="/chat">Trợ lý AI</a>
          <a aria-current={officerCurrent ? 'page' : undefined} className={officerCurrent ? 'active' : undefined} href="/officer">Cổng cán bộ</a>
        </nav>
        <div className="topbar-actions">
          <span className="secure-label">Kết nối bảo mật</span>
          {themeControl}
          <button
            ref={toggleRef}
            className="nav-toggle"
            type="button"
            aria-controls="primary-navigation"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? 'Đóng điều hướng' : 'Mở điều hướng'}
            onClick={() => setMenuOpen(current => !current)}
          >
            {menuOpen ? <X aria-hidden="true" /> : <List aria-hidden="true" />}
          </button>
        </div>
      </header>
      {children}
      <footer>
        <span>© 2026 UBNDAI</span>
        <span>Hệ thống hỗ trợ tiền kiểm, không thay thế quyết định của cơ quan có thẩm quyền.</span>
      </footer>
    </div>
  );
}

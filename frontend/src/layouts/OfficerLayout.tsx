import { Bell, ClipboardText, SignOut, SquaresFour } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { clearOfficerSession } from '../api';
import { ThemeSelector } from '../components/ThemeSelector';

const cautionStatus = 'CAUTION_REVIEW_REQUIRED';

export function OfficerLayout({ children }: { children?: ReactNode }) {
  const location = useLocation();
  const isApplicationList = location.pathname === '/officer/applications';
  const cautionSelected = isApplicationList && new URLSearchParams(location.search).get('status') === cautionStatus;
  const links = [
    { to: '/officer', label: 'Tổng quan', icon: SquaresFour, current: location.pathname === '/officer' || location.pathname === '/officer/' },
    { to: '/officer/applications', label: 'Hồ sơ', icon: ClipboardText, current: location.pathname.startsWith('/officer/applications') && !cautionSelected },
    { to: `/officer/applications?status=${cautionStatus}`, label: 'Cảnh báo', icon: Bell, current: cautionSelected },
  ];

  const logout = () => {
    clearOfficerSession();
    window.dispatchEvent(new Event('officer-session-expired'));
  };

  return (
    <div className="officer-app">
      <a className="officer-skip-link" href="#officer-main-content">Bỏ qua điều hướng</a>
      <div className="officer-app-shell">
        <aside className="officer-sidebar" aria-label="Khu vực điều hướng cán bộ">
          <a className="officer-sidebar-brand" href="/officer">
            <span className="brand-mark">AI</span>
            <span><strong>UBNDAI</strong><small>Cổng cán bộ</small></span>
          </a>
          <nav className="officer-nav" aria-label="Điều hướng cổng cán bộ">
            {links.map(({ to, label, icon: Icon, current }) => (
              <Link key={label} to={to} className={current ? 'active' : undefined} aria-current={current ? 'page' : undefined} aria-label={label}>
                <Icon size={20} weight={current ? 'fill' : 'regular'} aria-hidden="true" /><span>{label}</span>
              </Link>
            ))}
          </nav>
          <div className="officer-sidebar-footer">
            <ThemeSelector compact />
            <button className="officer-logout" type="button" onClick={logout}>
              <SignOut size={20} aria-hidden="true" /><span>Đăng xuất</span>
            </button>
          </div>
        </aside>
        <main className="officer-main" id="officer-main-content" tabIndex={-1}>
          {children ?? <Outlet />}
        </main>
      </div>
    </div>
  );
}

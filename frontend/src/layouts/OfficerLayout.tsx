import { Bell, ClipboardList, LayoutDashboard, LogOut } from 'lucide-react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { clearOfficerSession } from '../api';

const cautionStatus = 'CAUTION_REVIEW_REQUIRED';

export function OfficerLayout({ children }: { children?: ReactNode }) {
  const location = useLocation();
  const isApplicationList = location.pathname === '/officer/applications';
  const cautionSelected = isApplicationList && new URLSearchParams(location.search).get('status') === cautionStatus;
  const links = [
    { to: '/officer', label: 'Tổng quan', icon: LayoutDashboard, current: location.pathname === '/officer' || location.pathname === '/officer/' },
    { to: '/officer/applications', label: 'Hồ sơ', icon: ClipboardList, current: location.pathname.startsWith('/officer/applications') && !cautionSelected },
    { to: `/officer/applications?status=${cautionStatus}`, label: 'Cảnh báo', icon: Bell, current: cautionSelected },
  ];
  return (
    <div className="officer-app">
      <div className="officer-app-shell">
        <aside className="officer-sidebar" aria-label="Điều hướng cổng cán bộ">
          <a className="officer-sidebar-brand" href="/officer" aria-label="UBNDAI - Cổng cán bộ">
            <span className="brand-mark">AI</span>
            <span><strong>UBNDAI</strong><small>Cổng cán bộ</small></span>
          </a>
          <nav className="officer-nav">
            {links.map(({ to, label, icon: Icon, current }) => (
              <Link key={label} to={to} className={current ? 'active' : undefined} aria-current={current ? 'page' : undefined} aria-label={label}>
                <Icon aria-hidden="true" /><span>{label}</span>
              </Link>
            ))}
          </nav>
          <button className="officer-logout" onClick={() => { clearOfficerSession(); window.dispatchEvent(new Event('officer-session-expired')); }}><LogOut aria-hidden="true"/><span>Đăng xuất</span></button>
        </aside>
        <main className="officer-main">
          {children ?? <Outlet />}
        </main>
      </div>
    </div>
  );
}

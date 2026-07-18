import { Bell, ClipboardList, LayoutDashboard, LogOut } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import type { ReactNode } from 'react';
import { clearOfficerSession } from '../api';

const links = [
  { to: '/officer', label: 'Tổng quan', icon: LayoutDashboard },
  { to: '/officer/applications', label: 'Hồ sơ', icon: ClipboardList },
  { to: '/officer/applications?status=CAUTION_REVIEW_REQUIRED', label: 'Cảnh báo', icon: Bell },
];

export function OfficerLayout({ children }: { children?: ReactNode }) {
  return (
    <div className="officer-app">
      <div className="officer-app-shell">
        <aside className="officer-sidebar" aria-label="Điều hướng cổng cán bộ">
          <a className="officer-sidebar-brand" href="/officer" aria-label="UBNDAI - Cổng cán bộ">
            <span className="brand-mark">AI</span>
            <span><strong>UBNDAI</strong><small>Cổng cán bộ</small></span>
          </a>
          <nav className="officer-nav">
            {links.map(({ to, label, icon: Icon }) => (
              <NavLink key={label} to={to} className={({ isActive }) => isActive ? 'active' : undefined} aria-label={label}>
                <Icon aria-hidden="true" /><span>{label}</span>
              </NavLink>
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

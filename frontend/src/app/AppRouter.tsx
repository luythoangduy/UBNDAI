import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { api, setToken, token } from '../api';
import { needsOfficerAuthentication } from '../application-management-routing';
import { OfficerLayout } from '../layouts/OfficerLayout';
import { QueryProvider } from './QueryProvider';

const DashboardPage = lazy(() => import('../features/dashboard/DashboardPage'));
const ApplicationListPage = lazy(() => import('../features/applications/ApplicationListPage'));
const ApplicationDetailPage = lazy(() => import('../features/applications/ApplicationDetailPage'));

function OfficerLoginGate({ children }: { children: React.ReactNode }) {
  const [authenticated, setAuthenticated] = useState(() => !needsOfficerAuthentication(token()));
  const [username, setUsername] = useState('officer.demo');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { const expired = () => setAuthenticated(false); window.addEventListener('officer-session-expired', expired); return () => window.removeEventListener('officer-session-expired', expired); }, []);
  if (authenticated) return <>{children}</>;
  const login = async (event: React.FormEvent) => { event.preventDefault(); setBusy(true); setError(''); try { const result = await api<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }); setToken(result.access_token, 'officer'); setAuthenticated(true); } catch { setError('Tài khoản hoặc mật khẩu không đúng.'); } finally { setBusy(false); } };
  return <main className="management-login"><form onSubmit={login}><span className="brand-mark">AI</span><h1>Đăng nhập cổng cán bộ</h1><label>Tài khoản<input value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" /></label><label>Mật khẩu<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" /></label>{error && <p className="am-error" role="alert">{error}</p>}<button className="am-button" disabled={busy || password.length < 8}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button></form></main>;
}

export function ApplicationManagementRouter() {
  return <BrowserRouter><QueryProvider><OfficerLoginGate><Suspense fallback={<div className="am-route-loading" aria-live="polite">Đang tải trang…</div>}><Routes><Route element={<OfficerLayout />}><Route path="/officer" element={<DashboardPage />} /><Route path="/officer/applications" element={<ApplicationListPage />} /><Route path="/officer/applications/:applicationId" element={<ApplicationDetailPage />} /></Route><Route path="/officer/dashboard" element={<Navigate to="/officer" replace />} /><Route path="*" element={<Navigate to="/officer" replace />} /></Routes></Suspense></OfficerLoginGate></QueryProvider></BrowserRouter>;
}

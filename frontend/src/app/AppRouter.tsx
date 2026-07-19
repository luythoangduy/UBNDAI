import { lazy, Suspense, useEffect, useState } from 'react';
import { Buildings, LockKey, ShieldCheck } from '@phosphor-icons/react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { api, setToken, token } from '../api';
import { needsOfficerAuthentication } from '../application-management-routing';
import { OfficerLayout } from '../layouts/OfficerLayout';
import { QueryProvider } from './QueryProvider';
import { ThemeSelector } from '../components/ThemeSelector';

const DashboardPage = lazy(() => import('../features/dashboard/DashboardPage'));
const ApplicationListPage = lazy(() => import('../features/applications/ApplicationListPage'));
const ApplicationDetailPage = lazy(() => import('../features/applications/ApplicationDetailPage'));

export function OfficerLoginGate({ children }: { children: React.ReactNode }) {
  const [authenticated, setAuthenticated] = useState(() => !needsOfficerAuthentication(token()));
  const [username, setUsername] = useState('officer.demo');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { const expired = () => setAuthenticated(false); window.addEventListener('officer-session-expired', expired); return () => window.removeEventListener('officer-session-expired', expired); }, []);
  if (authenticated) return <>{children}</>;
  const login = async (event: React.FormEvent) => { event.preventDefault(); setBusy(true); setError(''); try { const result = await api<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }); setToken(result.access_token, 'officer'); setAuthenticated(true); } catch { setError('Tài khoản hoặc mật khẩu không đúng.'); } finally { setBusy(false); } };
  return <main className="management-login">
    <div className="management-login__theme"><ThemeSelector /></div>
    <section className="management-login__intro" aria-labelledby="officer-login-intro">
      <a className="management-login__brand" href="/citizen"><span className="brand-mark">AI</span><strong>UBNDAI</strong></a>
      <div><Buildings size={34} weight="duotone" aria-hidden="true"/><h2 id="officer-login-intro">Không gian xử lý hồ sơ tập trung</h2><p>Tra cứu, thẩm tra và theo dõi tiến độ trên một giao diện an toàn.</p></div>
      <p className="management-login__security"><ShieldCheck size={20} weight="fill" aria-hidden="true"/> Dữ liệu chỉ hiển thị cho cán bộ được phân quyền.</p>
    </section>
    <form onSubmit={login} aria-labelledby="officer-login-title">
      <div className="management-login__form-heading"><LockKey size={24} weight="duotone" aria-hidden="true"/><div><h1 id="officer-login-title">Đăng nhập cổng cán bộ</h1><p>Sử dụng tài khoản nghiệp vụ được cấp.</p></div></div>
      <label>Tài khoản<input required value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" /></label>
      <label>Mật khẩu<input required type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" aria-describedby={password.length > 0 && password.length < 8 ? 'officer-password-hint' : undefined} />{password.length > 0 && password.length < 8 && <small id="officer-password-hint" className="management-login__hint">Mật khẩu cần tối thiểu 8 ký tự.</small>}</label>
      {error && <p className="am-error" role="alert">{error}</p>}
      <button className="am-button management-login__submit" disabled={busy || password.length < 8}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
      {import.meta.env.VITE_SHOW_DEMO_CREDENTIALS === 'true' && <small className="demo-hint">Môi trường demo dùng mật khẩu <code>ChangeMe123!</code></small>}
    </form>
  </main>;
}

export function ApplicationManagementRouter() {
  return <BrowserRouter><QueryProvider><OfficerLoginGate><Suspense fallback={<div className="am-route-loading" aria-live="polite">Đang tải trang…</div>}><Routes><Route element={<OfficerLayout />}><Route path="/officer" element={<DashboardPage />} /><Route path="/officer/applications" element={<ApplicationListPage />} /><Route path="/officer/applications/:applicationId" element={<ApplicationDetailPage />} /></Route><Route path="/officer/dashboard" element={<Navigate to="/officer" replace />} /><Route path="*" element={<Navigate to="/officer" replace />} /></Routes></Suspense></OfficerLoginGate></QueryProvider></BrowserRouter>;
}

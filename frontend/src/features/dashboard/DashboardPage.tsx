import { lazy, Suspense, useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../../api';
const DashboardCharts = lazy(() => import('./DashboardCharts'));

type MetricItem = { name?: string; label?: string; status?: string; date?: string; count?: number; value?: number; total?: number; completed?: number };
const points = (value: unknown): MetricItem[] => Array.isArray(value) ? value : ((value as { items?: MetricItem[]; points?: MetricItem[] } | undefined)?.items ?? (value as { points?: MetricItem[] } | undefined)?.points ?? []);
const named = (value: unknown) => points(value).map(item => ({ name: item.name ?? item.label ?? item.status ?? 'Khác', value: item.value ?? item.count ?? item.total ?? 0 }));

export default function DashboardPage() {
  const [params, setParams] = useSearchParams();
  const from = params.get('from') ?? '', to = params.get('to') ?? '', granularity = params.get('granularity') ?? 'day';
  const query = useMemo(() => { const result = new URLSearchParams({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, granularity }); if (from) result.set('from', from); if (to) result.set('to', to); return result.toString(); }, [from, to, granularity]);
  const paths = ['summary', 'timeseries', 'status-distribution', 'application-types', 'anomalies'];
  const results = useQueries({ queries: paths.map(path => ({ queryKey: ['officer-dashboard', path, query], queryFn: () => api<unknown>(`/officer-dashboard/${path}?${query}`) })) });
  const summary = (results[0].data ?? {}) as Record<string, number>;
  const loading = results.some(result => result.isLoading), failed = results.some(result => result.error);
  const change = (key: string, value: string) => { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); setParams(next); };
  const kpis = [['Tổng hồ sơ', summary.total], ['Đã xử lý', summary.completed ?? summary.processed], ['Đang xử lý', summary.in_process ?? summary.in_review], ['Chưa xử lý', summary.unprocessed ?? summary.awaiting_review], ['Cần xem xét', summary.caution ?? summary.caution_review_required], ['Trả công dân', summary.returned ?? summary.needs_citizen_update]];
  return <><header className="officer-topbar"><div><h1>Tổng quan</h1><p>Thống kê tình hình xử lý hồ sơ</p></div><Link className="am-button" to="/officer/applications">Mở danh sách hồ sơ</Link></header><div className="officer-container"><div className="am-dashboard-filters"><label>Từ ngày<input type="date" value={from} onChange={event => change('from', event.target.value)} /></label><label>Đến ngày<input type="date" value={to} onChange={event => change('to', event.target.value)} /></label><label>Khoảng thời gian<select value={granularity} onChange={event => change('granularity', event.target.value)}><option value="day">Theo ngày</option><option value="week">Theo tuần</option><option value="month">Theo tháng</option></select></label></div>{loading ? <div className="am-loading" aria-live="polite">Đang tổng hợp dữ liệu…</div> : failed ? <div className="am-error" role="alert">Không thể tải đầy đủ dashboard. <button onClick={() => results.forEach(result => result.refetch())}>Thử lại</button></div> : <><section className="officer-kpi-grid am-six-kpis">{kpis.map(([label, value]) => <article className="officer-kpi" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></article>)}</section><Suspense fallback={<div className="am-loading">Đang tải biểu đồ…</div>}><DashboardCharts timeseries={points(results[1].data).map(item => ({ date: item.date ?? (item as MetricItem & { period?: string }).period ?? '', total: item.total ?? item.value ?? item.count ?? 0, completed: item.completed ?? 0 }))} statuses={named(results[2].data)} types={named(results[3].data)} anomalies={named(results[4].data)} /></Suspense></>}</div></>;
}

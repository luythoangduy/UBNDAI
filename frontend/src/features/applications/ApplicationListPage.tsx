import { useQuery } from '@tanstack/react-query';
import { FileMagnifyingGlass } from '@phosphor-icons/react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../../api';
import { applicationStatusLabels, serializeApplicationFilters, type ApplicationSummary, type ApplicationStatus } from '../../application-management-types';
import { readApplicationFilters, updateApplicationFilters } from './filters';

const statuses: Array<ApplicationStatus | ''> = ['', 'CAUTION_REVIEW_REQUIRED', 'READY_FOR_PROCESSING', 'IN_PROCESS', 'RETURNED_TO_CITIZEN', 'COMPLETED'];
const statusTone = (status: ApplicationStatus) => status === 'CAUTION_REVIEW_REQUIRED' ? 'warning' : status === 'COMPLETED' ? 'success' : status === 'RETURNED_TO_CITIZEN' ? 'danger' : 'info';
const unwrapItems = (value: unknown): { items: ApplicationSummary[]; total: number } => {
  if (Array.isArray(value)) return { items: value, total: value.length };
  const payload = value as { items?: ApplicationSummary[]; total?: number } | undefined;
  return { items: payload?.items ?? [], total: payload?.total ?? payload?.items?.length ?? 0 };
};

export default function ApplicationListPage() {
  const [params, setParams] = useSearchParams();
  const filters = readApplicationFilters(params);
  const query = serializeApplicationFilters(filters);
  const result = useQuery({ queryKey: ['applications', query], queryFn: () => api<unknown>(`/applications${query ? `?${query}` : ''}`) });
  const { items, total } = unwrapItems(result.data);
  const change = (key: string, value: string) => setParams(updateApplicationFilters(params, key, value));
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? 20;
  return <>
    <header className="officer-topbar"><div><h1>Hồ sơ</h1><p>Tìm kiếm, phân loại và xử lý hồ sơ trong một không gian thống nhất</p></div></header>
    <div className="officer-container"><section className="officer-page-card">
      <div className="am-toolbar" role="search">
        <label><span className="sr-only">Tìm hồ sơ</span><input aria-label="Tìm hồ sơ" placeholder="Mã hồ sơ, công dân, thủ tục…" value={filters.search} onChange={event => change('search', event.target.value)} /></label>
        <label><span className="sr-only">Trạng thái</span><select aria-label="Trạng thái" value={filters.status} onChange={event => change('status', event.target.value)}>{statuses.map(status => <option key={status || 'all'} value={status}>{status ? applicationStatusLabels[status] : 'Mọi trạng thái'}</option>)}</select></label>
        <label><span className="sr-only">Từ ngày</span><input aria-label="Từ ngày" type="date" value={filters.from} onChange={event => change('submitted_from', event.target.value)} /></label>
        <label><span className="sr-only">Đến ngày</span><input aria-label="Đến ngày" type="date" value={filters.to} onChange={event => change('submitted_to', event.target.value)} /></label>
      </div>
      {result.isLoading ? <div className="am-list-skeleton" aria-live="polite"><span className="sr-only">Đang tải hồ sơ…</span>{Array.from({ length: 5 }, (_, index) => <div className="am-skeleton" key={index}/>)}</div> : result.error ? <div className="am-error" role="alert">Không thể tải danh sách. <button onClick={() => result.refetch()}>Thử lại</button></div> : !items.length ? <div className="am-empty"><FileMagnifyingGlass size={34} weight="duotone" aria-hidden="true"/><h2>Không có hồ sơ phù hợp</h2><p>Thử bỏ bớt bộ lọc hoặc thay đổi từ khóa.</p></div> : <>
        <div className="officer-table-wrap"><table><caption className="sr-only">Danh sách {total} hồ sơ</caption><thead><tr><th scope="col">Mã hồ sơ</th><th scope="col">Công dân</th><th scope="col">Loại thủ tục</th><th scope="col">Cảnh báo</th><th scope="col">Trạng thái</th><th scope="col">Thao tác</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><Link to={`/officer/applications/${item.id}`}>{item.application_code}</Link></td><td>{item.citizen_name ?? 'Chưa cập nhật'}</td><td>{item.application_type_name}</td><td>{item.anomaly_count}</td><td><span className={`am-status am-status-${statusTone(item.status)}`}>{applicationStatusLabels[item.status] ?? item.status}</span></td><td><Link className="am-table-action" to={`/officer/applications/${item.id}`}>Xem đơn</Link></td></tr>)}</tbody></table></div>
        <div className="am-mobile-list">{items.map(item => <article className="am-mobile-card" key={item.id}><div><Link to={`/officer/applications/${item.id}`}><strong>{item.application_code}</strong></Link><span className={`am-status am-status-${statusTone(item.status)}`}>{applicationStatusLabels[item.status] ?? item.status}</span></div><span>{item.application_type_name}</span><span>{item.citizen_name ?? 'Chưa có tên'}</span><small>{item.anomaly_count} cảnh báo</small></article>)}</div>
        <nav className="am-pagination" aria-label="Phân trang"><button disabled={page <= 1} onClick={() => change('page', String(page - 1))}>Trang trước</button><span>Trang {page}<small>{total} hồ sơ</small></span><button disabled={page * pageSize >= total} onClick={() => change('page', String(page + 1))}>Trang sau</button></nav>
      </>}
    </section></div>
  </>;
}

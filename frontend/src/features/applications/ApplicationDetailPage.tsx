import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api';
import { applicationStatusLabels, type ApplicationDetail } from '../../application-management-types';
import type { CaseDetail } from '../../types';
import { ReviewWorkspace } from '../officer-review/ReviewWorkspace';

export default function ApplicationDetailPage() {
  const { applicationId = '' } = useParams();
  const [toast, setToast] = useState('');
  const management = useQuery({
    queryKey: ['application', applicationId],
    queryFn: () => api<ApplicationDetail>(`/applications/${applicationId}`),
  });
  const legacy = useQuery({
    queryKey: ['application-workspace', applicationId],
    queryFn: () => api<CaseDetail>(`/officer/cases/${applicationId}`),
  });

  if (management.isLoading || legacy.isLoading) {
    return <div className="officer-container am-loading" aria-live="polite">Đang tải không gian xử lý…</div>;
  }
  if (management.error || legacy.error || !management.data || !legacy.data) {
    return <div className="officer-container"><div className="am-error" role="alert">Không thể tải hồ sơ. <Link to="/officer/applications">Quay lại danh sách</Link></div></div>;
  }

  const app = management.data;
  return <>
    <header className="officer-topbar">
      <div><Link className="am-breadcrumb" to="/officer/applications">Hồ sơ</Link><h1>{app.application_code}</h1><p>{app.application_type_name}</p></div>
      <span className="am-status am-status-warning">{applicationStatusLabels[app.status] ?? app.status}</span>
    </header>
    <div className="officer-container am-detail-container am-legacy-embedded">
      <ReviewWorkspace
        detail={legacy.data}
        procedureName={app.application_type_name}
        onRefresh={async () => { await Promise.all([legacy.refetch(), management.refetch()]); }}
        onError={error => setToast(error instanceof Error ? error.message : 'Không thể tải lại hồ sơ.')}
      />
    </div>
    {toast && <div className="am-toast am-toast-error" role="alert">{toast}</div>}
  </>;
}

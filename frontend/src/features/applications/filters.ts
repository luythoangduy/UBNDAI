import type { ApplicationFilters, ApplicationStatus } from '../../application-management-types';
const positiveInt = (value: string | null, fallback: number) => { const number = Number(value); return Number.isInteger(number) && number > 0 ? number : fallback; };
export function readApplicationFilters(params: URLSearchParams): ApplicationFilters {
  return { search: params.get('search') ?? '', status: (params.get('status') ?? '') as ApplicationStatus | '', applicationType: params.get('application_type_code') ?? '', hasAnomaly: params.get('has_anomaly') === null ? '' : params.get('has_anomaly') === 'true', assignedOfficerId: params.get('assigned_officer_id') ?? '', from: params.get('submitted_from') ?? '', to: params.get('submitted_to') ?? '', page: positiveInt(params.get('page'), 1), pageSize: positiveInt(params.get('page_size'), 20), sortBy: params.get('sort_by') ?? 'submitted_at', sortOrder: params.get('sort_order') === 'asc' ? 'asc' : 'desc' };
}
export function updateApplicationFilters(current: URLSearchParams, key: string, value: string): URLSearchParams {
  const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); if (key !== 'page') next.delete('page'); return next;
}

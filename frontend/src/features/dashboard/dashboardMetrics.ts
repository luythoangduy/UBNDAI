import { applicationStatusLabels, type ApplicationStatus } from '../../application-management-types';

export type MetricItem = {
  key?: string;
  name?: string;
  label?: string;
  status?: string;
  date?: string;
  period?: string;
  count?: number;
  value?: number;
  total?: number;
  completed?: number;
};

export type NamedMetric = { key: string; name: string; value: number };

export const metricPoints = (value: unknown): MetricItem[] => {
  if (Array.isArray(value)) return value;
  const payload = value as { items?: MetricItem[]; points?: MetricItem[] } | undefined;
  return payload?.items ?? payload?.points ?? [];
};

const metricKey = (item: MetricItem) => item.key ?? item.name ?? item.label ?? item.status ?? 'UNKNOWN';
const metricValue = (item: MetricItem) => item.value ?? item.count ?? item.total ?? 0;
const isApplicationStatus = (value: string): value is ApplicationStatus => value in applicationStatusLabels;
const readableKey = (value: string) => {
  const words = value.toLocaleLowerCase('vi-VN').replace(/_/g, ' ').trim();
  return words ? words[0].toLocaleUpperCase('vi-VN') + words.slice(1) : 'Khác';
};

export const normalizeNamedMetrics = (value: unknown): NamedMetric[] => metricPoints(value).map(item => {
  const key = metricKey(item);
  return { key, name: readableKey(key), value: metricValue(item) };
});

export const normalizeStatusMetrics = (value: unknown): NamedMetric[] => metricPoints(value).map(item => {
  const key = metricKey(item);
  return { key, name: isApplicationStatus(key) ? applicationStatusLabels[key] : readableKey(key), value: metricValue(item) };
});

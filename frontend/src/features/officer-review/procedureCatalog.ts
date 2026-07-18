import type { ProcedureSummary } from '../../types';

export const procedureNames: Record<string, string> = {};

export function rememberProcedureNames(items: ProcedureSummary[]) {
  items.forEach(item => { procedureNames[item.id] = item.name; });
}

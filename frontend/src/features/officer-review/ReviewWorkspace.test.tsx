import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CaseDetail } from '../../types';
import { ReviewWorkspace } from './ReviewWorkspace';

afterEach(cleanup);

vi.mock('../../api', () => ({
  api: vi.fn(async () => []),
  apiBlob: vi.fn(async () => new Blob(['preview'], { type: 'image/svg+xml' })),
}));

const detail: CaseDetail = {
  case: {
    id: 'case-1',
    case_code: 'UBNDAI-2026-000001',
    status: 'in_officer_review',
    procedure_id: 'khai_sinh',
    version: 1,
  },
  submission: {
    id: 'submission-1',
    version: 1,
    form_data: { child_name: 'Nguyễn Minh An' },
    checklist_snapshot: {},
    procedure_rule_version: '2026.1',
    created_at: '2026-07-18T00:00:00Z',
  },
  documents: [{
    id: 'document-1',
    original_filename: 'giay-chung-sinh.svg',
    document_type: 'birth_certificate',
    content_type: 'image/svg+xml',
    size_bytes: 1024,
    ocr_status: 'completed',
  }],
  findings: [],
  timeline: [],
};

describe('ReviewWorkspace', () => {
  it('preserves the legacy three-panel review workspace', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:preview');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    render(<ReviewWorkspace detail={detail} onRefresh={vi.fn()} onError={vi.fn()} />);

    expect(screen.getByText('UBNDAI-2026-000001')).toBeInTheDocument();
    expect(screen.getByText('Nguyễn Minh An')).toBeInTheDocument();
    expect(document.querySelectorAll('.review-columns > .review-panel')).toHaveLength(3);
    await waitFor(() => expect(screen.getByAltText('giay-chung-sinh.svg')).toBeInTheDocument());
  });

  it('names each review region and exposes the process progress', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:preview');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    render(<ReviewWorkspace detail={detail} onRefresh={vi.fn()} onError={vi.fn()} />);

    expect(screen.getByRole('region', { name: 'Tài liệu và căn cứ' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Dữ liệu có cấu trúc' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Kết quả kiểm tra' })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Tiến trình xử lý hồ sơ' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByAltText('giay-chung-sinh.svg')).toBeInTheDocument());
  });
});

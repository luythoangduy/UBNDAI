import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DecisionDialog } from './DecisionDialog';

afterEach(cleanup);

describe('DecisionDialog', () => {
  it('closes on Escape and disables an invalid submission', () => {
    const close = vi.fn();
    render(<DecisionDialog title="Tiếp tục xử lý" note="" setNote={() => undefined} busy={false} valid={false} onClose={close} onConfirm={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Xác nhận' })).toBeDisabled();
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(close).toHaveBeenCalledOnce();
  });

  it('exposes the required note, error message, and busy state accessibly', () => {
    render(<DecisionDialog title="Tiếp tục xử lý" note="Ghi chú" setNote={() => undefined} busy valid error="Không thể lưu" onClose={() => undefined} onConfirm={() => undefined} />);

    expect(screen.getByRole('textbox', { name: /Ghi chú bắt buộc/i })).toBeRequired();
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('Không thể lưu');
    expect(screen.getByRole('button', { name: 'Hủy' })).toBeDisabled();
  });
});

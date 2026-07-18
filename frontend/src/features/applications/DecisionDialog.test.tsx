import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DecisionDialog } from './DecisionDialog';

describe('DecisionDialog', () => {
  it('closes on Escape and disables an invalid submission', () => {
    const close = vi.fn();
    render(<DecisionDialog title="Tiếp tục xử lý" note="" setNote={() => undefined} busy={false} valid={false} onClose={close} onConfirm={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Xác nhận' })).toBeDisabled();
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(close).toHaveBeenCalledOnce();
  });
});

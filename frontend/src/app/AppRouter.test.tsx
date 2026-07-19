import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { OfficerLoginGate } from './AppRouter';

vi.mock('../components/ThemeSelector', () => ({ ThemeSelector: () => <button>Giao diện: Theo hệ thống</button> }));

afterEach(cleanup);

describe('OfficerLoginGate', () => {
  beforeEach(() => localStorage.clear());

  it('shows a readable login action after credentials are entered', () => {
    render(<OfficerLoginGate><div>Officer content</div></OfficerLoginGate>);

    const password = screen.getByLabelText('Mật khẩu');
    fireEvent.change(password, { target: { value: 'valid-password' } });

    const button = screen.getByRole('button', { name: 'Đăng nhập' });
    expect(button).toBeVisible();
    expect(button).toBeEnabled();
    expect(button).toHaveClass('management-login__submit');
  });
});

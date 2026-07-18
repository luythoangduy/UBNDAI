import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { OfficerLoginGate } from './AppRouter';

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

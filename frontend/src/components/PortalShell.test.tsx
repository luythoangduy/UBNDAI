import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { PortalShell } from './PortalShell';

afterEach(cleanup);

describe('PortalShell', () => {
  it('provides skip navigation and marks the current citizen destination', () => {
    render(<PortalShell role="citizen" path="/citizen"><main>Nội dung</main></PortalShell>);

    expect(screen.getByRole('link', { name: 'Bỏ qua điều hướng' })).toHaveAttribute('href', '#main-content');
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content');
    expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('link', { name: 'Dành cho công dân' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Trợ lý AI' })).not.toHaveAttribute('aria-current');
  });

  it('exposes an accessible mobile navigation control', () => {
    render(<PortalShell role="citizen" path="/chat"><div id="main-content">Nội dung</div></PortalShell>);

    const menu = screen.getByRole('button', { name: 'Mở điều hướng' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(menu);
    expect(screen.getByRole('button', { name: 'Đóng điều hướng' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('navigation', { name: 'Điều hướng chính' })).toHaveClass('open');
  });

  it('renders the shared theme control in the application header', () => {
    render(<PortalShell role="officer" path="/officer/review/demo" themeControl={<button>Giao diện</button>}><div id="main-content">Nội dung</div></PortalShell>);

    expect(screen.getByRole('button', { name: 'Giao diện' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Cổng cán bộ' })).toHaveAttribute('aria-current', 'page');
  });
});

import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OfficerLayout } from './OfficerLayout';

vi.mock('../components/ThemeSelector', () => ({ ThemeSelector: () => <button>Giao diện: Theo hệ thống</button> }));

afterEach(cleanup);

describe('OfficerLayout navigation', () => {
  it('offers a skip link, a named navigation landmark, and theme controls', () => {
    render(
      <MemoryRouter initialEntries={['/officer']}>
        <OfficerLayout><div>Dashboard</div></OfficerLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Bỏ qua điều hướng' })).toHaveAttribute('href', '#officer-main-content');
    expect(screen.getByRole('navigation', { name: 'Điều hướng cổng cán bộ' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /giao diện/i })).toBeInTheDocument();
    expect(screen.getByRole('main')).toHaveAttribute('id', 'officer-main-content');
  });

  it('marks only Hồ sơ as current on the applications list', () => {
    render(
      <MemoryRouter initialEntries={['/officer/applications']}>
        <OfficerLayout><div>Applications</div></OfficerLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Hồ sơ' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Tổng quan' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('link', { name: 'Cảnh báo' })).not.toHaveAttribute('aria-current');
  });

  it('marks only Cảnh báo as current when its status filter is selected', () => {
    render(
      <MemoryRouter initialEntries={['/officer/applications?status=CAUTION_REVIEW_REQUIRED']}>
        <OfficerLayout><div>Warnings</div></OfficerLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Cảnh báo' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Hồ sơ' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('link', { name: 'Tổng quan' })).not.toHaveAttribute('aria-current');
  });

  it('keeps Hồ sơ current on a detail route even when a status query is present', () => {
    render(
      <MemoryRouter initialEntries={['/officer/applications/application-1?status=CAUTION_REVIEW_REQUIRED']}>
        <OfficerLayout><div>Application detail</div></OfficerLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Hồ sơ' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Cảnh báo' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('link', { name: 'Tổng quan' })).not.toHaveAttribute('aria-current');
  });
});

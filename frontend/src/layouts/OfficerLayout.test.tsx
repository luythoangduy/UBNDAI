import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { OfficerLayout } from './OfficerLayout';

afterEach(cleanup);

describe('OfficerLayout navigation', () => {
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

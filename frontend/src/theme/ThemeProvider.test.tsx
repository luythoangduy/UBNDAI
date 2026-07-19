import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeSelector } from '../components/ThemeSelector';
import { THEME_STORAGE_KEY, ThemeProvider, useTheme } from './ThemeProvider';

type Listener = (event: MediaQueryListEvent) => void;

function installMatchMedia(initialDark = false) {
  let matches = initialDark;
  const listeners = new Set<Listener>();
  const media = {
    get matches() { return matches; },
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addEventListener: vi.fn((_type: string, listener: Listener) => listeners.add(listener)),
    removeEventListener: vi.fn((_type: string, listener: Listener) => listeners.delete(listener)),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  } as unknown as MediaQueryList;

  vi.stubGlobal('matchMedia', vi.fn(() => media));
  return {
    media,
    setDark(next: boolean) {
      matches = next;
      listeners.forEach(listener => listener({ matches: next } as MediaQueryListEvent));
    },
  };
}

function ThemeState() {
  const { preference, resolvedTheme } = useTheme();
  return <output>{preference}:{resolvedTheme}</output>;
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.style.colorScheme = '';
  document.head.querySelector('meta[name="theme-color"]')?.remove();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('ThemeProvider', () => {
  it('defaults to system and reflects the current OS theme', () => {
    installMatchMedia(true);
    render(<ThemeProvider><ThemeState /></ThemeProvider>);

    expect(screen.getByText('system:dark')).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
    expect(document.querySelector('meta[name="theme-color"]')).toHaveAttribute('content', '#0b1628');
  });

  it('persists an explicit preference and updates the document', async () => {
    installMatchMedia(false);
    const user = userEvent.setup();
    render(<ThemeProvider><ThemeSelector /><ThemeState /></ThemeProvider>);

    await user.click(screen.getByRole('button', { name: /Giao diện/i }));
    await user.click(screen.getByRole('menuitemradio', { name: 'Tối' }));

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    expect(screen.getByText('dark:dark')).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });

  it('ignores invalid persisted values', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'sepia');
    installMatchMedia(false);
    render(<ThemeProvider><ThemeState /></ThemeProvider>);

    expect(screen.getByText('system:light')).toBeInTheDocument();
  });

  it('tracks OS changes only while preference is system', async () => {
    const matchMedia = installMatchMedia(false);
    const user = userEvent.setup();
    render(<ThemeProvider><ThemeSelector /><ThemeState /></ThemeProvider>);

    matchMedia.setDark(true);
    await waitFor(() => expect(screen.getByText('system:dark')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /Giao diện/i }));
    await user.click(screen.getByRole('menuitemradio', { name: 'Sáng' }));
    matchMedia.setDark(false);
    expect(screen.getByText('light:light')).toBeInTheDocument();
  });

  it('synchronizes a valid preference changed in another tab', async () => {
    installMatchMedia(false);
    render(<ThemeProvider><ThemeState /></ThemeProvider>);

    window.dispatchEvent(new StorageEvent('storage', { key: THEME_STORAGE_KEY, newValue: 'dark' }));

    await waitFor(() => expect(screen.getByText('dark:dark')).toBeInTheDocument());
  });
});

describe('ThemeSelector', () => {
  it('offers Light, Dark and System choices with an accessible label', async () => {
    installMatchMedia(false);
    const user = userEvent.setup();
    render(<ThemeProvider><ThemeSelector /></ThemeProvider>);

    const selector = screen.getByRole('button', { name: 'Giao diện: Theo hệ thống' });
    expect(selector).toHaveAttribute('aria-haspopup', 'menu');
    expect(selector).toHaveAttribute('aria-expanded', 'false');

    await user.click(selector);
    expect(screen.getByRole('menuitemradio', { name: 'Theo hệ thống' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('menuitemradio', { name: 'Sáng' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: 'Tối' })).toBeInTheDocument();
  });

  it('supports arrow-key navigation and returns focus on Escape', async () => {
    installMatchMedia(false);
    const user = userEvent.setup();
    render(<ThemeProvider><ThemeSelector /></ThemeProvider>);

    const selector = screen.getByRole('button', { name: 'Giao diện: Theo hệ thống' });
    selector.focus();
    await user.keyboard('{ArrowDown}');

    const systemOption = screen.getByRole('menuitemradio', { name: 'Theo hệ thống' });
    const lightOption = screen.getByRole('menuitemradio', { name: 'Sáng' });
    await waitFor(() => expect(systemOption).toHaveFocus());
    await user.keyboard('{ArrowDown}');
    expect(lightOption).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(selector).toHaveFocus();
    expect(selector).toHaveAttribute('aria-expanded', 'false');
  });
});

import { Desktop, Moon, Sun } from '@phosphor-icons/react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { useTheme } from '../theme/ThemeProvider';
import type { ThemePreference } from '../theme/types';

const OPTIONS: ReadonlyArray<{
  value: ThemePreference;
  label: string;
  icon: typeof Sun;
}> = [
  { value: 'system', label: 'Theo hệ thống', icon: Desktop },
  { value: 'light', label: 'Sáng', icon: Sun },
  { value: 'dark', label: 'Tối', icon: Moon },
];

export interface ThemeSelectorProps {
  className?: string;
  compact?: boolean;
}

export function ThemeSelector({ className = '', compact = false }: ThemeSelectorProps) {
  const { preference, resolvedTheme, setPreference } = useTheme();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const activeOption = OPTIONS.find(option => option.value === preference) ?? OPTIONS[0];
  const TriggerIcon = resolvedTheme === 'dark' ? Moon : Sun;

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutsideClick);
    return () => document.removeEventListener('pointerdown', closeOnOutsideClick);
  }, [open]);

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      requestAnimationFrame(() => containerRef.current?.querySelector<HTMLButtonElement>('[role="menuitemradio"]')?.focus());
    }
  };

  const handleMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'));
    const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      items[(currentIndex + direction + items.length) % items.length]?.focus();
    }
  };

  return (
    <div ref={containerRef} className={`theme-selector ${className}`.trim()}>
      <button
        ref={triggerRef}
        type="button"
        className="theme-selector__trigger"
        aria-label={`Giao diện: ${activeOption.label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen(current => !current)}
        onKeyDown={handleTriggerKeyDown}
      >
        <TriggerIcon aria-hidden="true" size={20} weight="regular" />
        {!compact && <span>{activeOption.label}</span>}
      </button>
      {open && (
        <div id={menuId} className="theme-selector__menu" role="menu" aria-label="Chọn giao diện" onKeyDown={handleMenuKeyDown}>
          {OPTIONS.map(option => {
            const OptionIcon = option.icon;
            return (
              <button
                type="button"
                role="menuitemradio"
                aria-checked={preference === option.value}
                key={option.value}
                onClick={() => {
                  setPreference(option.value);
                  setOpen(false);
                  requestAnimationFrame(() => triggerRef.current?.focus());
                }}
              >
                <OptionIcon aria-hidden="true" size={19} weight="regular" />
                <span>{option.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

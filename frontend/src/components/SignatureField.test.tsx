import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { SignatureField } from './SignatureField';

describe('SignatureField', () => {
  it('opens the drawing popup and closes it with Escape', async () => {
    const user = userEvent.setup();
    render(<SignatureField value="" onChange={vi.fn()} signerName="" onSignerNameChange={vi.fn()}/>);

    await user.click(screen.getByRole('button', { name: /bấm để ký trực tiếp/i }));
    expect(screen.getByRole('dialog', { name: /vẽ chữ ký/i })).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows an existing signature with replace and remove controls', () => {
    const onChange = vi.fn();
    render(<SignatureField value="data:image/png;base64,abc" onChange={onChange} signerName="Nguyễn Văn An" onSignerNameChange={vi.fn()}/>);

    expect(screen.getByRole('img', { name: /chữ ký người khai/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ký lại/i })).toBeInTheDocument();
    screen.getByRole('button', { name: /xóa chữ ký/i }).click();
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('lets the signer type their full name with the keyboard', async () => {
    const user = userEvent.setup();
    function ControlledField() {
      const [name, setName] = useState('');
      return <SignatureField value="" onChange={vi.fn()} signerName={name} onSignerNameChange={setName}/>;
    }
    const view = render(<ControlledField/>);

    const input = within(view.container).getByRole('textbox', { name: /họ và tên người ký/i });
    await user.type(input, 'Nguyễn Văn An');
    expect(input).toHaveValue('Nguyễn Văn An');
  });
});

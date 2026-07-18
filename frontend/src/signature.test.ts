import { describe, expect, it } from 'vitest';
import { composeSignedDocumentHtml, isSignatureImage } from './signature';

describe('document signature helpers', () => {
  it('adds a signature placeholder to every unsigned document', () => {
    const html = composeSignedDocumentHtml('<p>Nội dung</p>', '', '', new Date('2026-07-18T00:00:00Z'));
    expect(html).toContain('NGƯỜI KÝ');
    expect(html).toContain('[Chưa ký]');
    expect(html).toContain('[Chưa nhập họ tên]');
    expect(html).toContain('18/07/2026');
  });

  it('embeds a PNG signature when the citizen has signed', () => {
    const signature = 'data:image/png;base64,c2lnbmF0dXJl';
    const html = composeSignedDocumentHtml('<p>Nội dung</p>', signature, 'Nguyễn Văn An', new Date('2026-07-18T00:00:00Z'));
    expect(isSignatureImage(signature)).toBe(true);
    expect(html).toContain(`<img src="${signature}"`);
    expect(html).toContain('<strong>Nguyễn Văn An</strong>');
    expect(html).not.toContain('[Chưa ký]');
  });

  it('escapes the typed signer name before export', () => {
    const html = composeSignedDocumentHtml('<p>Nội dung</p>', '', 'Nguyễn <An> & Co.');
    expect(html).toContain('Nguyễn &lt;An&gt; &amp; Co.');
    expect(html).not.toContain('Nguyễn <An>');
  });
});

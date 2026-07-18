const SIGNATURE_IMAGE_PREFIX = 'data:image/png;base64,';

export function isSignatureImage(value: string): boolean {
  return value.startsWith(SIGNATURE_IMAGE_PREFIX) && value.length > SIGNATURE_IMAGE_PREFIX.length;
}

function escapeAttribute(value: string): string {
  return escapeHtml(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export function composeSignedDocumentHtml(
  html: string,
  signature: string,
  signerName = '',
  signedOn = new Date(),
): string {
  const date = new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(signedOn);
  const signatureContent = isSignatureImage(signature)
    ? `<img src="${escapeAttribute(signature)}" alt="Chữ ký người khai"/>`
    : '<em>[Chưa ký]</em>';
  const signerNameContent = signerName.trim()
    ? `<strong>${escapeHtml(signerName.trim())}</strong>`
    : '<em>[Chưa nhập họ tên]</em>';

  return `${html}
<p style="text-align: right">Ngày ký: ${date}</p>
<p style="text-align: right"><strong>NGƯỜI KÝ</strong><br/><em>(Ký và ghi rõ họ tên)</em></p>
<p style="text-align: right">${signatureContent}</p>
<p style="text-align: right">${signerNameContent}</p>`;
}

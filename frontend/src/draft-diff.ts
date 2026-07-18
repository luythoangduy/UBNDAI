export type DiffBlock = { type: 'same' | 'added' | 'removed'; html: string };

const BLOCK_RE = /<(p|h[1-6]|ul|ol|table|blockquote|pre)\b[^>]*>[\s\S]*?<\/\1>/gi;

export function splitBlocks(html: string): string[] {
  const blocks = html.match(BLOCK_RE);
  if (blocks?.length) return blocks.map(block => block.trim());
  return html.trim() ? [html.trim()] : [];
}

export function diffDraftBlocks(oldHtml: string, newHtml: string): DiffBlock[] {
  const oldBlocks = splitBlocks(oldHtml);
  const newBlocks = splitBlocks(newHtml);
  const normalize = (value: string) => value.replace(/\s+/g, ' ').trim();
  const oldNormalized = oldBlocks.map(normalize);
  const newNormalized = newBlocks.map(normalize);
  const table = Array.from({ length: oldBlocks.length + 1 }, () => Array(newBlocks.length + 1).fill(0));

  for (let oldIndex = oldBlocks.length - 1; oldIndex >= 0; oldIndex -= 1) {
    for (let newIndex = newBlocks.length - 1; newIndex >= 0; newIndex -= 1) {
      table[oldIndex][newIndex] = oldNormalized[oldIndex] === newNormalized[newIndex]
        ? table[oldIndex + 1][newIndex + 1] + 1
        : Math.max(table[oldIndex + 1][newIndex], table[oldIndex][newIndex + 1]);
    }
  }

  const result: DiffBlock[] = [];
  let oldIndex = 0;
  let newIndex = 0;
  while (oldIndex < oldBlocks.length && newIndex < newBlocks.length) {
    if (oldNormalized[oldIndex] === newNormalized[newIndex]) {
      result.push({ type: 'same', html: newBlocks[newIndex] }); oldIndex += 1; newIndex += 1;
    } else if (table[oldIndex + 1][newIndex] >= table[oldIndex][newIndex + 1]) {
      result.push({ type: 'removed', html: oldBlocks[oldIndex] }); oldIndex += 1;
    } else {
      result.push({ type: 'added', html: newBlocks[newIndex] }); newIndex += 1;
    }
  }
  while (oldIndex < oldBlocks.length) result.push({ type: 'removed', html: oldBlocks[oldIndex++] });
  while (newIndex < newBlocks.length) result.push({ type: 'added', html: newBlocks[newIndex++] });
  return result;
}

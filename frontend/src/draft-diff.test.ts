import { describe, expect, it } from 'vitest';
import { diffDraftBlocks } from './draft-diff';

describe('diffDraftBlocks', () => {
  it('marks replaced blocks as removed and added', () => {
    expect(diffDraftBlocks('<h1>A</h1><p>Cũ</p>', '<h1>A</h1><p>Mới</p>')).toEqual([
      { type: 'same', html: '<h1>A</h1>' },
      { type: 'removed', html: '<p>Cũ</p>' },
      { type: 'added', html: '<p>Mới</p>' },
    ]);
  });
});

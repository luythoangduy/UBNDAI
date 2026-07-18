import { describe, expect, it } from 'vitest';
import { draftValuesFromCase, validateClarifyingAnswers } from './citizen-form';
import type { ClarifyingQuestion } from './types';

const questions: ClarifyingQuestion[] = [
  { key: 'ket_hon', text: 'Đã kết hôn?', answer_type: 'boolean', options: [] },
  { key: 'so_ngay', text: 'Bao nhiêu ngày?', answer_type: 'integer', options: [], minimum: 0, maximum: 30 },
  { key: 'kenh_nop', text: 'Kênh nộp?', answer_type: 'choice', options: ['Trực tuyến', 'Trực tiếp'] },
];

describe('validateClarifyingAnswers', () => {
  it('accepts valid non-default branch values', () => {
    expect(validateClarifyingAnswers(questions, {
      ket_hon: false,
      so_ngay: 30,
      kenh_nop: 'Trực tiếp',
    })).toEqual({});
  });

  it('rejects missing, out-of-range and unknown choice values', () => {
    expect(validateClarifyingAnswers(questions, {
      ket_hon: '',
      so_ngay: 31,
      kenh_nop: 'Bưu điện',
    })).toEqual({
      ket_hon: 'Vui lòng trả lời câu hỏi này.',
      so_ngay: 'Giá trị lớn nhất là 30.',
      kenh_nop: 'Vui lòng chọn một giá trị trong danh sách.',
    });
  });
});

describe('draftValuesFromCase', () => {
  it('keeps only fields belonging to the selected template', () => {
    expect(draftValuesFromCase(
      [{ key: 'ho_ten' }, { key: 'nam_sinh' }, { key: 'dong_y' }],
      { ho_ten: 'Nguyễn Văn A', nam_sinh: 1990, dong_y: false, _answers: { ket_hon: true }, locality_code: '01' },
    )).toEqual({ ho_ten: 'Nguyễn Văn A', nam_sinh: '1990', dong_y: 'false' });
  });
});

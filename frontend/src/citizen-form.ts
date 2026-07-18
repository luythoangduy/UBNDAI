import type { ClarifyingQuestion } from './types';

export type ClarifyingAnswer = string | number | boolean;
export type ClarifyingAnswers = Record<string, ClarifyingAnswer>;

export function isMissingAnswer(value: ClarifyingAnswer | undefined): boolean {
  return value === undefined || (typeof value === 'string' && value.trim() === '');
}

export function validateClarifyingAnswers(
  questions: ClarifyingQuestion[],
  answers: ClarifyingAnswers,
): Record<string, string> {
  const errors: Record<string, string> = {};

  for (const question of questions) {
    const value = answers[question.key];
    if (isMissingAnswer(value)) {
      errors[question.key] = 'Vui lòng trả lời câu hỏi này.';
      continue;
    }

    if (question.answer_type === 'boolean' && typeof value !== 'boolean') {
      errors[question.key] = 'Vui lòng chọn Có hoặc Không.';
    } else if (question.answer_type === 'integer') {
      if (typeof value !== 'number' || !Number.isInteger(value)) {
        errors[question.key] = 'Vui lòng nhập một số nguyên.';
      } else if (question.minimum != null && value < question.minimum) {
        errors[question.key] = `Giá trị nhỏ nhất là ${question.minimum}.`;
      } else if (question.maximum != null && value > question.maximum) {
        errors[question.key] = `Giá trị lớn nhất là ${question.maximum}.`;
      }
    } else if (
      question.answer_type === 'choice'
      && !(question.options ?? []).includes(String(value))
    ) {
      errors[question.key] = 'Vui lòng chọn một giá trị trong danh sách.';
    }
  }

  return errors;
}

export function draftValuesFromCase(
  fields: Array<{ key: string }>,
  formData: Record<string, unknown> | undefined,
): Record<string, string> {
  if (!formData) return {};

  return Object.fromEntries(fields.flatMap(field => {
    const value = formData[field.key];
    if (typeof value === 'string') return [[field.key, value]];
    if (typeof value === 'number' || typeof value === 'boolean') {
      return [[field.key, String(value)]];
    }
    return [];
  }));
}

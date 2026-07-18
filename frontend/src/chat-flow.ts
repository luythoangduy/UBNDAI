import type { ChatExperience, ChatHistoryResponse, ChatResponse } from './types';

export type ChatMessage = {
  id?: string | number;
  role: 'user' | 'assistant';
  text: string;
  response?: ChatExperience & Partial<ChatResponse>;
};

export type ClarificationControl = 'boolean' | 'number' | 'date' | 'text';

export function clarificationControlFor(question: string): ClarificationControl {
  const normalized = question.toLocaleLowerCase('vi');
  if (/\b(bao nhiêu|mấy ngày|số ngày|bao lâu|tuổi)\b/u.test(normalized)) return 'number';
  if (/\b(ngày nào|ngày sinh|ngày dự sinh|thời điểm)\b/u.test(normalized)) return 'date';
  if (/\b(có|không|đã|chưa|phải|còn|tại việt nam)\b/u.test(normalized)) return 'boolean';
  return 'text';
}

export function messagesFromHistory(history: ChatHistoryResponse): ChatMessage[] {
  return history.messages
    .filter(item => item.role === 'user' || item.role === 'assistant')
    .map(item => ({ id: item.id, role: item.role, text: item.content, ...(item.response ? { response: item.response } : {}) }));
}

export function latestInteractiveMessageIndex(messages: ChatMessage[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'assistant' && messages[index].response) return index;
  }
  return -1;
}

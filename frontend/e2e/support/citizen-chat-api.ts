import { expect, type Page, type Route } from '@playwright/test';

const procedureId = 'birth-registration';
const oldCaseId = 'case-old-001';
const chatCaseId = 'case-chat-001';

const oldCase = {
  id: oldCaseId,
  case_code: 'UBNDAI-2026-000001',
  status: 'draft',
  procedure_id: procedureId,
  form_data: {},
  version: 1,
  created_at: '2026-07-17T08:00:00Z',
  updated_at: '2026-07-17T08:00:00Z',
};

const chatCase = {
  id: chatCaseId,
  case_code: 'UBNDAI-2026-000002',
  status: 'draft',
  procedure_id: procedureId,
  form_data: { noi_sinh_trong_nuoc: true },
  checklist: {
    items: [
      { code: 'GIAY_CHUNG_SINH', name: 'Giấy chứng sinh', required: true },
      { code: 'GIAY_TO_CHA_ME', name: 'Giấy tờ tùy thân của cha hoặc mẹ', required: true },
    ],
  },
  version: 2,
  created_at: '2026-07-18T08:00:00Z',
  updated_at: '2026-07-18T08:02:00Z',
};

export type CitizenChatApiState = {
  chatRequests: Array<Record<string, unknown>>;
  createCaseRequests: Array<Record<string, unknown>>;
};

function json(route: Route, data: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
}

export async function mockCitizenChatApi(page: Page): Promise<CitizenChatApiState> {
  const state: CitizenChatApiState = { chatRequests: [], createCaseRequests: [] };

  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    const body = request.postDataJSON?.() as Record<string, unknown> | null;

    if (pathname === '/api/v1/auth/login' && method === 'POST') {
      expect(body).toMatchObject({ username: 'citizen.demo', password: 'ChangeMe123!' });
      return json(route, { access_token: 'citizen-e2e-token' });
    }

    if (pathname !== '/api/v1/auth/login') {
      expect(request.headers().authorization).toBe('Bearer citizen-e2e-token');
    }

    if (pathname === '/api/v1/citizen/cases' && method === 'GET') {
      return json(route, state.chatRequests.length ? [chatCase, oldCase] : [oldCase]);
    }
    if (pathname === `/api/v1/citizen/cases/${oldCaseId}` && method === 'GET') {
      return json(route, { case: oldCase });
    }
    if (pathname === `/api/v1/citizen/cases/${chatCaseId}` && method === 'GET') {
      return json(route, { case: chatCase });
    }
    if (pathname === `/api/v1/chat/${oldCaseId}/messages` && method === 'GET') {
      return json(route, {
        case_id: oldCaseId,
        procedure_id: procedureId,
        status: 'draft',
        messages: [
          { id: 'old-message-1', role: 'user', content: 'Tôi cần xem lại hồ sơ khai sinh cũ.', created_at: '2026-07-17T08:00:00Z' },
          { id: 'old-message-2', role: 'assistant', content: 'Đây là cuộc trò chuyện khai sinh trước đó.', created_at: '2026-07-17T08:00:01Z' },
        ],
      });
    }
    if (pathname === '/api/v1/citizen/cases' && method === 'POST') {
      state.createCaseRequests.push(body ?? {});
      return json(route, { ...chatCase, id: 'case-duplicate-should-not-exist' }, 201);
    }
    if (pathname === '/api/v1/procedures' && method === 'GET') {
      return json(route, [{
        id: procedureId,
        national_code: '1.000894',
        name: 'Đăng ký khai sinh',
        agency: 'Ủy ban nhân dân cấp xã',
        locality_code: 'national',
        status: 'published',
        source_url: 'https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-hanh-chinh.html',
      }]);
    }
    if (pathname === '/api/v1/chat/starter' && method === 'GET') {
      return json(route, {
        reply: 'Xin chào! Hãy mô tả thủ tục bạn cần hỗ trợ.',
        actions: [],
        templates: [],
        evidence: [],
      });
    }
    if (pathname === '/api/v1/chat' && method === 'POST') {
      state.chatRequests.push(body ?? {});
      if (state.chatRequests.length === 1) {
        return json(route, {
          case_id: chatCaseId,
          reply: 'Tôi đã xác định thủ tục phù hợp là Đăng ký khai sinh.',
          kind: 'clarify',
          procedure_id: procedureId,
          clarifying_questions: ['Trẻ sinh tại Việt Nam?'],
          citations: [],
          actions: [],
        });
      }
      return json(route, {
        case_id: chatCaseId,
        reply: 'Checklist cá nhân hóa đã sẵn sàng: 2 giấy tờ cần chuẩn bị.',
        kind: 'checklist',
        procedure_id: procedureId,
        clarifying_questions: [],
        citations: [{
          index: 1,
          section: 'Thành phần hồ sơ đăng ký khai sinh',
          source_url: 'https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-hanh-chinh.html',
        }],
        evidence: [{
          id: 'official-catalog',
          label: 'Cổng Dịch vụ công Quốc gia',
          detail: 'Đã đối chiếu thủ tục 1.000894',
          status: 'ready',
          source_url: 'https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-hanh-chinh.html',
        }],
        actions: [{
          id: 'start-birth-form',
          label: 'Bắt đầu điền tờ khai',
          description: 'Mở mẫu khai sinh đã kiểm duyệt',
          kind: 'start_form',
          value: procedureId,
          icon: 'form',
          primary: true,
        }],
      });
    }
    if (pathname === `/api/v1/drafts/templates/${procedureId}` && method === 'GET') {
      return json(route, [{
        id: 'birth-declaration-v1',
        procedure_id: procedureId,
        output_name: 'Tờ khai đăng ký khai sinh',
        version: '1.0',
        source_checked_on: '2026-07-18',
        fields: [
          { key: 'ho_ten_tre', label: 'Họ, chữ đệm, tên trẻ', input_type: 'text', required: true, allowed_values: [] },
          { key: 'ngay_sinh', label: 'Ngày sinh', input_type: 'date', required: true, allowed_values: [] },
        ],
        disclaimer: 'Bản nháp cần được người dân rà soát.',
        legal_sources: [{
          document_number: 'NĐ 123/2015/NĐ-CP',
          title: 'Quy định chi tiết một số điều và biện pháp thi hành Luật hộ tịch',
          issuing_authority: 'Chính phủ',
          role: 'Căn cứ biểu mẫu',
          source_url: 'https://vanban.chinhphu.vn/',
        }],
      }]);
    }
    if (pathname === `/api/v1/procedures/${procedureId}/capabilities` && method === 'GET') {
      return json(route, {
        chat: true,
        checklist: true,
        dynamic_form: true,
        ocr_autofill: true,
        legal_validation: true,
        official_draft: true,
        requires_human_review: true,
      });
    }
    if (pathname === `/api/v1/procedures/${procedureId}/form-schema` && method === 'GET') {
      return json(route, {
        procedure_id: procedureId,
        template_id: 'birth-declaration-v1',
        title: 'Tờ khai đăng ký khai sinh',
        fields: [
          { key: 'ho_ten_tre', label: 'Họ, chữ đệm, tên trẻ', type: 'text', required: true, options: [], ocr_sources: ['birth_certificate'] },
          { key: 'ngay_sinh', label: 'Ngày sinh', type: 'date', required: true, options: [], ocr_sources: ['birth_certificate'] },
        ],
        clarifying_questions: [],
      });
    }

    return json(route, { detail: `E2E mock chưa định nghĩa ${method} ${pathname}` }, 501);
  });

  return state;
}

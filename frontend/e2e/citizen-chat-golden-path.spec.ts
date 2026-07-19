import { expect, test } from '@playwright/test';
import { mockCitizenChatApi } from './support/citizen-chat-api';

test('citizen completes the hackathon chat golden path without creating a duplicate case', async ({ page }, testInfo) => {
  const pageErrors: Error[] = [];
  page.on('pageerror', error => pageErrors.push(error));
  await page.addInitScript(theme => localStorage.setItem('ubndai.theme', theme), testInfo.project.name === 'mobile' ? 'dark' : 'light');
  const apiState = await mockCitizenChatApi(page);

  await page.goto('/chat');
  await page.getByLabel('Mật khẩu').fill('ChangeMe123!');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();

  if (pageErrors.length) throw pageErrors[0];
  await Promise.race([
    expect(page.getByRole('heading', { name: 'Chuẩn bị hồ sơ bằng một cuộc trò chuyện' })).toBeVisible(),
    page.waitForEvent('pageerror').then(error => Promise.reject(error)),
  ]);
  expect(pageErrors, 'the chat page must not raise runtime errors').toEqual([]);
  await page.getByRole('button', { name: 'Lịch sử', exact: true }).click();
  await expect(page.locator('.history-item', { hasText: 'Đăng ký khai sinh' })).toBeVisible();

  // Prove that “new chat” clears a previously selected case, not merely the transcript.
  await page.locator('.history-item', { hasText: 'Đăng ký khai sinh' }).click();
  await expect(page.getByText('Đây là cuộc trò chuyện khai sinh trước đó.')).toBeVisible();
  await page.getByRole('button', { name: 'Cuộc trò chuyện mới', exact: true }).click();
  await expect(page.getByText('Đây là cuộc trò chuyện khai sinh trước đó.')).not.toBeVisible();
  await expect(page.getByText('Xin chào! Hãy mô tả thủ tục bạn cần hỗ trợ.')).toBeVisible();

  const composer = page.getByRole('textbox', { name: 'Nội dung cần hỏi' });
  await composer.fill('Vợ tôi mới sinh em bé, tôi cần làm giấy tờ gì?');
  await composer.press('Enter');

  await expect(page.getByText('Tôi đã xác định thủ tục phù hợp là Đăng ký khai sinh.')).toBeVisible();
  await expect(page.getByText('Trẻ sinh tại Việt Nam?')).toBeVisible();
  expect(apiState.chatRequests[0]).toMatchObject({ message: 'Vợ tôi mới sinh em bé, tôi cần làm giấy tờ gì?' });
  expect(apiState.chatRequests[0]).not.toHaveProperty('case_id');

  await page.getByRole('button', { name: 'Có', exact: true }).click();
  // Boolean chips currently prepare the answer in the composer. Keep the test
  // compatible if the UX advances to submit-on-click for the demo.
  if (await composer.inputValue() === 'Có') await composer.press('Enter');

  await expect(page.getByText('Checklist cá nhân hóa đã sẵn sàng: 2 giấy tờ cần chuẩn bị.')).toBeVisible();
  await expect(page.getByText('Đã kiểm chứng nguồn')).toBeVisible();
  await expect(page).toHaveScreenshot('citizen-chat-checklist.png', { animations: 'disabled' });
  expect(apiState.chatRequests[1]).toMatchObject({ case_id: 'case-chat-001', message: 'Có' });

  await page.getByRole('button', { name: /Bắt đầu điền tờ khai/ }).click();
  await expect(page.getByRole('complementary', { name: 'Không gian sinh văn bản' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Tờ khai đăng ký khai sinh' })).toBeVisible();
  await expect(page.getByText('Đã mở biểu mẫu. Bạn có thể bổ sung dữ liệu rồi sinh bản nháp để rà soát.')).toBeVisible();
  await expect(page).toHaveScreenshot('citizen-document-workspace.png', { animations: 'disabled' });

  expect(apiState.createCaseRequests, 'form handoff must reuse the case created by chat').toHaveLength(0);
});

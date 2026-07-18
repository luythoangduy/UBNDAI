import { describe, expect, it } from 'vitest';
import { applicationStatusFromSearch, isApplicationManagementPath, legacyReviewCaseId, needsOfficerAuthentication } from './application-management-routing';

describe('officer application-management routing', () => {
  it('renders the dashboard directly at the officer root', () => {
    expect(isApplicationManagementPath('/officer')).toBe(true);
    expect(isApplicationManagementPath('/officer/')).toBe(true);
  });

  it('keeps legacy review routes on the existing officer portal', () => {
    expect(isApplicationManagementPath('/officer/review/case-demo-001')).toBe(false);
    expect(isApplicationManagementPath('/citizen')).toBe(false);
  });

  it('requires login without an officer token', () => {
    expect(needsOfficerAuthentication('')).toBe(true);
    expect(needsOfficerAuthentication('signed-token')).toBe(false);
  });

  it('reads the caution filter from the applications URL', () => {
    expect(applicationStatusFromSearch('?status=CAUTION_REVIEW_REQUIRED')).toBe('CAUTION_REVIEW_REQUIRED');
    expect(applicationStatusFromSearch('')).toBeUndefined();
  });

  it('opens the legacy form workspace for a selected application', () => {
    expect(legacyReviewCaseId('/officer/review/case-demo-001')).toBe('case-demo-001');
    expect(legacyReviewCaseId('/officer/applications')).toBeUndefined();
    expect(isApplicationManagementPath('/officer/applications/case-demo-001')).toBe(true);
  });
});

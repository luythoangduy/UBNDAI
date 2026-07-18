export function isApplicationManagementPath(pathname: string): boolean {
  return /^\/officer\/?$/.test(pathname)
    || /^\/officer\/(dashboard|history|reports)(\/|$)/.test(pathname)
    || /^\/officer\/applications(\/|$)/.test(pathname);
}

export function needsOfficerAuthentication(accessToken: string): boolean {
  return !accessToken.trim();
}

export function applicationStatusFromSearch(search: string): string | undefined {
  return new URLSearchParams(search).get('status') || undefined;
}

export function legacyReviewCaseId(pathname: string): string | undefined {
  const match = pathname.match(/^\/officer\/review\/([^/]+)\/?$/);
  return match?.[1] ? decodeURIComponent(match[1]) : undefined;
}

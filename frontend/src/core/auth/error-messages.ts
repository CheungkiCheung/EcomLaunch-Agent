import type { AuthErrorCode, AuthErrorResponse } from "./types";

export type LocalizedAuthErrorMessages = Record<
  AuthErrorCode | "fallback",
  string
>;

export function getLocalizedAuthErrorMessage(
  error: AuthErrorResponse,
  messages: LocalizedAuthErrorMessages,
): string {
  return messages[error.code] ?? messages.fallback;
}

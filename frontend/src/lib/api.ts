import type {
  Account,
  ChatResponse,
  FlaggedTransaction,
  FlagExplanation,
  Page,
  Transaction,
  User,
} from "./types";

const TOKEN_KEY = "sentinelbank.token";
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 401) {
    clearToken();
    throw new ApiError("Your session has expired. Sign in again.", 401);
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body.detail)
      .catch(() => null);
    throw new ApiError(
      typeof detail === "string" ? detail : `Request failed (${response.status})`,
      response.status,
    );
  }

  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username, password });
  const response = await fetch("/api/v1/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (response.status === 401) {
    throw new ApiError("Incorrect username or password", 401);
  }
  if (!response.ok) {
    throw new ApiError(`Sign in failed: the server returned ${response.status}`, response.status);
  }

  const data = (await response.json()) as { access_token: string };
  setToken(data.access_token);
}

export const api = {
  me: () => request<User>("/auth/me"),

  listFlags: (params: { status?: string; minScore?: number; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.minScore) query.set("min_score", String(params.minScore));
    query.set("limit", String(params.limit ?? 50));
    return request<Page<FlaggedTransaction>>(`/flags?${query}`);
  },

  getFlag: (flagId: number) => request<FlaggedTransaction>(`/flags/${flagId}`),

  explainFlag: (flagId: number) => request<FlagExplanation>(`/flags/${flagId}/explain`),

  reviewFlag: (flagId: number, status: "confirmed" | "dismissed", note?: string) =>
    request<unknown>(`/flags/${flagId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, note: note ?? null }),
    }),

  getAccount: (accountId: number) => request<Account>(`/accounts/${accountId}`),

  listTransactions: (accountId: number, limit = 20) =>
    request<Page<Transaction>>(`/accounts/${accountId}/transactions?limit=${limit}`),

  setAccountStatus: (accountId: number, status: "active" | "frozen", reason: string) =>
    request<Account>(`/accounts/${accountId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, reason }),
    }),

  chat: (message: string, threadId?: string) =>
    request<ChatResponse>("/assistant/chat", {
      method: "POST",
      body: JSON.stringify({ message, thread_id: threadId ?? null }),
    }),

  approve: (
    threadId: string,
    decisions: { action_id: string; approved: boolean; note?: string }[],
  ) =>
    request<ChatResponse>("/assistant/approve", {
      method: "POST",
      body: JSON.stringify({ thread_id: threadId, decisions }),
    }),
};
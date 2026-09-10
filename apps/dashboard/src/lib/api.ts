import type { DashboardSnapshot, JournalRecord } from "@/types/dashboard"

const API_URL = (process.env.RIRI_API_URL || "").replace(/\/$/, "")
const DASHBOARD_TOKEN = process.env.RIRI_DASHBOARD_API_KEY || ""

export class RiriApiError extends Error {
  constructor(
    message: string,
    public readonly kind: "configuration" | "timeout" | "upstream",
    public readonly status = 502,
  ) {
    super(message)
    this.name = "RiriApiError"
  }
}

async function request<T>(endpoint: string, timeoutMs = 10_000): Promise<T> {
  if (!API_URL) {
    throw new RiriApiError("RIRI_API_URL is not configured", "configuration", 500)
  }
  if (!DASHBOARD_TOKEN) {
    throw new RiriApiError("RIRI_DASHBOARD_API_KEY is not configured", "configuration", 500)
  }

  let response: Response
  try {
    response = await fetch(
      `${API_URL}${endpoint}`,
      {
        cache: "no-store",
        headers: { Authorization: `Bearer ${DASHBOARD_TOKEN}` },
        signal: AbortSignal.timeout(timeoutMs),
      },
    )
  } catch (error) {
    if (error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError")) {
      throw new RiriApiError("RIRI API request timed out", "timeout", 504)
    }
    throw new RiriApiError("RIRI API connection failed", "upstream")
  }

  if (!response.ok) {
    throw new RiriApiError(`RIRI API returned ${response.status}`, "upstream")
  }
  return response.json() as Promise<T>
}

export function getDashboardSnapshot() {
  return request<DashboardSnapshot>("/dashboard/latest")
}

export function getJournalHistory() {
  return request<JournalRecord[]>("/journal/history")
}

export function getFullJournalHistory() {
  return request<JournalRecord[]>("/journal", 15_000)
}

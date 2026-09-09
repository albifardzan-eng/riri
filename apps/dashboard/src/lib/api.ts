import type { DashboardSnapshot, JournalRecord } from "@/types/dashboard"

const API_URL = (process.env.RIRI_API_URL || "").replace(/\/$/, "")
const DASHBOARD_TOKEN = process.env.RIRI_DASHBOARD_API_KEY || ""

async function request<T>(endpoint: string): Promise<T> {
  if (!API_URL) {
    throw new Error("RIRI_API_URL is not configured")
  }
  if (!DASHBOARD_TOKEN) {
    throw new Error("RIRI_DASHBOARD_API_KEY is not configured")
  }

  const response = await fetch(
    `${API_URL}${endpoint}`,
    {
      cache: "no-store",
      headers: { Authorization: `Bearer ${DASHBOARD_TOKEN}` },
      signal: AbortSignal.timeout(5_000),
    },
  )

  if (!response.ok) {
    throw new Error(`RIRI API returned ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function getDashboardSnapshot() {
  return request<DashboardSnapshot>("/dashboard/latest")
}

export function getJournalHistory() {
  return request<JournalRecord[]>("/journal/history")
}

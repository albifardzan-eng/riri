import { getFullJournalHistory, RiriApiError } from "@/lib/api"
import type { JournalRecord } from "@/types/dashboard"

export const dynamic = "force-dynamic"

export async function GET() {
  try {
    const rows = await getFullJournalHistory()
    const trades = rows.filter((row: JournalRecord) =>
      row.event === "TRADE_EXECUTED" || row.event === "TRADE_CLOSED",
    ).reverse()
    return Response.json(trades, {
      headers: { "Cache-Control": "no-store" },
    })
  } catch (error) {
    const failure = error instanceof RiriApiError ? error : new RiriApiError("Unexpected trade history proxy error", "upstream")
    return Response.json({ error: failure.message, kind: failure.kind }, {
      status: failure.status,
      headers: { "Cache-Control": "no-store" },
    })
  }
}

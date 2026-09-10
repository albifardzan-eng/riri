import { getJournalHistory, RiriApiError } from "@/lib/api"

export const dynamic = "force-dynamic"

export async function GET() {
  try {
    return Response.json(await getJournalHistory(), {
      headers: { "Cache-Control": "no-store" },
    })
  } catch (error) {
    const failure = error instanceof RiriApiError ? error : new RiriApiError("Unexpected event proxy error", "upstream")
    return Response.json({ error: failure.message, kind: failure.kind }, {
      status: failure.status,
      headers: { "Cache-Control": "no-store" },
    })
  }
}

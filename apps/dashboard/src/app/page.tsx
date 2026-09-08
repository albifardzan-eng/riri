import DashboardCard from "@/components/dashboard-card"
import JournalTable from "@/components/journal-table"
import { getDashboardSnapshot, getJournalHistory } from "@/lib/api"

export const dynamic = "force-dynamic"

export default async function Home() {
  const [snapshotResult, historyResult] = await Promise.allSettled([
    getDashboardSnapshot(),
    getJournalHistory(),
  ])

  const snapshot = snapshotResult.status === "fulfilled" ? snapshotResult.value : {}
  const history = historyResult.status === "fulfilled" ? historyResult.value : []
  const unavailable = snapshotResult.status === "rejected" || historyResult.status === "rejected"
  const market = snapshot.market

  return (
    <main className="p-8">
      <h1 className="mb-2 text-4xl font-bold">RIRI Dashboard</h1>
      <p className="mb-8 text-sm text-neutral-500">
        {market ? `${market.symbol} · ${market.timeframe} · account ${market.account_id}` : "No market snapshot"}
        {snapshot.updated_at && ` · Updated ${snapshot.updated_at}`}
        {" · Refresh this page for the latest snapshot."}
      </p>

      {unavailable && (
        <div role="alert" className="mb-6 rounded border border-amber-500 bg-amber-50 p-3 text-amber-900">
          Dashboard data is temporarily unavailable. Verify the API URL and dashboard credential.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardCard title="Balance" value={market?.balance ?? 0} />
        <DashboardCard title="Equity" value={market?.equity ?? 0} />
        <DashboardCard title="Free Margin" value={market?.free_margin ?? 0} />
        <DashboardCard title="Open Trades" value={market?.positions?.length ?? 0} />
        <DashboardCard title="Score" value={snapshot.score?.score ?? 0} />
        <DashboardCard title="Current Decision" value={snapshot.decision?.decision ?? "-"} />
        <DashboardCard title="Confidence" value={snapshot.decision?.confidence ?? "-"} />
        <DashboardCard title="Risk" value={snapshot.risk?.approved ? "APPROVED" : snapshot.risk?.reason ?? "-"} />
        <DashboardCard title="Pipeline" value={snapshot.pipeline ? `${snapshot.pipeline.status} · ${snapshot.pipeline.stage}` : "UNKNOWN"} />
        <DashboardCard title="AI Status" value={snapshot.decision?.status ?? (snapshot.pipeline?.status === "PROCESSING" ? "PENDING" : snapshot.pipeline?.status === "SKIPPED" ? "NOT_CALLED" : "UNKNOWN")} />
        <DashboardCard title="AI Gate" value={snapshot.ai_gate?.reason ?? "UNKNOWN"} />
        <DashboardCard title="Analysis Reason" value={snapshot.pipeline?.reason || snapshot.decision?.reason || "-"} />
        <DashboardCard title="AI Output Tokens" value={snapshot.decision?.output_tokens ?? "-"} />
      </div>

      <section className="mt-10">
        <h2 className="mb-4 text-2xl font-bold">Lifecycle Journal</h2>
        <JournalTable rows={history} />
      </section>
    </main>
  )
}

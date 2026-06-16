import DashboardCard from "@/components/dashboard-card"
import JournalTable from "@/components/journal-table"

import {
  getLatestMarket,
  getLatestDecision,
  getLatestRisk,
  getLatestExecution,
  getJournalHistory
} from "@/lib/api"

export default async function Home() {

  const market =
    await getLatestMarket()

  const decision =
    await getLatestDecision()

  const risk =
    await getLatestRisk()

  const execution =
    await getLatestExecution()

  const history =
    await getJournalHistory()

  return (
    <main className="p-8">

      <h1 className="text-4xl font-bold mb-8">
        RIRI Dashboard
      </h1>

      <div className="grid grid-cols-4 gap-4">

        <DashboardCard
          title="Balance"
          value={market?.balance ?? 0}
        />

        <DashboardCard
          title="Equity"
          value={market?.equity ?? 0}
        />

        <DashboardCard
          title="Free Margin"
          value={market?.free_margin ?? 0}
        />

        <DashboardCard
          title="Open Trades"
          value={
            market?.positions?.length ?? 0
          }
        />

        <DashboardCard
          title="Last Decision"
          value={
            decision?.decision ?? "-"
          }
        />

        <DashboardCard
          title="Confidence"
          value={
            decision?.confidence ?? 0
          }
        />

        <DashboardCard
          title="Risk Status"
          value={
            risk?.approved
              ? "APPROVED"
              : "-"
          }
        />

        <DashboardCard
          title="Execution"
          value={
            execution?.executed
              ? "READY"
              : "-"
          }
        />

      </div>

      <div className="mt-10">

        <h2 className="text-2xl font-bold mb-4">
          Trade History
        </h2>

        <JournalTable
          rows={
            Array.isArray(history)
              ? history
              : []
          }
        />

      </div>

    </main>
  )
}
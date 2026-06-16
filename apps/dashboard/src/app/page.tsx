import StatusCard from "@/components/status-card"
import MarketPanel from "@/components/market-panel"
import { getStatus } from "@/lib/api"

export default async function Home() {
  const status = await getStatus()

  return (
    <main className="p-8">
      <h1 className="text-4xl font-bold mb-8">
        RIRI Dashboard
      </h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatusCard
          title="System"
          value={status.status}
        />

        <StatusCard
          title="Version"
          value={status.version}
        />

        <StatusCard
          title="Trader Status"
          value="Waiting"
        />
      </div>

      <MarketPanel />
    </main>
  )
}
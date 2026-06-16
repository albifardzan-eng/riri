"use client"

import StatusCard from "./status-card"
import { useMarketWS } from "@/lib/use-market-ws"

export default function MarketPanel() {

  const market =
    useMarketWS()

  if (!market) {
    return (
      <div>
        Waiting for market data...
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-4">

      <StatusCard
        title="Bid"
        value={market.bid}
      />

      <StatusCard
        title="Ask"
        value={market.ask}
      />

      <StatusCard
        title="Spread"
        value={market.spread}
      />

      <StatusCard
        title="Balance"
        value={market.balance}
      />

      <StatusCard
        title="Equity"
        value={market.equity}
      />

      <StatusCard
        title="Free Margin"
        value={market.free_margin}
      />

    </div>
  )
}
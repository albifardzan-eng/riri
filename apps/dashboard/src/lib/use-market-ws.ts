"use client"

import { useEffect, useState } from "react"

export function useMarketWS() {

  const [market, setMarket] =
    useState<any>(null)

  useEffect(() => {

    const ws = new WebSocket(
      process.env.NEXT_PUBLIC_WS_URL ||
      "ws://localhost:8000/ws"
    )

    ws.onmessage = (event) => {

      const data =
        JSON.parse(event.data)

      setMarket(data)
    }

    return () => {
      ws.close()
    }

  }, [])

  return market
}
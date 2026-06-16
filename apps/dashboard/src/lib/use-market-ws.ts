"use client"

import {
  useEffect,
  useState
} from "react"

export function useMarketWS() {

  const [
    payload,
    setPayload
  ] = useState<any>(null)

  useEffect(() => {

    const ws =
      new WebSocket(
        process.env
          .NEXT_PUBLIC_WS_URL ||
        "ws://localhost:8000/ws"
      )

    ws.onmessage =
      (event) => {

        setPayload(
          JSON.parse(
            event.data
          )
        )
      }

    return () => {
      ws.close()
    }

  }, [])

  return payload
}
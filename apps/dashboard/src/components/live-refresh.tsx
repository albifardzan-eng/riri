"use client"

import { useEffect, useState, useTransition } from "react"
import { useRouter } from "next/navigation"

export default function LiveRefresh() {
  const router = useRouter()
  const [isPending, startTransition] = useTransition()
  const [seconds, setSeconds] = useState(10)

  useEffect(() => {
    const ticker = window.setInterval(() => setSeconds(value => value <= 1 ? 10 : value - 1), 1_000)
    const refresh = window.setInterval(() => startTransition(() => router.refresh()), 10_000)
    return () => { window.clearInterval(ticker); window.clearInterval(refresh) }
  }, [router])

  return <button className="refresh-button" type="button" onClick={() => startTransition(() => router.refresh())} disabled={isPending}>
    <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M20 7v5h-5M4 17v-5h5M6.1 9A7 7 0 0 1 18 6.5L20 9M4 15l2 2.5A7 7 0 0 0 17.9 15" /></svg>
    {isPending ? "Updating" : `Refresh ${seconds}s`}
  </button>
}

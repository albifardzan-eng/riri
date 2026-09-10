"use client"

import { useState } from "react"
import type { JournalRecord } from "@/types/dashboard"

interface Props { recentRows: JournalRecord[]; tradeRows: JournalRecord[]; tradeHistoryAvailable: boolean }

const localTime = (value?: string) => value ? new Intl.DateTimeFormat("id-ID", {
  timeZone: "Asia/Jakarta", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit",
}).format(new Date(value)) : "—"

const eventLabel = (event?: string) => ({
  ANALYSIS: "Analysis", SIGNAL_CREATED: "Signal created", TRADE_EXECUTED: "Trade opened",
  TRADE_REJECTED: "Trade rejected", TRADE_CLOSED: "Trade closed",
}[event ?? ""] ?? event ?? "Analysis")

const detail = (row: JournalRecord) => {
  if (row.event === "TRADE_CLOSED") return row.profit === undefined ? "Position closed" : `Realized P/L ${row.profit >= 0 ? "+" : ""}$${row.profit.toFixed(2)}`
  if (row.confirmation) return row.confirmation.reason || row.confirmation.status
  if (row.pipeline?.reason) return row.pipeline.reason
  if (row.decision?.decision === "NONE") return row.decision.reason || row.decision.status || "No trade"
  if (row.risk && !row.risk.approved) return row.risk.reason
  return row.execution?.reason || row.risk?.reason || row.gate_reason || "—"
}

const action = (row: JournalRecord) => row.decision?.decision ?? row.confirmation?.action ?? row.signal?.action ?? row.side ?? "—"
const lot = (row: JournalRecord) => row.confirmation?.filled_lot || row.signal?.lot || row.execution?.lot || row.lot

function EventTable({ rows }: { rows: JournalRecord[] }) {
  return <div className="journal-wrap"><table className="journal-table">
    <thead><tr><th>Time</th><th>Event</th><th>Action</th><th>Score</th><th>AI confidence</th><th>Lot</th><th>Result / reason</th></tr></thead>
    <tbody>{rows.map((row, index) => <tr key={row.signal?.signal_id || row.confirmation?.signal_id || `${row.timestamp}-${index}`}>
      <td className="time-cell">{localTime(row.timestamp)}</td>
      <td><span className={`event-tag event-${(row.event ?? "analysis").toLowerCase()}`}>{eventLabel(row.event)}</span></td>
      <td><span className={`side side-${action(row).toLowerCase()}`}>{action(row)}</span></td>
      <td>{row.score?.score ?? "—"}</td><td>{row.decision ? `${row.decision.confidence}%` : "—"}</td>
      <td>{lot(row)?.toFixed(2) ?? "—"}</td><td className="detail-cell">{detail(row)}</td>
    </tr>)}</tbody>
  </table>{!rows.length && <div className="table-empty">No lifecycle events yet.</div>}</div>
}

function TradeTable({ rows, available }: { rows: JournalRecord[]; available: boolean }) {
  return <div className="journal-wrap"><table className="journal-table trade-table">
    <thead><tr><th>Time</th><th>Lifecycle</th><th>Side</th><th>Lot</th><th>Price</th><th>Order / deal</th><th>Realized P/L</th></tr></thead>
    <tbody>{rows.map((row, index) => {
      const confirmation = row.confirmation
      return <tr key={`${row.event}-${row.deal_id ?? confirmation?.deal_id ?? row.timestamp}-${index}`}>
        <td className="time-cell">{localTime(row.timestamp)}</td>
        <td><span className={`event-tag event-${(row.event ?? "trade").toLowerCase()}`}>{eventLabel(row.event)}</span></td>
        <td><span className={`side side-${action(row).toLowerCase()}`}>{action(row)}</span></td>
        <td>{lot(row)?.toFixed(2) ?? "—"}</td>
        <td>{(row.price ?? confirmation?.executed_price)?.toFixed(2) ?? "—"}</td>
        <td className="mono-cell">#{row.order_id ?? confirmation?.order_id ?? row.deal_id ?? confirmation?.deal_id ?? "—"}</td>
        <td className={row.profit === undefined ? "" : row.profit >= 0 ? "profit" : "loss"}>{row.profit === undefined ? "Open" : `${row.profit >= 0 ? "+" : ""}$${row.profit.toFixed(2)}`}</td>
      </tr>
    })}</tbody>
  </table>{!available && <div className="table-empty table-error">Full trade history is temporarily unavailable.</div>}{available && !rows.length && <div className="table-empty">Belum ada trade yang tercatat.</div>}</div>
}

export default function JournalTable({ recentRows, tradeRows, tradeHistoryAvailable }: Props) {
  const [tab, setTab] = useState<"events" | "trades">("events")
  return <div className="journal-panel">
    <div className="journal-tabs" role="tablist" aria-label="Journal view">
      <button type="button" role="tab" aria-selected={tab === "events"} onClick={() => setTab("events")}><span>100 Event Terakhir</span><i>{recentRows.length}</i></button>
      <button type="button" role="tab" aria-selected={tab === "trades"} onClick={() => setTab("trades")}><span>Histori Trade</span><i>{tradeRows.length}</i></button>
    </div>
    <div role="tabpanel">{tab === "events" ? <EventTable rows={recentRows} /> : <TradeTable rows={tradeRows} available={tradeHistoryAvailable} />}</div>
  </div>
}

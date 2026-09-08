import type { JournalRecord } from "@/types/dashboard"

interface Props {
  rows: JournalRecord[]
}

function detail(row: JournalRecord) {
  if (row.event === "TRADE_CLOSED" && row.profit !== undefined) return `P/L ${row.profit}`
  if (row.confirmation) return row.confirmation.reason || row.confirmation.status
  if (row.pipeline?.reason) return row.pipeline.reason
  if (row.decision?.status && row.decision.status !== "UNKNOWN" && row.decision.decision === "NONE") {
    return row.decision.reason || row.decision.status
  }
  if (row.risk && !row.risk.approved) return row.risk.reason
  if (row.execution) return row.execution.reason
  if (row.risk) return row.risk.reason
  return row.gate_reason || "-"
}

export default function JournalTable({ rows }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse border text-left text-sm">
        <thead>
          <tr>
            <th className="border p-2">Time</th>
            <th className="border p-2">Event</th>
            <th className="border p-2">Symbol</th>
            <th className="border p-2">Action</th>
            <th className="border p-2">AI Status</th>
            <th className="border p-2">Score</th>
            <th className="border p-2">Lot</th>
            <th className="border p-2">Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.signal?.signal_id || `${row.timestamp}-${index}`}>
              <td className="border p-2">{row.timestamp ? new Date(row.timestamp).toLocaleString() : "-"}</td>
              <td className="border p-2">{row.event ?? "ANALYSIS"}</td>
              <td className="border p-2">{row.symbol ?? row.signal?.symbol ?? "-"}</td>
              <td className="border p-2">{row.decision?.decision ?? row.confirmation?.action ?? row.signal?.action ?? row.side ?? "-"}</td>
              <td className="border p-2">{row.decision?.status ?? (row.pipeline?.status === "SKIPPED" && row.pipeline.reason !== "CYCLE_SUPERSEDED" ? "NOT_CALLED" : "UNKNOWN")}</td>
              <td className="border p-2">{row.score?.score ?? "-"}</td>
              <td className="border p-2">{row.confirmation?.filled_lot ?? row.signal?.lot ?? row.execution?.lot ?? row.lot ?? "-"}</td>
              <td className="border p-2">{detail(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="border border-t-0 p-4 text-neutral-500">No lifecycle events yet.</p>}
    </div>
  )
}

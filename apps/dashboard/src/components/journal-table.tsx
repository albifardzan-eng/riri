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
    <div className="journal-wrap">
      <table className="journal-table">
        <thead>
          <tr>
            <th>Time</th><th>Event</th><th>Symbol</th><th>Action</th>
            <th>AI Status</th><th>Score</th><th>Confidence</th><th>Lot</th><th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.signal?.signal_id || `${row.timestamp}-${index}`}>
              <td>{row.timestamp ? new Date(row.timestamp).toLocaleString() : "-"}</td>
              <td>{row.event ?? "ANALYSIS"}</td>
              <td>{row.symbol ?? row.signal?.symbol ?? "-"}</td>
              <td>{row.decision?.decision ?? row.confirmation?.action ?? row.signal?.action ?? row.side ?? "-"}</td>
              <td>{row.decision?.status ?? (row.pipeline?.status === "SKIPPED" && row.pipeline.reason !== "CYCLE_SUPERSEDED" ? "NOT_CALLED" : "UNKNOWN")}</td>
              <td>{row.score?.score ?? "-"}</td>
              <td>{row.decision?.confidence ?? "-"}</td>
              <td>{row.confirmation?.filled_lot ?? row.signal?.lot ?? row.execution?.lot ?? row.lot ?? "-"}</td>
              <td>{detail(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="empty">No lifecycle events yet.</p>}
    </div>
  )
}

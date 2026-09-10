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
  const decision = snapshot.decision
  const risk = snapshot.risk
  const execution = snapshot.execution
  const aiTone = decision?.status === "ERROR" || decision?.status === "UNAVAILABLE"
    ? "danger" : decision?.decision && decision.decision !== "NONE" ? "good" : "neutral"
  const riskTone = risk?.approved ? "good" : risk ? "warn" : "neutral"

  return (
    <main className="dashboard-shell">
      <div className="eyebrow">Operational trading control</div>
      <h1 className="dashboard-title">RIRI</h1>
      <p className="dashboard-subtitle">
        {market ? `${market.symbol} · ${market.timeframe} · account ${market.account_id}` : "Waiting for a market snapshot"}
        {snapshot.updated_at && ` · updated ${new Date(snapshot.updated_at).toLocaleString()}`}
      </p>

      <div className="status-strip">
        <span className={`status-pill ${unavailable ? "danger" : "good"}`}>{unavailable ? "API UNAVAILABLE" : "API CONNECTED"}</span>
        <span className={`status-pill ${snapshot.pipeline?.status === "ERROR" ? "danger" : snapshot.pipeline?.status === "SKIPPED" ? "warn" : "good"}`}>PIPELINE {snapshot.pipeline?.status ?? "WAITING"}</span>
        <span className={`status-pill ${aiTone}`}>AI {decision?.status ?? (snapshot.pipeline?.status === "SKIPPED" ? "NOT CALLED" : "WAITING")}</span>
        <span className={`status-pill ${riskTone}`}>RISK {risk?.approved ? "APPROVED" : risk?.reason ?? "PENDING"}</span>
      </div>

      {unavailable && (
        <div role="alert" className="alert">
          Dashboard data is unavailable. In Vercel, set <code>RIRI_API_URL=https://api-riri.albiagent.com</code> and the server-only <code>RIRI_DASHBOARD_API_KEY</code>, then redeploy.
        </div>
      )}

      <div className="metrics-grid">
        <DashboardCard title="Balance" value={market?.balance ?? "–"} />
        <DashboardCard title="Equity" value={market?.equity ?? "–"} detail={`free margin ${market?.free_margin ?? "–"}`} />
        <DashboardCard title="Open positions" value={market?.positions?.length ?? "–"} detail={`spread ${market?.spread ?? "–"} · ATR ${market?.atr ?? "–"}`} />
        <DashboardCard title="Initial score" value={snapshot.score?.score ?? "–"} tone={snapshot.score?.qualified ? "good" : "warn"} detail={snapshot.score?.qualified ? "AI-eligible score" : "Below AI score gate"} />
        <DashboardCard title="AI direction" value={decision?.decision ?? "–"} tone={aiTone} detail={decision?.reason ?? snapshot.ai_gate?.reason ?? "Waiting"} />
        <DashboardCard title="AI probability" value={decision ? `${decision.confidence}%` : "–"} tone={aiTone} detail="TP 1000 before SL 3000" />
        <DashboardCard title="Risk decision" value={risk?.approved ? "APPROVED" : "–"} tone={riskTone} detail={risk?.reason ?? "Not evaluated"} />
        <DashboardCard title="Signal" value={execution?.signal_created ? execution.order_type : "–"} tone={execution?.signal_created ? "good" : "neutral"} detail={execution ? `${execution.reason} · lot ${execution.lot}` : "No signal"} />
        <DashboardCard title="AI gate" value={snapshot.ai_gate?.call ? "CALLED" : "SKIPPED"} tone={snapshot.ai_gate?.call ? "good" : "warn"} detail={snapshot.ai_gate?.reason ?? "Waiting"} />
        <DashboardCard title="Pipeline" value={snapshot.pipeline?.stage ?? "WAITING"} detail={snapshot.pipeline?.reason ?? snapshot.pipeline?.status ?? "–"} />
        <DashboardCard title="AI output tokens" value={decision?.output_tokens ?? "–"} detail={decision?.latency_ms ? `${decision.latency_ms} ms` : "No AI call"} />
      </div>

      <section className="section">
        <div className="section-head"><h2 className="section-title">Lifecycle Journal</h2><span className="section-note">Latest 100 events · refresh page for latest data</span></div>
        <JournalTable rows={history} />
      </section>
    </main>
  )
}

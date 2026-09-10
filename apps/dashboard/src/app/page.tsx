import JournalTable from "@/components/journal-table"
import LiveRefresh from "@/components/live-refresh"
import { getDashboardSnapshot, getFullJournalHistory, getJournalHistory } from "@/lib/api"
import type { JournalRecord, Tone } from "@/types/dashboard"

export const dynamic = "force-dynamic"

const number = (value: number | undefined, digits = 2) =>
  value === undefined ? "—" : new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)

const money = (value: number | undefined) =>
  value === undefined ? "—" : new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", minimumFractionDigits: 2,
  }).format(value)

const time = (value?: string | number) => {
  if (!value) return "Waiting for data"
  const date = typeof value === "number" ? new Date(value * 1_000) : new Date(value)
  return new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(date)
}

function statusTone(status?: string): Tone {
  if (!status) return "neutral"
  if (["ERROR", "UNAVAILABLE", "REJECTED"].includes(status)) return "danger"
  if (["SKIPPED", "FILTERED", "PROCESSING"].includes(status)) return "warn"
  return "good"
}

function Stat({ label, value, detail, tone = "neutral" }: {
  label: string; value: string | number; detail?: string; tone?: Tone
}) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {detail && <span className="stat-detail">{detail}</span>}
    </div>
  )
}

function FlowStep({ index, label, value, detail, tone = "neutral" }: {
  index: string; label: string; value: string; detail: string; tone?: Tone
}) {
  return (
    <div className={`flow-step tone-${tone}`}>
      <span className="flow-index">{index}</span>
      <div>
        <span className="flow-label">{label}</span>
        <strong className="flow-value">{value}</strong>
        <span className="flow-detail">{detail}</span>
      </div>
    </div>
  )
}

export default async function Home() {
  const [snapshotResult, recentResult, fullResult] = await Promise.allSettled([
    getDashboardSnapshot(), getJournalHistory(), getFullJournalHistory(),
  ])

  const snapshot = snapshotResult.status === "fulfilled" ? snapshotResult.value : {}
  const recent = recentResult.status === "fulfilled" ? recentResult.value : []
  const full = fullResult.status === "fulfilled" ? fullResult.value : []
  const unavailable = snapshotResult.status === "rejected"
  const market = snapshot.market
  const score = snapshot.score
  const decision = snapshot.decision
  const risk = snapshot.risk
  const execution = snapshot.execution
  const pipeline = snapshot.pipeline
  const fundamental = snapshot.fundamental
  const statistics = snapshot.statistics
  const pattern = snapshot.pattern
  const positions = market?.positions ?? []
  const floating = market ? market.equity - market.balance : undefined
  const mid = market ? (market.bid + market.ask) / 2 : undefined
  const tradeRows = full.filter((row: JournalRecord) =>
    row.event === "TRADE_EXECUTED" || row.event === "TRADE_CLOSED",
  ).reverse()
  const recentRows = recent.slice(-100).reverse()
  const aiStatus = decision?.status ?? (snapshot.ai_gate?.call ? "PROCESSING" : "NOT CALLED")
  const executionStatus = execution?.signal_created ? execution.order_type : execution?.reason ?? "NO SIGNAL"
  const spreadBlocked = risk?.reason === "SPREAD_ABOVE_LIMIT" || pipeline?.reason === "SPREAD_ABOVE_LIMIT"
  const scoreParts = [
    ["Trend", score?.trend_score, 20], ["Momentum", score?.momentum_score, 15],
    ["Volume", score?.volume_score, 20], ["Volatility", score?.volatility_score, 15],
    ["Session", score?.session_score, 15], ["Spread", score?.spread_score, 15],
  ] as const

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">R</div>
          <div>
            <div className="brand-line"><strong>RIRI</strong><span>v1.2.0</span></div>
            <p>Real-time Investment Research Intelligence</p>
          </div>
        </div>
        <div className="topbar-status">
          <span className={`connection ${unavailable ? "is-offline" : ""}`}>
            <i aria-hidden="true" />{unavailable ? "API OFFLINE" : "LIVE"}
          </span>
          <LiveRefresh key={snapshot.updated_at} />
        </div>
      </header>

      {unavailable && <div role="alert" className="alert">Data API tidak tersedia. Periksa konfigurasi RIRI API pada deployment dashboard.</div>}

      <section className="market-hero" aria-label="Current XAUUSD market">
        <div className="market-identity">
          <div className="symbol-row">
            <span className="asset-icon">Au</span>
            <div><h1>{market?.symbol ?? "XAUUSD"}</h1><p>Gold / US Dollar · {market?.timeframe ?? "H1"}</p></div>
          </div>
          <span className="market-clock">Market snapshot · {time(market?.market_time)}</span>
        </div>
        <div className="price-block">
          <span className="price-label">MID PRICE</span>
          <strong>{number(mid, market?.digits ?? 2)}</strong>
          <span className="price-meta">Spread {number(market?.spread, 1)} pts</span>
        </div>
        <div className="quote-grid">
          <div><span>BID</span><strong>{number(market?.bid, market?.digits ?? 2)}</strong></div>
          <div><span>ASK</span><strong>{number(market?.ask, market?.digits ?? 2)}</strong></div>
          <div><span>ATR</span><strong>{number(market?.atr, 2)}</strong></div>
          <div><span>TICK VOL</span><strong>{number(market?.tick_volume, 0)}</strong></div>
        </div>
      </section>

      <section className="stat-grid" aria-label="Account overview">
        <Stat label="Balance" value={money(market?.balance)} detail={`Account ${market?.account_id ?? "—"}`} />
        <Stat label="Equity" value={money(market?.equity)} detail={`Floating ${money(floating)}`} tone={(floating ?? 0) >= 0 ? "good" : "danger"} />
        <Stat label="Free margin" value={money(market?.free_margin)} detail={market?.terminal_id ?? "Terminal unavailable"} />
        <Stat label="Open positions" value={positions.length} detail={positions.length ? `${positions.reduce((sum, p) => sum + p.lot, 0).toFixed(2)} total lot` : "No market exposure"} tone={positions.length ? "warn" : "good"} />
      </section>

      <div className="dashboard-grid">
        <section className="panel decision-panel">
          <div className="panel-heading">
            <div><span className="kicker">DECISION ENGINE</span><h2>Current pipeline</h2></div>
            <span className={`badge tone-${statusTone(pipeline?.status)}`}>{pipeline?.status ?? "WAITING"}</span>
          </div>
          <div className="flow-grid">
            <FlowStep index="01" label="INITIAL SCORE" value={score ? `${score.score}/100` : "—"} detail={score?.qualified ? "Qualified for AI" : "Below score gate"} tone={score?.qualified ? "good" : "warn"} />
            <FlowStep index="02" label="AI TRADER" value={decision?.decision ?? "NONE"} detail={decision ? `${decision.confidence}% confidence` : snapshot.ai_gate?.reason ?? "Waiting"} tone={decision?.decision && decision.decision !== "NONE" ? "good" : statusTone(aiStatus)} />
            <FlowStep index="03" label="RISK ENGINE" value={risk?.approved ? "PASS" : risk?.reason ?? "NOT RUN"} detail={risk?.approved ? `Risk score ${risk.risk_score}` : spreadBlocked ? "Spread protection active" : "No executable setup"} tone={risk?.approved ? "good" : risk ? "warn" : "neutral"} />
            <FlowStep index="04" label="EXECUTION" value={executionStatus} detail={execution?.signal_created ? `Lot ${execution.lot}` : pipeline?.reason ?? "No order queued"} tone={execution?.signal_created ? "good" : "neutral"} />
          </div>
          <div className="pipeline-foot">
            <div><span>AI gate</span><strong>{snapshot.ai_gate?.reason ?? "—"}</strong></div>
            <div><span>Stage</span><strong>{pipeline?.stage ?? "—"}</strong></div>
            <div><span>Latency</span><strong>{decision?.latency_ms ? `${decision.latency_ms} ms` : "—"}</strong></div>
            <div><span>Output tokens</span><strong>{decision?.output_tokens ?? "—"}</strong></div>
          </div>
        </section>

        <section className="panel score-panel">
          <div className="panel-heading">
            <div><span className="kicker">MARKET QUALITY</span><h2>Score composition</h2></div>
            <strong className={`score-orb ${score?.qualified ? "qualified" : ""}`}>{score?.score ?? "—"}</strong>
          </div>
          <div className="score-list">
            {scoreParts.map(([label, value, maximum]) => (
              <div className="score-row" key={label}>
                <div><span>{label}</span><strong>{value ?? 0}/{maximum}</strong></div>
                <div className="score-track"><i style={{ width: `${((value ?? 0) / maximum) * 100}%` }} /></div>
              </div>
            ))}
          </div>
          <div className="score-foot"><span>RSI <strong>{number(score?.rsi, 2)}</strong></span><span>Reversal <strong>{score?.reversal_score ?? 0}</strong></span></div>
        </section>
      </div>

      <div className="insight-grid">
        <section className="panel compact-panel">
          <div className="panel-heading"><div><span className="kicker">MARKET STRUCTURE</span><h2>Technical context</h2></div></div>
          <div className="detail-list">
            <div><span>Trend</span><strong>{statistics?.trend ?? pattern?.trend ?? "—"}</strong></div>
            <div><span>Pattern</span><strong>{pattern?.direction ?? "—"}</strong></div>
            <div><span>Support</span><strong>{number(statistics?.support ?? pattern?.support, 2)}</strong></div>
            <div><span>Resistance</span><strong>{number(statistics?.resistance ?? pattern?.resistance, 2)}</strong></div>
            <div><span>Market location</span><strong>{statistics?.market_location ?? "—"}</strong></div>
            <div><span>Volume spike</span><strong>{pattern?.volume_spike ? "YES" : "NO"}</strong></div>
          </div>
        </section>
        <section className="panel compact-panel">
          <div className="panel-heading"><div><span className="kicker">FUNDAMENTAL</span><h2>Session & news</h2></div><span className={`badge tone-${fundamental?.high_impact_news ? "danger" : "good"}`}>{fundamental?.high_impact_news ? "HIGH IMPACT" : "CLEAR"}</span></div>
          <div className="detail-list">
            <div><span>Session</span><strong>{fundamental?.session ?? "—"}</strong></div>
            <div><span>Liquidity</span><strong>{fundamental?.liquidity ?? "—"}</strong></div>
            <div><span>Risk level</span><strong>{fundamental?.risk_level ?? "—"}</strong></div>
            <div><span>News phase</span><strong>{fundamental?.phase ?? fundamental?.news_state ?? "NONE"}</strong></div>
            <div className="detail-wide"><span>Event</span><strong>{fundamental?.event ?? "No high-impact event"}</strong></div>
          </div>
        </section>
        <section className="panel compact-panel positions-panel">
          <div className="panel-heading"><div><span className="kicker">EXPOSURE</span><h2>Active positions</h2></div><span className="badge">{positions.length} OPEN</span></div>
          {positions.length ? <div className="position-list">{positions.map(position => (
            <div className="position-row" key={position.ticket}>
              <span className={`side side-${position.type.toLowerCase()}`}>{position.type}</span>
              <div><strong>#{position.ticket}</strong><span>{position.lot.toFixed(2)} lot</span></div>
              <strong className={position.profit >= 0 ? "profit" : "loss"}>{money(position.profit)}</strong>
            </div>
          ))}</div> : <div className="empty-state"><span>0</span><p>No active XAUUSD positions</p></div>}
        </section>
      </div>

      <section className="journal-section">
        <div className="section-heading">
          <div><span className="kicker">AUDIT TRAIL</span><h2>RIRI journal</h2></div>
          <p>Waktu ditampilkan dalam WIB · data diperbarui otomatis setiap 10 detik</p>
        </div>
        <JournalTable recentRows={recentRows} tradeRows={tradeRows} tradeHistoryAvailable={fullResult.status === "fulfilled"} />
      </section>

      <footer><span>RIRI · XAUUSD autonomous execution</span><span>Last API update {time(snapshot.updated_at)}</span></footer>
    </main>
  )
}

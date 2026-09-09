interface Props {
  title: string
  value: string | number
  detail?: string
  tone?: "neutral" | "good" | "warn" | "danger"
}

export default function DashboardCard(
  props: Props
) {

  return (
    <div className={`metric-card metric-${props.tone ?? "neutral"}`}>

      <div className="metric-title">
        {props.title}
      </div>

      <div className="metric-value">
        {props.value}
      </div>
      {props.detail && <div className="metric-detail">{props.detail}</div>}

    </div>
  )
}

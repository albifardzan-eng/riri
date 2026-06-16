export interface TraderDecision {
  decision: string
  confidence: number
}

export interface RiskDecision {
  approved: boolean
  risk_score: number
}

export interface ExecutionResult {
  executed: boolean
  order_type: string
  lot: number
  reason: string
}

export interface JournalRecord {
  timestamp?: string

  symbol: string

  score: {
    score: number
    qualified: boolean
  }

  decision?: TraderDecision

  risk?: RiskDecision

  execution?: ExecutionResult
}
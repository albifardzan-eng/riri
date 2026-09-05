export interface Position {
  ticket: number
  symbol: string
  type: "BUY" | "SELL"
  lot: number
  profit: number
}

export interface MarketData {
  symbol: string
  timeframe: string
  market_time: number
  account_id: string
  terminal_id: string
  instance_id: string
  bid: number
  ask: number
  spread: number
  point: number
  digits: number
  balance: number
  equity: number
  free_margin: number
  tick_volume: number
  atr: number
  positions: Position[]
}

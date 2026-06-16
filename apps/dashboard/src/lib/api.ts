const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"

async function request(
  endpoint: string
) {
  const response =
    await fetch(
      `${API_URL}${endpoint}`,
      {
        cache: "no-store"
      }
    )

  return response.json()
}

export async function getStatus() {
  return request("/status")
}

export async function getLatestMarket() {
  return request("/mt5/latest")
}

export async function getLatestScore() {
  return request("/score/latest")
}

export async function getLatestDecision() {
  return request("/trader/latest")
}

export async function getLatestRisk() {
  return request("/risk/latest")
}

export async function getLatestExecution() {
  return request("/execution/latest")
}

export async function getJournalHistory() {
  return request("/journal/history")
}
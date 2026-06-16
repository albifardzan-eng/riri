const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"

export async function getStatus() {
  const response = await fetch(
    `${API_URL}/status`,
    {
      cache: "no-store"
    }
  )

  return response.json()
}

export async function getLatestMarket() {
  const response = await fetch(
    `${API_URL}/mt5/latest`,
    {
      cache: "no-store"
    }
  )

  return response.json()
}
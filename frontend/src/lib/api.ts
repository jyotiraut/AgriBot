import axios from 'axios'
import { useAuth } from './auth'
import type {
  AdminFarmersResponse,
  AuthToken,
  ChatMessageOut,
  ChatResponse,
  ChatSession,
  MarketCalendarAllResponse,
  MarketCalendarMonthResponse,
  MarketForecastResponse,
  RecommendationsResponse,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

export const http = axios.create({ baseURL: BASE_URL, timeout: 60_000 })

http.interceptors.request.use((config) => {
  const token = useAuth.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      useAuth.getState().logout()
    }
    return Promise.reject(error)
  },
)

// ── Auth ──────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  const { data } = await http.post<AuthToken>('/auth/login', { email, password })
  return data
}

export async function register(email: string, password: string, name: string) {
  const { data } = await http.post<AuthToken>('/auth/register', { email, password, name })
  return data
}

// ── Chat ──────────────────────────────────────────────────────────────────

export async function sendChatMessage(message: string, sessionId?: string) {
  const { data } = await http.post<ChatResponse>('/chat', {
    message,
    session_id: sessionId,
  })
  return data
}

export async function listChatSessions() {
  const { data } = await http.get<ChatSession[]>('/chat/sessions')
  return data
}

export async function createChatSession() {
  const { data } = await http.post<ChatSession>('/chat/sessions')
  return data
}

export async function getChatSessionMessages(sessionId: string) {
  const { data } = await http.get<ChatMessageOut[]>(`/chat/sessions/${sessionId}/messages`)
  return data
}

export async function deleteChatSession(sessionId: string) {
  await http.delete(`/chat/sessions/${sessionId}`)
}

// ── Market ────────────────────────────────────────────────────────────────

export async function getMarketCalendar(topN = 5) {
  const { data } = await http.get<MarketCalendarAllResponse>('/market/calendar', {
    params: { top_n: topN },
  })
  return data
}

export async function getMarketCalendarMonth(bsMonth: number, topN = 8) {
  const { data } = await http.get<MarketCalendarMonthResponse>(`/market/calendar/${bsMonth}`, {
    params: { top_n: topN },
  })
  return data
}

export async function getMarketForecast(topN = 5) {
  const { data } = await http.get<MarketForecastResponse>('/market/forecast', {
    params: { top_n: topN },
  })
  return data
}

export async function getRecommendations(month: number, lang: 'en' | 'ne' = 'en') {
  // This endpoint runs a full feasibility+risk+price evaluation per candidate
  // crop, uncached server-side — routinely 40-45s cold. The shared client
  // timeout (60s) cuts it too close under normal variance, so give this one
  // call more room rather than raising the default for every other request.
  const { data } = await http.get<RecommendationsResponse>('/recommendations', {
    params: { month, lang },
    timeout: 120_000,
  })
  return data
}

// ── Admin ─────────────────────────────────────────────────────────────────

export async function getAdminFarmers(skip = 0, limit = 200) {
  const { data } = await http.get<AdminFarmersResponse>('/admin/farmers', {
    params: { skip, limit },
  })
  return data
}

export async function getCurrentSeason(month: number) {
  const { data } = await http.get<{ bs_month: number; month_name: string; season: string }>(
    '/season',
    { params: { month } },
  )
  return data
}

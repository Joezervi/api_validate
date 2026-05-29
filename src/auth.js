/**
 * auth.js — Gateway JWT management and configured axios instance.
 *
 * Auth flow:
 *  1. getGatewayToken() silently POSTs to /api/v1/auth/token using VITE_API_USER /
 *     VITE_API_PASSWORD from the build-time env. The resulting JWT is cached in
 *     localStorage with its expiry timestamp.
 *  2. odooLogin(username, password) calls /api/v1/odoo/odoo-login with the gateway
 *     JWT as Bearer auth + the user-supplied Odoo credentials in the request body.
 *     The backend sets httponly session cookies on success.
 *  3. The exported `api` axios instance auto-attaches the gateway JWT Bearer header
 *     to every request and retries once on 401 (after refreshing the token).
 */

import axios from 'axios'

// ── Storage keys ───────────────────────────────────────────────────────
const TOKEN_KEY = 'gateway_jwt'
const TOKEN_EXP_KEY = 'gateway_jwt_exp'

/** Refresh the token this many seconds before its actual expiry. */
const REFRESH_BUFFER_SECONDS = 60

// Empty in dev (Vite proxy handles routing), full URL in production builds.
// e.g. VITE_API_BASE_URL=https://api.prod.com  → direct HTTPS calls
//      VITE_API_BASE_URL=                        → relative paths → Vite proxy
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

/**
 * Plain axios instance (no interceptors) used for auth-bootstrap calls
 * (fetchGatewayToken, odooLogin). Cannot use `api` here — that would
 * cause circular interceptor calls. baseURL ensures production correctness.
 */
const plainAxios = axios.create({ baseURL: API_BASE })

// ── Token storage helpers ──────────────────────────────────────────────

/**
 * Persist the JWT and its expiry claim in localStorage.
 * Decodes the `exp` claim from the JWT payload (base64 middle segment)
 * without importing a jwt library.
 */
function saveToken(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(TOKEN_EXP_KEY, String(payload.exp))
  } catch {
    // If decode fails (e.g. malformed token), store without expiry tracking
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.removeItem(TOKEN_EXP_KEY)
  }
}

function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * Returns true if the stored token has more than REFRESH_BUFFER_SECONDS
 * of life remaining (i.e. no need to re-fetch yet).
 */
function isTokenFresh() {
  const exp = localStorage.getItem(TOKEN_EXP_KEY)
  if (!exp) return false
  const nowSeconds = Math.floor(Date.now() / 1000)
  return Number(exp) - nowSeconds > REFRESH_BUFFER_SECONDS
}

/** Remove the stored token and its expiry. Call on logout or 401. */
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(TOKEN_EXP_KEY)
  clearSession()
}

// ── Odoo session persistence ────────────────────────────────────────────

const SESSION_KEY = 'odoo_session'

/** Persist the Odoo user session in localStorage for page-refresh recovery. */
export function saveSession(user) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({
    odoo_username: user.odoo_username,
    odoo_user_id: user.odoo_user_id,
  }))
}

/** Return the stored session object, or null if none exists. */
export function getStoredSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** Remove the stored Odoo session. */
export function clearSession() {
  localStorage.removeItem(SESSION_KEY)
}

/**
 * Validate a stored session against the backend.
 * The backend reads the httponly ``odoo_token_{login}`` cookie and returns
 * the decoded user info if it is still valid.
 */
export async function checkSession(login) {
  const res = await api.get('/api/v1/odoo/session', {
    params: { login },
  })
  return res.data  // { odoo_username, odoo_user_id }
}

// ── Gateway JWT fetching ───────────────────────────────────────────────

/**
 * Fetch a fresh gateway JWT from the backend using the API credentials
 * baked into the Vite build (VITE_API_USER / VITE_API_PASSWORD).
 * Uses plain `axios` (not the `api` instance) to avoid circular interceptor calls.
 */
async function fetchGatewayToken() {
  // The backend expects OAuth2PasswordRequestForm — application/x-www-form-urlencoded
  const form = new URLSearchParams()
  form.append('username', import.meta.env.VITE_API_USER)
  form.append('password', import.meta.env.VITE_API_PASSWORD)
  form.append('client_id', import.meta.env.VITE_API_CLIENT_ID)

  const res = await plainAxios.post('/api/v1/auth/token', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

  // Backend returns { access_token: "...", token_type: "Bearer" }
  const token = res.data.access_token
  saveToken(token)
  return token
}

/**
 * Returns a valid gateway token, fetching a fresh one from the backend
 * if none is stored or the stored one is about to expire.
 */
export async function getGatewayToken() {
  if (isTokenFresh()) {
    return getStoredToken()
  }
  return fetchGatewayToken()
}

// ── Odoo user login ────────────────────────────────────────────────────

/**
 * Authenticate the end-user against Odoo.
 * Requires a valid gateway JWT (call getGatewayToken first).
 *
 * On success the backend sets httponly session cookies:
 *   odoo_token_<username>  and  odoo_user_id
 *
 * Returns the full OdooAuthResponse body:
 *   { success, message, jwt_token, expires_in, odoo_user_id, odoo_username }
 */
export async function odooLogin(odooUsername, odooPassword) {
  const token = await getGatewayToken()

  const res = await plainAxios.post(
    '/api/v1/odoo/odoo-login',
    { odoo_username: odooUsername, odoo_password: odooPassword },
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      withCredentials: true, // Required so the browser stores the Set-Cookie headers
    }
  )
  return res.data
}

// ── Pre-configured axios instance for all protected API calls ──────────

/**
 * Use this instance for every call to /api/v1/validate/* and other
 * protected endpoints. It automatically:
 *   - Attaches Authorization: Bearer <gateway-token>
 *   - Sends session cookies (withCredentials)
 *   - On 401: clears the cached token, fetches a new one, retries once
 */
export const api = axios.create({
  baseURL: API_BASE,     // empty in dev (proxy), full URL in production builds
  withCredentials: true, // Always send session cookies set by odoo-login
})

// Request interceptor — attach current gateway token as Bearer
api.interceptors.request.use(async (config) => {
  const token = await getGatewayToken()
  config.headers['Authorization'] = `Bearer ${token}`
  return config
})

// Response interceptor — retry once on 401 after refreshing the token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      clearToken()
      const newToken = await fetchGatewayToken()
      originalRequest.headers['Authorization'] = `Bearer ${newToken}`
      return api(originalRequest)
    }
    return Promise.reject(error)
  }
)

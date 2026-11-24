/** API base URL, resolved at RUNTIME. Accepts "host:port" (e.g. Render private-service hostport) as well as a full URL. */
export function apiBase(): string {
  const raw = (process.env.API_URL ?? "http://127.0.0.1:8000").trim().replace(/\/$/, "");
  return /^https?:\/\//i.test(raw) ? raw : `http://${raw}`;
}

/**
 * Backend API client.
 *
 * All requests go through Next.js rewrites → /api/v1/* → backend:8000/api/v1/*
 * so no CORS configuration is needed on the frontend.
 *
 * Endpoints used:
 *   POST /api/v1/research/start    — kick off a research session
 *   GET  /api/v1/research/:id      — poll session status
 *   GET  /api/v1/reports/:id       — fetch the final report
 */

import type { ResearchSession, WorkflowOutput, ResearchMode } from "@/lib/types";

const BASE = "/api/v1";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Research endpoints
// ---------------------------------------------------------------------------

export async function startResearch(
  query: string,
  mode: ResearchMode = "general",
): Promise<{ session_id: string; status: string; created_at: string }> {
  return request("/research/start", {
    method: "POST",
    body: JSON.stringify({ query, mode }),
  });
}

export async function getResearchSession(
  sessionId: string,
): Promise<ResearchSession> {
  return request(`/research/${sessionId}`);
}

// ---------------------------------------------------------------------------
// Report endpoints
// ---------------------------------------------------------------------------

export async function getReport(reportId: string): Promise<WorkflowOutput> {
  return request<WorkflowOutput>(`/reports/${reportId}`);
}

// ---------------------------------------------------------------------------
// Polling helper
// ---------------------------------------------------------------------------

/**
 * Poll a research session until it reaches a terminal state.
 *
 * Returns a tuple of [promise, cancel].  Call cancel() to stop polling and
 * prevent the promise from resolving — the promise will simply never settle
 * after cancellation (the caller discards it).
 *
 * @param sessionId  Session to watch.
 * @param onUpdate   Called on each poll with the latest session state.
 * @param intervalMs Polling interval in milliseconds (default 2000).
 */
export function pollResearchSession(
  sessionId: string,
  onUpdate: (session: ResearchSession) => void,
  intervalMs = 2000,
): { promise: Promise<ResearchSession>; cancel: () => void } {
  let timer: ReturnType<typeof setInterval> | null = null;

  const promise = new Promise<ResearchSession>((resolve, reject) => {
    timer = setInterval(async () => {
      try {
        const session = await getResearchSession(sessionId);
        onUpdate(session);

        if (session.status === "complete" || session.status === "failed") {
          if (timer !== null) clearInterval(timer);
          resolve(session);
        }
      } catch (err) {
        if (timer !== null) clearInterval(timer);
        reject(err);
      }
    }, intervalMs);
  });

  const cancel = () => {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  };

  return { promise, cancel };
}

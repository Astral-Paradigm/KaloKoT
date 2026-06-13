/// <reference types="vite/client" />

/* ===================================================================
 * KaloKoT API Client
 *
 * All endpoints talk to the FastAPI backend at /api.  Two transport
 * strategies are used:
 *   1. formPost()   — general‑purpose POST with FormData (most calls)
 *   2. raw fetch()  — direct GET or POST for file uploads & plain text
 * =================================================================== */

const API_BASE = "/api";

// ── Transport helpers ───────────────────────────────

/** Fetch with a timeout signal (milliseconds). */
function fetchWithTimeout(url: string, init: RequestInit, ms: number = 60_000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  init.signal = controller.signal;
  return fetch(url, init).finally(() => clearTimeout(timer));
}

/** POST with FormData encoding and a 60‑second timeout.
 * FastAPI expects form params for nearly all endpoints.
 * The return type is determined by the response Content‑Type:
 *   application/pdf  → Blob
 *   audio/mpeg       → Blob
 *   text/plain       → string
 *   anything else    → parsed JSON (generic T)
 */
async function formPost<T>(path: string, data: Record<string, unknown>): Promise<T> {
  const fd = new FormData();
  for (const [k, v] of Object.entries(data)) {
    if (v !== undefined && v !== null) {
      fd.append(k, typeof v === "boolean" ? String(v) : v as string | Blob);
    }
  }
  const res = await fetchWithTimeout(`${API_BASE}${path}`, { method: "POST", body: fd });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/pdf")) return res.blob() as unknown as T;
  if (ct.includes("audio/mpeg"))      return res.blob() as unknown as T;
  if (ct.includes("text/plain"))      return res.text() as unknown as T;
  return res.json() as Promise<T>;
}

// ── Shared request / response types ───────────────

export interface CounselRequest {
  tender_context?: string;
  question: string;
  jurisdiction?: string;
  risk_report?: unknown;
}

export interface CounselResponse {
  answer: string;
  citations?: { source: string; description: string }[];
  suggested_actions?: string[];
  disclaimer?: string;
}

export interface ConstitutionSearchResult {
  child_id: string;
  child_text: string;
  score: number;
  parent_id: string;
  parent_title: string;
  part_title: string;
  path: string[];
}

export interface ConstitutionSearchResponse {
  results: ConstitutionSearchResult[];
  context: string;
}

export interface AnalysisResponse {
  report_id: string;
  overview?: string;
  summary?: string;
  overall_risk?: string;
}

export interface LegalArticle {
  source: string;
  description: string;
  penalty?: string;
  action?: string;
}

export interface LegalSearchResponse {
  results: LegalArticle[];
  context: string;
}

// ── Tender analysis ────────────────────────────────

/** Upload a tender file (PDF / image / text) for corruption‑risk analysis. */
export async function analyzeTender(file: File): Promise<AnalysisResponse> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetchWithTimeout(`${API_BASE}/analyze`, { method: "POST", body: fd });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Upload failed (${res.status}): ${body.slice(0, 200)}`);
  }
  return res.json();
}

/** Analyse pasted tender text (with optional title). */
export async function analyzeTenderText(
  text: string,
  title?: string,
): Promise<AnalysisResponse> {
  return formPost<AnalysisResponse>("/analyze-text", { text, title: title || "Uploaded Tender" });
}

/** Fetch a previously generated report by its ID. */
export async function getReport(reportId: string): Promise<unknown> {
  const res = await fetchWithTimeout(`${API_BASE}/report/${reportId}`);
  if (!res.ok) throw new Error(`Report fetch failed: ${res.status}`);
  return res.json();
}

// ── Legal counsel (chat) ───────────────────────────

/** Ask the Digital Lawyer a legal question (optionally scoped to a tender context). */
export async function counselQuestion(
  req: CounselRequest,
): Promise<CounselResponse> {
  return formPost<CounselResponse>("/counsel", {
    question: req.question,
    tender_context: req.tender_context || "",
    jurisdiction: req.jurisdiction || "np",
  });
}

// ── Constitution search ────────────────────────────

/** Semantic search over the Constitution of Nepal 2015. */
export async function searchConstitution(
  query: string,
  topK: number = 5,
): Promise<ConstitutionSearchResponse> {
  return formPost<ConstitutionSearchResponse>("/constitution-search", {
    query,
    top_k: topK,
    resolve_parents: true,
  });
}

/** Retrieve the full text of the constitution for browsing. */
export async function getConstitutionContext(): Promise<string> {
  const res = await fetchWithTimeout(`${API_BASE}/constitution-context`);
  if (!res.ok) throw new Error(`Constitution fetch failed: ${res.status}`);
  return res.text();
}

// ── Legal database search ──────────────────────────

/** Search case law / statutes by text and jurisdiction. */
export async function searchLegal(
  query: string,
  jurisdiction: string = "NEPAL",
): Promise<LegalSearchResponse> {
  return formPost<LegalSearchResponse>("/legal-search", { query, jurisdiction });
}

/** List available jurisdictions. */
export async function getJurisdictions(): Promise<string[]> {
  const res = await fetchWithTimeout(`${API_BASE}/jurisdictions`);
  if (!res.ok) throw new Error(`Jurisdictions fetch failed: ${res.status}`);
  return res.json();
}

// ── Complaint drafting ────────────────────────────

/** Generate a formal complaint letter PDF from the user's personal details + description. */
export async function draftComplaint(
  name: string,
  permanent_address: string,
  temporary_address: string,
  citizenship_no: string,
  phone: string,
  email: string,
  complaint_description: string,
  complaint_date: string = "",
): Promise<Blob> {
  return formPost<Blob>("/draft-complaint", {
    name,
    permanent_address,
    temporary_address,
    citizenship_no,
    phone,
    email,
    complaint_description,
    complaint_date,
  });
}

/** Generate a legal analysis report PDF for a described issue. */
export async function generateAnalysisReport(issue: string): Promise<Blob> {
  return formPost<Blob>("/analysis-report", { issue });
}

// ── Text‑to‑speech ─────────────────────────────────

/** Convert legal‑counsel text to an MP3 audio blob (ElevenLabs). */
export async function textToSpeech(text: string): Promise<Blob> {
  return formPost<Blob>("/tts", { text });
}

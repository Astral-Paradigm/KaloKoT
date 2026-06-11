/// <reference types="vite/client" />

const API_BASE = "/api";

/** Helper: POST with FormData (FastAPI expects form params for all endpoints). */
async function formPost<T>(path: string, data: Record<string, any>): Promise<T> {
  const fd = new FormData();
  for (const [k, v] of Object.entries(data)) {
    if (v !== undefined && v !== null) {
      fd.append(k, typeof v === "boolean" ? String(v) : v);
    }
  }
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  // Check Content-Type to decide JSON vs blob
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/pdf")) {
    return res.blob() as any;
  }
  if (ct.includes("audio/mpeg")) {
    return res.blob() as any;
  }
  if (ct.includes("text/plain")) {
    return res.text() as any;
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────

export interface CounselRequest {
  tender_context?: string;
  question: string;
  jurisdiction?: string;
  risk_report?: any;
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

// ── API Methods ───────────────────────────────

export async function analyzeTender(file: File): Promise<AnalysisResponse> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/analyze`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function analyzeTenderText(
  text: string,
  title?: string,
): Promise<AnalysisResponse> {
  return formPost<AnalysisResponse>("/analyze-text", { text, title: title || "Uploaded Tender" });
}

export async function getReport(reportId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/report/${reportId}`);
  return res.json();
}

export async function counselQuestion(
  req: CounselRequest,
): Promise<CounselResponse> {
  return formPost<CounselResponse>("/counsel", {
    question: req.question,
    tender_context: req.tender_context || "",
    jurisdiction: req.jurisdiction || "unknown",
  });
}

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

export async function getConstitutionContext(): Promise<string> {
  const res = await fetch(`${API_BASE}/constitution-context`);
  return res.text();
}

export async function searchLegal(
  query: string,
  jurisdiction: string = "NEPAL",
): Promise<LegalSearchResponse> {
  return formPost<LegalSearchResponse>("/legal-search", { query, jurisdiction });
}

export async function getJurisdictions(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/jurisdictions`);
  return res.json();
}

export async function draftComplaint(
  name: string,
  permanent_address: string,
  temporary_address: string,
  citizenship_no: string,
  phone: string,
  email: string,
  complaint_description: string,
): Promise<Blob> {
  return formPost<Blob>("/draft-complaint", {
    name,
    permanent_address,
    temporary_address,
    citizenship_no,
    phone,
    email,
    complaint_description,
  });
}

export async function generateAnalysisReport(issue: string): Promise<Blob> {
  return formPost<Blob>("/analysis-report", { issue });
}

export async function textToSpeech(text: string): Promise<Blob> {
  return formPost<Blob>("/tts", { text });
}

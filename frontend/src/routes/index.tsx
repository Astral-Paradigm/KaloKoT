/* ===================================================================
 * KaloKoT — Home Page
 *
 * Single‑page application hub with four modes:
 *   1. Chat  (FAQ / Digital Lawyer)
 *   2. Tender Review (upload or paste tender for analysis)
 *   3. Complaint (fill details, draft letter PDF)
 *   4. Analysis (describe an issue, generate report PDF)
 *
 * Includes a landing state (mascot + thought bubble) and TTS playback
 * for lawyer messages.
 * =================================================================== */

import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  ArrowUp, FileText, HelpCircle, AlertOctagon, BarChart3,
  BookOpen, Circle, KeyRound, Cpu,
  User, Volume2, VolumeX, AlertTriangle, Download, Edit3,
  MapPin, Lightbulb, MessageCircle, Loader2,
} from "lucide-react";
import mascot from "@/assets/mascot.png";
import {
  counselQuestion,
  textToSpeech,
  analyzeTender,
  analyzeTenderText,
  draftComplaint,
  generateAnalysisReport,
  getProvidersStatus,
  setApiKey,
  getStoredApiKey,
  type CounselResponse,
  type ProvidersStatus,
} from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

// ── Types ──────────────────────────────────────────

type Mode = "chat" | "tender" | "analysis" | "complaint";

interface Message {
  role: "user" | "lawyer";
  text: string;
}

interface FlaggedClause {
  id: string;
  label: string;
  severity: string;
  description: string;
  location: string;
  suggestion: string;
  risk_reason?: string; /* why this clause poses a risk, shown as an expanded note */
}

interface AnalysisResult {
  report_id: string;
  overall_risk: string;
  summary: string;
  section_scores: Record<string, string>;
  flagged_clauses: FlaggedClause[];
}

// ── Risk helpers ───────────────────────────────────

/** Return the oklch colour for a given risk level. */
function riskColor(level: string): string {
  switch (level) {
    case "critical": return "oklch(0.52 0.18 30)";
    case "high":     return "oklch(0.6 0.16 40)";
    case "medium":   return "oklch(0.7 0.14 70)";
    default:         return "oklch(0.6 0.1 150)";
  }
}

/** Return the human‑readable label for a risk level. */
function riskBadge(level: string): string {
  const map: Record<string, string> = {
    critical: "CRITICAL", high: "HIGH",
    medium: "MEDIUM", low: "LOW",
  };
  return map[level] || level.toUpperCase();
}

/** Emoji icon corresponding to severity. */
function severityIcon(sev: string): string {
  switch (sev) {
    case "critical": return "🔴";
    case "high":     return "🟠";
    case "medium":   return "🟡";
    default:         return "🟢";
  }
}

// ── Static data ────────────────────────────────────

/** LLM provider options for the dropdown. */
const providers: { value: string; label: string; keyRequired: boolean }[] = [
  { value: "", label: "Auto", keyRequired: false },
  { value: "gemini", label: "Gemini", keyRequired: true },
  { value: "anthropic", label: "Claude", keyRequired: true },
  { value: "openai", label: "OpenAI", keyRequired: true },
  { value: "openrouter", label: "OpenRouter", keyRequired: true },
  { value: "rule-based", label: "Default", keyRequired: false },
];

/** Sidebar navigation items. */
const navItems: { label: string; icon: React.ComponentType<{ className?: string }>; mode: Mode }[] = [
  { label: "Tender", icon: FileText, mode: "tender" as Mode },
  { label: "Counsel", icon: HelpCircle, mode: "chat" as Mode },
  { label: "Complaint", icon: AlertOctagon, mode: "complaint" as Mode },
  { label: "Analysis", icon: BarChart3, mode: "analysis" as Mode },
  { label: "Constitution", icon: BookOpen, mode: "chat" as Mode },
];

/** Recent activity shown in sidebar. */
const recents: { title: string; time: string }[] = [
  { title: "Tenancy notice review", time: "2h" },
  { title: "Contractor delay claim", time: "yesterday" },
];

/** Suggested quick‑action chips on the landing state. */
const chips: string[] = [
  "Draft a complaint against a noisy neighbour",
  "Summarise this tender document",
];

// ── Component ──────────────────────────────────────

function HomePage() {
  const navigate = useNavigate();

  // ── Mode & chat state ────────────────────────
  const [mode, setMode] = useState<Mode>("chat");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "lawyer",
      text: "Hello, I'm KaloKoT's Digital Lawyer. Ask me anything about tender corruption, your constitutional rights, or how to report a violation. You can also upload a tender for review, or switch to Analysis/Complaint mode.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiProvider, setAiProvider] = useState("rule-based");
  const [providersStatus, setProvidersStatus] = useState<ProvidersStatus | null>(null);
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [keyDialogProvider, setKeyDialogProvider] = useState("");
  const [keyInputValue, setKeyInputValue] = useState("");
 
  // ── TTS state ────────────────────────────────
  const [speakingId, setSpeakingId] = useState<number | null>(null);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [ttsError, setTtsError] = useState<string | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const speakingRef = useRef(false);

  // ── Tender context (carried over to chat) ────
  const [tenderContext, setTenderContext] = useState("");

  // ── Tender Review state ──────────────────────
  const [uploadedFileName, setUploadedFileName] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // ── Complaint state ──────────────────────────
  const [complaintForm, setComplaintForm] = useState({
    name: "", permanent_address: "", temporary_address: "",
    citizenship_no: "", phone: "", email: "", description: "", date: "",
  });
  const [complaintPdf, setComplaintPdf] = useState<Blob | null>(null);
  const [draftingComplaint, setDraftingComplaint] = useState(false);

  // ── Analysis report state ────────────────────
  const [issueText, setIssueText] = useState("");
  const [analysisPdf, setAnalysisPdf] = useState<Blob | null>(null);
  const [generatingAnalysis, setGeneratingAnalysis] = useState(false);

  // ── Refs ─────────────────────────────────────
  const chatEnd = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Effects ──────────────────────────────────

  /** Auto‑scroll chat to the latest message. */
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /** Fetch LLM provider status on mount. */
  useEffect(() => {
    getProvidersStatus()
      .then(setProvidersStatus)
      .catch(() => setProvidersStatus(null));
  }, []);



  /** Prime the AudioContext on first user gesture (required by browsers). */
  useEffect(() => {
    const primeAudio = () => {
      if (audioCtxRef.current) return;
      try {
        const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
        ctx.resume();
        audioCtxRef.current = ctx;
      } catch { /* no audio — safe to ignore */ }
    };
    document.addEventListener("pointerdown", primeAudio, { once: true });
    return () => document.removeEventListener("pointerdown", primeAudio);
  }, []);

  // ── Chat handlers ────────────────────────────

  /** Send the current input to the counsel backend. */
  const sendMessage = useCallback(async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const res: CounselResponse = await counselQuestion({
        question: q,
        tender_context: tenderContext,
      }, aiProvider, messages);
      const answer = res.answer;
      setMessages((m) => [...m, { role: "lawyer", text: answer }]);
    } catch {
      const fallback = "I need my legal backend connected to give you a precise answer. Please make sure the server is running, or try again.";
      setMessages((m) => [...m, { role: "lawyer", text: fallback }]);
    }
    setLoading(false);
  }, [input, loading, tenderContext, aiProvider]);

  /** Read a lawyer message aloud via TTS. */
  const handleTts = useCallback(async (text: string, idx: number) => {
    if (speakingRef.current) return;
    speakingRef.current = true;
    setSpeakingId(idx);
    setTtsError(null);
    try {
      const blob = await textToSpeech(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => { setSpeakingId(null); speakingRef.current = false; URL.revokeObjectURL(url); };
      await audio.play();
    } catch (err: unknown) {
      setSpeakingId(null);
      speakingRef.current = false;
      if (err instanceof Error && err.message.includes("503")) {
        setTtsError("TTS unavailable — add ELEVENLABS_API_KEY to .env");
      } else if (err instanceof DOMException && err.name === "NotAllowedError") {
        setAudioBlocked(true);
      } else {
        setTtsError("Audio playback failed — check server");
      }
    }
  }, []);

  // ── Tender Review handlers ────────────────────

  /** Analyse an uploaded tender file. */
  const handleFileUpload = useCallback(async (file: File) => {
    setUploadedFileName(file.name);
    setAnalyzing(true);
    setAnalysisResult(null);
    setAnalysisError(null);
    try { setAnalysisResult(await analyzeTender(file) as unknown as AnalysisResult); }
    catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setAnalysisError(msg);
      console.error("Tender analysis failed", e);
    }
    setAnalyzing(false);
  }, []);

  /** Analyse pasted tender text. */
  const handleAnalyzeText = useCallback(async () => {
    if (!pasteText.trim()) return;
    setUploadedFileName("Pasted text");
    setAnalyzing(true);
    setAnalysisResult(null);
    setAnalysisError(null);
    try { setAnalysisResult(await analyzeTenderText(pasteText) as unknown as AnalysisResult); }
    catch (e) {
      const msg = e instanceof Error ? e.message : "Analysis failed";
      setAnalysisError(msg);
      console.error("Analyze text failed", e);
    }
    setAnalyzing(false);
  }, [pasteText]);

  /** React to the file‑input change event. */
  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileUpload(file);
    },
    [handleFileUpload],
  );

  /** Send the analysis summary to the chat lawyer and switch to chat mode. */
  const discussWithLawyer = useCallback(() => {
    if (analysisResult) setTenderContext(analysisResult.summary);
    setMode("chat");
  }, [analysisResult]);

  // ── Complaint handlers ───────────────────────

  /** Draft a complaint letter PDF from form data. */
  const handleDraftComplaint = useCallback(async () => {
    if (!complaintForm.description.trim()) return;
    setDraftingComplaint(true);
    try {
      const blob = await draftComplaint(
        complaintForm.name, complaintForm.permanent_address,
        complaintForm.temporary_address, complaintForm.citizenship_no,
        complaintForm.phone, complaintForm.email, complaintForm.description,
        complaintForm.date,
      );
      setComplaintPdf(blob);
    } catch { console.error("Draft complaint failed"); }
    setDraftingComplaint(false);
  }, [complaintForm]);

  /** Download the drafted complaint PDF. */
  const handleDownloadComplaint = useCallback(() => {
    if (!complaintPdf) return;
    const url = URL.createObjectURL(complaintPdf);
    const a = document.createElement("a");
    a.href = url; a.download = "complaint-letter.pdf"; a.click();
    URL.revokeObjectURL(url);
  }, [complaintPdf]);

  // ── Analysis Report handlers ─────────────────

  /** Generate a legal analysis PDF for the described issue. */
  const handleGenerateAnalysis = useCallback(async () => {
    if (!issueText.trim()) return;
    setGeneratingAnalysis(true);
    try { setAnalysisPdf(await generateAnalysisReport(issueText)); }
    catch { console.error("Generate analysis failed"); }
    setGeneratingAnalysis(false);
  }, [issueText]);

  /** Download the generated analysis PDF. */
  const handleDownloadAnalysis = useCallback(() => {
    if (!analysisPdf) return;
    const url = URL.createObjectURL(analysisPdf);
    const a = document.createElement("a");
    a.href = url; a.download = "analysis-report.pdf"; a.click();
    URL.revokeObjectURL(url);
  }, [analysisPdf]);

  // ── Shared input bar handler ─────────────────

  /** Submit on Enter (without Shift). */
  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  /** True when in chat mode with only the opening lawyer message — shows the landing view. */
  const isLanding = mode === "chat" && messages.length === 1 && messages[0].role === "lawyer";

  // ═══════════════════════════════════════════════════
  //  RENDER
  // ═══════════════════════════════════════════════════

  return (
    <div className="min-h-screen w-full text-ink">

      {/* ── Header ── */}
      <header className="glass sticky top-3 z-30 mx-3 flex h-14 items-center justify-between gap-3 rounded-2xl px-4 sm:px-5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-serif text-xl sm:text-2xl italic tracking-tight text-deep">
            KaloKoT
          </span>
          <span className="hidden sm:inline font-mono text-[10px] uppercase tracking-[0.2em] text-ink/50">
            v.01
          </span>
        </div>
        <nav className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink/50 flex items-center gap-1">
            <Cpu className="h-3 w-3" />
            {aiProvider
              ? providers?.find((p) => p.value === aiProvider)?.label ?? aiProvider
              : "Auto"}
          </span>
          <div className="h-8 w-8 shrink-0 rounded-full bg-deep text-paper grid place-items-center font-mono text-xs">
            K
          </div>
        </nav>
      </header>

      {/* ── API Key Entry Dialog ── */}
      <Dialog open={keyDialogOpen} onOpenChange={setKeyDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="h-4 w-4" />
              {keyDialogProvider
                ? providers.find((p) => p.value === keyDialogProvider)?.label ?? keyDialogProvider
                : ""}{" "}
              API Key
            </DialogTitle>
            <DialogDescription>
              Enter your API key for this provider. The key is stored locally in your browser
              and sent securely with each request.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <input
              type="password"
              value={keyInputValue}
              onChange={(e) => setKeyInputValue(e.target.value)}
              placeholder={`Paste your ${keyDialogProvider ? providers.find((p) => p.value === keyDialogProvider)?.label ?? keyDialogProvider : ""} API key here...`}
              className="w-full p-2.5 rounded-lg text-sm outline-none"
              style={{
                border: "1px solid color-mix(in oklab, var(--ink) 15%, transparent)",
                background: "color-mix(in oklab, var(--paper-dark) 50%, transparent)",
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && keyInputValue.trim()) {
                  setApiKey(keyDialogProvider, keyInputValue.trim());
                  setAiProvider(keyDialogProvider);
                  setKeyDialogOpen(false);
                }
              }}
            />
          </div>
          <DialogFooter className="flex gap-2">
            <button
              onClick={() => setKeyDialogOpen(false)}
              className="px-4 py-2 rounded-lg text-xs"
              style={{
                border: "1px solid color-mix(in oklab, var(--ink) 20%, transparent)",
                color: "color-mix(in oklab, var(--ink) 55%, transparent)",
              }}
            >
              Cancel
            </button>
            <button
              onClick={async () => {
                if (!keyInputValue.trim()) return;
                await setApiKey(keyDialogProvider, keyInputValue.trim());
                setAiProvider(keyDialogProvider);
                setKeyDialogOpen(false);
                // Refresh provider status
                getProvidersStatus()
                  .then(setProvidersStatus)
                  .catch(() => {});
              }}
              disabled={!keyInputValue.trim()}
              className="px-4 py-2 rounded-lg text-xs font-semibold transition"
              style={{
                background: keyInputValue.trim() ? "var(--gold)" : "color-mix(in oklab, var(--ink) 10%, transparent)",
                color: keyInputValue.trim() ? "var(--paper)" : "color-mix(in oklab, var(--ink) 40%, transparent)",
                cursor: keyInputValue.trim() ? "pointer" : "not-allowed",
              }}
            >
              Save Key
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Two‑column layout ── */}
      <div className="mx-3 mt-3 flex gap-3" style={{ minHeight: "calc(100vh - 5rem)" }}>

        {/* ── Sidebar (desktop only) ── */}
        <aside className="glass hidden w-64 shrink-0 flex-col rounded-2xl p-4 md:flex">
          <div className="mb-4">
            <p className="text-kicker mb-2 px-2">Sections</p>
            <ul className="space-y-0.5">
              {navItems.map((item) => (
                <li key={item.label}>
                  <button
                    onClick={() => {
                      if (item.label === "Constitution") {
                        navigate({ to: "/constitution" });
                      } else {
                        setMode(item.mode);
                      }
                    }}
                    className={`group interactive flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                      item.label === "Constitution"
                        ? "text-ink/75 hover:bg-paper-dark/60"
                        : mode === item.mode
                          ? "bg-ink/8 text-deep font-medium"
                          : "text-ink/75 hover:bg-paper-dark/60"
                    }`}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="h-px bg-ink/10 my-2" />

          <div className="flex-1 overflow-hidden">
            <p className="text-kicker mb-2 px-2">Recent</p>
            <ul className="space-y-1">
              {recents.map((r) => (
                <li key={r.title} className="rounded-lg px-3 py-2 hover:bg-paper-dark/60 cursor-pointer">
                  <p className="text-sm text-ink/80 truncate">{r.title}</p>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-ink/40">{r.time}</p>
                </li>
              ))}
            </ul>
          </div>



          {/* Live‑clerk indicator */}
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-ink/10 px-3 py-2 bg-paper/40">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gold opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-gold" />
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink/60">
              Live clerk
            </span>
          </div>
        </aside>

        {/* ── Main stage ── */}
        <main className="relative flex-1 rounded-2xl overflow-hidden">

          {/* Gold glow aura */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(520px 360px at 50% 38%, rgba(201,168,76,0.28), transparent 65%)",
            }}
          />

          <div className="relative flex h-full flex-col items-center justify-between gap-6 py-6 px-4 sm:py-10 sm:px-6">

            {/* ── Content area ── */}
            <div className="flex flex-1 flex-col items-center w-full overflow-y-auto animate-fade-in" key={mode}>

              {/* ═══ LANDING STATE (chat mode, only greeting) ═══ */}
              {isLanding && (
                <div className="flex flex-1 flex-col items-center justify-center w-full">

                  {/* Mascot + thought bubble */}
                  <div className="relative flex flex-col md:flex-row items-center md:items-center justify-center gap-5 md:gap-10 w-full max-w-3xl">

                    {/* Warm halo */}
                    <div
                      aria-hidden
                      className="absolute left-1/2 top-1/2 -z-10 h-[420px] w-[420px] md:h-[520px] md:w-[640px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl animate-fade-in"
                      style={{
                        background:
                          "radial-gradient(ellipse at 50% 45%, rgba(201,168,76,0.32) 0%, rgba(201,168,76,0.12) 40%, transparent 72%)",
                      }}
                    />

                    {/* Mascot */}
                    <div className="relative flex shrink-0 flex-col items-center animate-slide-up delay-100">
                      <div
                        aria-hidden
                        className="absolute -bottom-2 left-1/2 -z-10 h-8 w-[160px] -translate-x-1/2 rounded-[50%] blur-xl"
                        style={{ background: "radial-gradient(ellipse, rgba(13,13,13,0.35), transparent 70%)" }}
                      />
                      <img
                        src={mascot}
                        alt="KaloKoT, the pixel-art judge mascot"
                        width={196}
                        height={284}
                        className="pixelated h-[180px] sm:h-[220px] md:h-[280px] w-auto drop-shadow-[0_24px_20px_rgba(13,13,13,0.22)]"
                      />
                      <p className="mt-3 text-kicker">Kalokot · in chambers</p>
                    </div>

                    {/* Thought bubble */}
                    <div className="relative w-full max-w-sm animate-slide-up delay-200">
                      <div className="absolute -top-4 left-1/2 -translate-x-1/2 flex md:hidden items-center gap-1.5">
                        <span className="glass block h-1.5 w-1.5 rounded-full" />
                        <span className="glass block h-2.5 w-2.5 rounded-full" />
                        <span className="glass block h-3.5 w-3.5 rounded-full" />
                      </div>
                      <div className="absolute -left-6 bottom-6 hidden md:flex flex-col items-center gap-1.5">
                        <span className="glass block h-2 w-2 rounded-full" />
                        <span className="glass block h-3 w-3 rounded-full" />
                        <span className="glass block h-4 w-4 rounded-full" />
                      </div>

                      <div className="glass rounded-3xl px-5 py-4 sm:px-6 sm:py-5">
                        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold/90 mb-2">
                          Counsel's note
                        </p>
                        <p className="font-serif text-sm sm:text-base md:text-lg leading-relaxed text-deep">
                          Ask me about a <em>tender clause</em>, a faulty service complaint, or how a statute
                          reads in your situation — I'll cite the section and lay out your options.
                        </p>
                        <div className="mt-4 flex items-center gap-2">
                          <span className="text-kicker">Hearing open</span>
                          <span className="h-px flex-1 bg-ink/15" />
                          <span className="font-mono text-[10px] text-ink/45">§ Art. 21</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Suggested chips */}
                  <div className="mt-8 sm:mt-10 flex flex-wrap items-center justify-center gap-2 max-w-xl animate-slide-up delay-300">
                    {chips.map((c) => (
                      <button
                        key={c}
                        onClick={() => setInput(c)}
                        className="interactive glass rounded-full px-3.5 py-2 text-[11px] sm:text-xs text-ink/80 hover:text-deep transition"
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* ═══ CHAT MESSAGES (once user has interacted) ═══ */}
              {mode === "chat" && !isLanding && (
                <div className="w-full max-w-3xl space-y-3">
                  {messages.map((msg, i) => (
                      <div
                        key={i}
                        className="flex gap-2.5 items-start message-bubble"
                      style={{ flexDirection: msg.role === "user" ? "row-reverse" : "row" }}
                    >
                      {msg.role === "lawyer" && (
                        <div
                          className="w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-xs mt-1"
                          style={{
                            background: "color-mix(in oklab, var(--gold) 18%, transparent)",
                            border: "1px solid color-mix(in oklab, var(--gold) 25%, transparent)",
                          }}
                        >
                          <img src={mascot} alt="KaloKoT" className="w-6 h-6 rounded-full object-cover" />
                        </div>
                      )}
                      {msg.role === "user" && (
                        <div
                          className="w-8 h-8 shrink-0 rounded-full flex items-center justify-center mt-1"
                          style={{
                            background: "color-mix(in oklab, var(--ink) 8%, transparent)",
                          }}
                        >
                          <User className="h-4 w-4" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }} />
                        </div>
                      )}
                      <div
                        className="relative text-sm leading-relaxed max-w-[75%]"
                        style={msg.role === "lawyer" ? {
                          background: "var(--paper)",
                          border: "1px solid color-mix(in oklab, var(--gold) 20%, transparent)",
                          borderRadius: "20px 20px 20px 4px",
                          padding: "14px 18px",
                          boxShadow: "0 4px 16px rgba(13,13,13,0.06), 0 1px 3px rgba(13,13,13,0.04)",
                          whiteSpace: "pre-wrap",
                        } : {
                          background: "color-mix(in oklab, var(--ink) 6%, transparent)",
                          border: "1px solid color-mix(in oklab, var(--ink) 12%, transparent)",
                          borderRadius: "20px 20px 4px 20px",
                          padding: "10px 14px",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {msg.text.split(/\*\*(.+?)\*\*/g).map((part, pi) =>
                          pi % 2 === 1 ? <strong key={pi}>{part}</strong> : part
                        )}
                        {msg.role === "lawyer" && (
                          <div className="flex items-center gap-2 mt-2 pt-1.5 border-t border-ink/10">
                            <button
                              onClick={() => handleTts(msg.text, i)}
                              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition hover:bg-ink/5 active:scale-95"
                              style={{
                                color: speakingId === i ? "var(--gold)" : "color-mix(in oklab, var(--ink) 50%, transparent)",
                              }}
                              title={speakingId === i ? "Playing..." : "Read aloud"}
                            >
                              {speakingId === i ? <Volume2 className="h-3 w-3" /> : <Volume2 className="h-3 w-3" />} {speakingId === i ? "Playing..." : "Listen"}
                            </button>
                            <span className="font-mono text-[9px] uppercase tracking-wider" style={{ color: "color-mix(in oklab, var(--ink) 35%, transparent)" }}>
                              KaloKoT AI
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex gap-1.5 items-center text-gold text-xs pl-10">
                      <span>Thinking</span>
                      <span className="inline-flex gap-[3px]">
                        {[0, 1, 2].map((d) => (
                          <span
                            key={d}
                            className="w-1.5 h-1.5 rounded-full bg-gold"
                            style={{ animation: `pulse-dot 1.2s ${d * 0.3}s infinite` }}
                          />
                        ))}
                      </span>
                    </div>
                  )}
                  <div ref={chatEnd} />
                </div>
              )}

              {/* ═══ Audio blocked / TTS error indicator ═══ */}
              {audioBlocked && mode === "chat" && (
                <div
                  className="flex items-center gap-2 px-5 py-1.5 text-xs rounded-lg mb-2"
                  style={{
                    color: "var(--gold)",
                    background: "color-mix(in oklab, var(--gold) 10%, transparent)",
                    border: "1px solid color-mix(in oklab, var(--gold) 20%, transparent)",
                  }}
                >
                  <VolumeX className="h-3 w-3 shrink-0" />
                  <span>Click any button to enable audio playback</span>
                  <button
                    onClick={() => { new Audio(); setAudioBlocked(false); }}
                    className="ml-auto px-2 py-0.5 rounded text-[10px]"
                    style={{
                      background: "color-mix(in oklab, var(--gold) 20%, transparent)",
                      border: "1px solid color-mix(in oklab, var(--gold) 30%, transparent)",
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              )}
              {ttsError && mode === "chat" && (
                <div
                  className="flex items-center gap-2 px-5 py-1.5 text-xs rounded-lg mb-2"
                  style={{
                    color: "var(--gold)",
                    background: "color-mix(in oklab, var(--gold) 10%, transparent)",
                    border: "1px solid color-mix(in oklab, var(--gold) 20%, transparent)",
                  }}
                >
                  <AlertTriangle className="h-3 w-3 shrink-0" />
                  <span>{ttsError}</span>
                  <button
                    onClick={() => setTtsError(null)}
                    className="ml-auto px-2 py-0.5 rounded text-[10px]"
                    style={{
                      background: "color-mix(in oklab, var(--gold) 20%, transparent)",
                      border: "1px solid color-mix(in oklab, var(--gold) 30%, transparent)",
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* ═══ TENDER REVIEW MODE ═══ */}
              {mode === "tender" && (
                <div className="w-full max-w-3xl space-y-4">
                  {!analysisResult && !analyzing && (
                    <>
                      {/* Upload zone */}
                      <div
                        className="border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition"
                        style={{ borderColor: "color-mix(in oklab, var(--ink) 20%, transparent)" }}
                        onClick={() => fileInput.current?.click()}
                        onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = "var(--gold)"; }}
                        onDragLeave={(e) => { e.currentTarget.style.borderColor = "color-mix(in oklab, var(--ink) 20%, transparent)"; }}
                        onDrop={(e) => {
                          e.preventDefault();
                          const file = e.dataTransfer.files?.[0];
                          if (file) handleFileUpload(file);
                        }}
                      >
                        <input
                          ref={fileInput}
                          type="file"
                          accept=".pdf,.txt,.html,.htm,.jpg,.jpeg,.png,.gif,.webp"
                          style={{ display: "none" }}
                          onChange={handleFileChange}
                        />
                        <FileText className="h-10 w-10 mb-2 mx-auto" style={{ color: "color-mix(in oklab, var(--gold) 60%, transparent)" }} />
                        <div className="font-semibold mb-1 text-sm">Upload a tender document (PDF, TXT, HTML, Images)</div>
                        <div className="text-xs" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                          Drag & drop or click to browse
                        </div>
                      </div>

                      {/* OR divider */}
                      <div className="flex items-center gap-3 text-xs" style={{ color: "color-mix(in oklab, var(--ink) 45%, transparent)" }}>
                        <div className="flex-1 h-px" style={{ background: "color-mix(in oklab, var(--ink) 15%, transparent)" }} />
                        OR PASTE TEXT
                        <div className="flex-1 h-px" style={{ background: "color-mix(in oklab, var(--ink) 15%, transparent)" }} />
                      </div>

                      {/* Paste text area */}
                      <textarea
                        value={pasteText}
                        onChange={(e) => setPasteText(e.target.value)}
                        placeholder="Paste the tender text here..."
                        className="w-full min-h-[120px] p-3 rounded-lg text-sm resize-y outline-none"
                        style={{
                          border: "1px solid color-mix(in oklab, var(--ink) 15%, transparent)",
                          background: "color-mix(in oklab, var(--paper-dark) 50%, transparent)",
                        }}
                      />
                      <button
                        onClick={handleAnalyzeText}
                        disabled={!pasteText.trim()}
                        className="px-5 py-2.5 rounded-lg text-sm font-semibold self-start transition"
                        style={{
                          background: pasteText.trim() ? "var(--gold)" : "color-mix(in oklab, var(--ink) 10%, transparent)",
                          color: pasteText.trim() ? "var(--paper)" : "color-mix(in oklab, var(--ink) 40%, transparent)",
                          cursor: pasteText.trim() ? "pointer" : "not-allowed",
                        }}
                      >
                        Analyze Text
                      </button>
                    </>
                  )}

                  {/* Analyzing spinner */}
                  {analyzing && (
                    <div className="text-center py-10">
                      <div
                        className="w-10 h-10 rounded-full mx-auto mb-4"
                        style={{
                          border: "3px solid color-mix(in oklab, var(--ink) 10%, transparent)",
                          borderTop: "3px solid var(--gold)",
                          animation: "spin 0.8s linear infinite",
                        }}
                      />
                      <div className="text-sm" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>Analyzing tender...</div>
                      <div className="text-xs mt-1" style={{ color: "color-mix(in oklab, var(--ink) 40%, transparent)" }}>{uploadedFileName}</div>
                    </div>
                  )}

                  {/* Error banner */}
                  {analysisError && !analyzing && (
                    <div
                      className="p-3 rounded-lg text-sm"
                      style={{
                        background: "color-mix(in oklab, #c0392b 10%, transparent)",
                        border: "1px solid color-mix(in oklab, #c0392b 25%, transparent)",
                      }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <AlertTriangle className="h-4 w-4" style={{ color: "#c0392b" }} />
                        <span className="font-semibold text-sm">Analysis Failed</span>
                      </div>
                      <div className="text-xs" style={{ color: "color-mix(in oklab, var(--ink) 65%, transparent)" }}>
                        {analysisError}
                      </div>
                      <button
                        onClick={() => { setAnalysisError(null); setUploadedFileName(""); }}
                        className="mt-2 text-xs px-2.5 py-1 rounded"
                        style={{
                          border: "1px solid color-mix(in oklab, var(--ink) 20%, transparent)",
                          color: "color-mix(in oklab, var(--ink) 55%, transparent)",
                        }}
                      >
                        Try again
                      </button>
                    </div>
                  )}

                  {/* Analysis Results */}
                  {analysisResult && !analyzing && (
                    <div className="space-y-4">
                      {/* Risk Badge */}
                      <div className="flex items-center gap-3">
                        <div
                          className="px-4 py-1.5 rounded-full text-xs font-bold tracking-wider text-white"
                          style={{ background: riskColor(analysisResult.overall_risk) }}
                        >
                          {riskBadge(analysisResult.overall_risk)} RISK
                        </div>
                        <div className="text-xs" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                          {uploadedFileName}
                        </div>
                      </div>

                      {/* Summary */}
                      <div
                        className="p-3 rounded-lg text-sm"
                        style={{
                          background: "color-mix(in oklab, var(--paper-dark) 50%, transparent)",
                          border: "1px solid color-mix(in oklab, var(--ink) 10%, transparent)",
                        }}
                      >
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                          Summary
                        </div>
                        <div style={{ whiteSpace: "pre-wrap" }}>{analysisResult.summary}</div>
                      </div>

                      {/* Section Scores */}
                      <div>
                        <div className="text-xs uppercase tracking-wider mb-2" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                          Section Risk Scores
                        </div>
                        {Object.entries(analysisResult.section_scores || {}).map(([section, level]) => (
                          <div key={section} className="flex items-center gap-2.5 mb-1.5">
                            <div className="flex-[0_0_120px] text-xs capitalize" style={{ color: "color-mix(in oklab, var(--ink) 65%, transparent)" }}>
                              {section.replace(/_/g, " ")}
                            </div>
                            <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "color-mix(in oklab, var(--ink) 10%, transparent)" }}>
                              <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{
                                  width: level === "critical" ? "100%" : level === "high" ? "75%" : level === "medium" ? "50%" : "25%",
                                  background: riskColor(level),
                                }}
                              />
                            </div>
                            <div className="flex-[0_0_60px] text-[11px] font-semibold text-right" style={{ color: riskColor(level) }}>
                              {level.toUpperCase()}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Flagged Clauses */}
                      <div>
                        <div className="text-xs uppercase tracking-wider mb-2" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                          Flagged Clauses ({analysisResult.flagged_clauses.length})
                        </div>
                        {analysisResult.flagged_clauses.map((clause) => (
                          <div
                            key={clause.id}
                            className="p-3 rounded-lg mb-2"
                            style={{
                              background: "color-mix(in oklab, var(--paper-dark) 40%, transparent)",
                              border: `1px solid ${riskColor(clause.severity)}40`,
                            }}
                          >
                            <div className="flex items-center gap-2 mb-1.5">
                              <span>{severityIcon(clause.severity)}</span>
                              <span className="font-semibold text-sm">{clause.label}</span>
                              <span
                                className="ml-auto text-[10px] px-1.5 py-0.5 rounded text-white"
                                style={{ background: riskColor(clause.severity) }}
                              >
                                {clause.severity.toUpperCase()}
                              </span>
                            </div>
                            {clause.location && (
                              <div className="flex items-center gap-1 text-xs mb-1" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                                <MapPin className="h-3 w-3 shrink-0" /> {clause.location}
                              </div>
                            )}
                            <div className="text-xs mb-1.5">{clause.description}</div>
                            {clause.risk_reason && (
                              <div
                                className="text-xs p-2 rounded mb-1.5"
                                style={{
                                  background: "color-mix(in oklab, var(--gold) 6%, transparent)",
                                  border: "1px solid color-mix(in oklab, var(--gold) 12%, transparent)",
                                  color: "color-mix(in oklab, var(--ink) 85%, transparent)",
                                }}
                              >
                                <AlertTriangle className="h-3 w-3 inline-block mr-1 shrink-0" /> <strong>Why this matters:</strong> {clause.risk_reason}
                              </div>
                            )}
                            {clause.suggestion && (
                              <div
                                className="text-xs p-1.5 rounded"
                                style={{
                                  color: "var(--gold)",
                                  background: "color-mix(in oklab, var(--gold) 8%, transparent)",
                                  border: "1px solid color-mix(in oklab, var(--gold) 15%, transparent)",
                                }}
                              >
                                <Lightbulb className="h-3 w-3 inline-block mr-1 shrink-0" /> {clause.suggestion}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Action buttons */}
                      <button
                        onClick={discussWithLawyer}
                        className="px-5 py-2.5 rounded-lg text-sm font-semibold self-center"
                        style={{
                          border: "1px solid color-mix(in oklab, var(--gold) 35%, transparent)",
                          background: "color-mix(in oklab, var(--gold) 10%, transparent)",
                          color: "var(--gold)",
                        }}
                      >
                        <MessageCircle className="h-4 w-4 inline-block mr-1.5" />Discuss this with the Digital Lawyer
                      </button>
                      <button
                        onClick={() => { setAnalysisResult(null); setUploadedFileName(""); setPasteText(""); setAnalysisError(null); }}
                        className="px-4 py-2 rounded-lg text-xs self-center"
                        style={{
                          border: "1px solid color-mix(in oklab, var(--ink) 20%, transparent)",
                          background: "transparent",
                          color: "color-mix(in oklab, var(--ink) 55%, transparent)",
                        }}
                      >
                        Analyze another tender
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* ═══ ANALYSIS MODE ═══ */}
              {mode === "analysis" && (
                <div className="w-full max-w-3xl space-y-3">
                  <div className="text-xs mb-1" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                    Describe the legal issue or tender concern you'd like analyzed.
                  </div>
                  <textarea
                    value={issueText}
                    onChange={(e) => setIssueText(e.target.value)}
                    placeholder="e.g., A road construction contract was awarded at 40% above market rate with no competitive bidding..."
                    className="w-full min-h-[150px] p-3 rounded-lg text-sm resize-y outline-none"
                    style={{
                      border: "1px solid color-mix(in oklab, var(--ink) 15%, transparent)",
                      background: "color-mix(in oklab, var(--paper-dark) 50%, transparent)",
                    }}
                  />
                  <button
                    onClick={handleGenerateAnalysis}
                    disabled={!issueText.trim() || generatingAnalysis}
                    className="px-5 py-2.5 rounded-lg text-sm font-semibold self-start transition"
                    style={{
                      background: !issueText.trim() || generatingAnalysis
                        ? "color-mix(in oklab, var(--ink) 10%, transparent)"
                        : "var(--gold)",
                      color: !issueText.trim() || generatingAnalysis
                        ? "color-mix(in oklab, var(--ink) 40%, transparent)"
                        : "var(--paper)",
                      cursor: !issueText.trim() || generatingAnalysis ? "not-allowed" : "pointer",
                    }}
                  >
                    {generatingAnalysis ? "Generating..." : "Generate Analysis Report"}
                  </button>
                  {analysisPdf && (
                    <button
                      onClick={handleDownloadAnalysis}
                      className="px-5 py-2.5 rounded-lg text-sm font-semibold self-start"
                      style={{
                        border: "1px solid color-mix(in oklab, var(--gold) 35%, transparent)",
                        background: "color-mix(in oklab, var(--gold) 10%, transparent)",
                        color: "var(--gold)",
                      }}
                    >
                      <Download className="h-4 w-4 inline-block mr-1.5" />Download Analysis Report (PDF)
                    </button>
                  )}
                </div>
              )}

              {/* ═══ COMPLAINT MODE ═══ */}
              {mode === "complaint" && (
                <div className="w-full max-w-3xl space-y-3">
                  <div className="text-xs mb-1" style={{ color: "color-mix(in oklab, var(--ink) 50%, transparent)" }}>
                    Fill in your details and describe the complaint. The Digital Lawyer will draft a formal complaint letter.
                  </div>

                  {(["name", "permanent_address", "temporary_address", "citizenship_no", "phone", "email", "date"] as const).map((field) => (
                    <input
                      key={field}
                      type={field === "email" ? "email" : field === "date" ? "date" : "text"}
                      value={complaintForm[field]}
                      onChange={(e) => setComplaintForm((f) => ({ ...f, [field]: e.target.value }))}
                      placeholder={
                        field === "name" ? "Full Name"
                        : field === "permanent_address" ? "Permanent Address"
                        : field === "temporary_address" ? "Temporary Address"
                        : field === "citizenship_no" ? "Citizenship No."
                        : field === "phone" ? "Phone"
                        : field === "date" ? "Complaint Date"
                        : "Email"
                      }
                      className="w-full p-2.5 rounded-lg text-sm outline-none"
                      style={{
                        border: "1px solid color-mix(in oklab, var(--ink) 15%, transparent)",
                        background: "color-mix(in oklab, var(--paper-dark) 50%, transparent)",
                      }}
                    />
                  ))}

                  <textarea
                    value={complaintForm.description}
                    onChange={(e) => setComplaintForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Describe the complaint in detail..."
                    className="w-full min-h-[120px] p-3 rounded-lg text-sm resize-y outline-none"
                    style={{
                      border: "1px solid color-mix(in oklab, var(--ink) 15%, transparent)",
                      background: "color-mix(in oklab, var(--paper-dark) 50%, transparent)",
                    }}
                  />

                  <button
                    onClick={handleDraftComplaint}
                    disabled={!complaintForm.description.trim() || draftingComplaint}
                    className="px-5 py-2.5 rounded-lg text-sm font-semibold self-start transition"
                    style={{
                      background: !complaintForm.description.trim() || draftingComplaint
                        ? "color-mix(in oklab, var(--ink) 10%, transparent)"
                        : "var(--gold)",
                      color: !complaintForm.description.trim() || draftingComplaint
                        ? "color-mix(in oklab, var(--ink) 40%, transparent)"
                        : "var(--paper)",
                      cursor: !complaintForm.description.trim() || draftingComplaint ? "not-allowed" : "pointer",
                    }}
                  >
                    {draftingComplaint ? "Drafting..." : <><Edit3 className="h-4 w-4 inline-block mr-1.5" />Draft Complaint Letter</>}
                  </button>

                  {complaintPdf && (
                    <button
                      onClick={handleDownloadComplaint}
                      className="px-5 py-2.5 rounded-lg text-sm font-semibold self-start"
                      style={{
                        border: "1px solid color-mix(in oklab, var(--gold) 35%, transparent)",
                        background: "color-mix(in oklab, var(--gold) 10%, transparent)",
                        color: "var(--gold)",
                      }}
                    >
                      <Download className="h-4 w-4 inline-block mr-1.5" />Download Complaint Letter (PDF)
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* ── Input bar (always visible) ── */}
            <div className="w-full max-w-2xl animate-slide-up delay-500">
              <form
                onSubmit={(e) => { e.preventDefault(); sendMessage(); }}
                className="glass flex items-center gap-1 rounded-full pl-3 pr-1.5 py-1.5 transition-all duration-200 focus-within:shadow-[0_0_0_2px_rgba(201,168,76,0.3)]"
              >
                <select
                  value={aiProvider}
                  onChange={(e) => {
                    const val = e.target.value;
                    const prov = providers.find((p) => p.value === val);
                    if (!val || !prov) { setAiProvider(val || ""); return; }
                    if (!prov.keyRequired) { setAiProvider(val); return; }
                    if (getStoredApiKey(val)) { setAiProvider(val); return; }
                    if (providersStatus?.providers?.[val]) { setAiProvider(val); return; }
                    setKeyDialogProvider(val);
                    setKeyInputValue("");
                    setKeyDialogOpen(true);
                  }}
                  className="shrink-0 bg-transparent text-[12px] font-mono outline-none cursor-pointer mr-1 font-bold tracking-wider px-1.5 py-0.5 rounded"
                  style={{
                    color: aiProvider
                      ? "var(--gold)"
                      : "color-mix(in oklab, var(--ink) 45%, transparent)",
                  }}
                >
                  {providers.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleInputKeyDown}
                  placeholder="Ask anything…"
                  className="flex-1 bg-transparent py-2.5 font-serif italic text-base text-deep placeholder:text-ink/40 placeholder:italic outline-none"
                />
                <button
                  type="submit"
                  aria-label="Send"
                  disabled={!input.trim() || loading}
                  className="grid h-10 w-10 place-items-center rounded-full text-paper transition-all duration-200 disabled:opacity-40 active:scale-90"
                  style={{
                    background: input.trim() ? "var(--gold)" : "var(--deep)",
                    boxShadow: input.trim() ? "0 0 12px rgba(201,168,76,0.3)" : "none",
                  }}
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
              </form>
              <p className="mt-3 px-4 text-center font-serif italic text-[12px] leading-relaxed text-ink/55">
                This is advice by AI and it could be wrong — please don't take this as legal advice and
                consult with a legal attorney for cross verification.
              </p>
            </div>
          </div>
        </main>
      </div>

      {/* ── Footer ── */}
      <footer className="mx-3 mt-3 mb-3 flex flex-wrap items-center justify-between gap-2 px-4 sm:px-5 py-3 font-mono text-[10px] uppercase tracking-[0.2em] text-ink/40">
        <span>© KaloKoT Chambers</span>
        <span className="flex items-center gap-2">
          <Circle className="h-2 w-2 fill-gold text-gold" />
          Session encrypted
        </span>
      </footer>
    </div>
  );
}

// ── Route definition ───────────────────────────────

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Kalokot — AI Legal Companion" },
      { name: "description", content: "Ask Kalokot about tenders, FAQs, complaints and case analysis." },
    ],
  }),
  component: HomePage,
});

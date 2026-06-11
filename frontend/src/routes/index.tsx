import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useRef, useEffect } from "react";
import { Backdrop } from "@/components/lawyer/Backdrop";
import { LowPolyLawyer } from "@/components/lawyer/LowPolyLawyer";
import { counselQuestion, draftComplaint, generateAnalysisReport, textToSpeech } from "@/lib/api";
import {
  Scale, Send, FileText, Shield, Volume2, Download, Loader2, CheckCircle,
  Menu,
} from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "KaloKoT — Know the law. Name the crime." },
      {
        name: "description",
        content:
          "Digital Lawyer for tender corruption analysis, legal counsel, and formal complaint drafting. Powered by the Constitution of Nepal.",
      },
    ],
  }),
  component: Index,
});

type Message = {
  role: "user" | "lawyer";
  text: string;
  id: string;
};

type Mode = "chat" | "analysis" | "complaint";

function Index() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "lawyer",
      text: "Hello, I'm KaloKoT's Digital Lawyer. Ask me anything about tender corruption, your constitutional rights, or how to report a violation. You can also switch to Analysis mode for a full legal report, or Complaint mode to draft a formal complaint letter.",
      id: "welcome",
    },
  ]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [mascotState, setMascotState] = useState<"idle" | "speaking">("idle");
  const [mode, setMode] = useState<Mode>("chat");

  // Analysis mode
  const [analysisIssue, setAnalysisIssue] = useState("");
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analysisPdf, setAnalysisPdf] = useState<Blob | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  // Complaint mode
  const [cmplName, setCmplName] = useState("");
  const [cmplPermAddr, setCmplPermAddr] = useState("");
  const [cmplTempAddr, setCmplTempAddr] = useState("");
  const [cmplCitNo, setCmplCitNo] = useState("");
  const [cmplPhone, setCmplPhone] = useState("");
  const [cmplEmail, setCmplEmail] = useState("");
  const [cmplDesc, setCmplDesc] = useState("");
  const [cmplResult, setCmplResult] = useState<string | null>(null);
  const [cmplPdf, setCmplPdf] = useState<Blob | null>(null);
  const [drafting, setDrafting] = useState(false);

  // Playing audio
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Chat ──
  const handleSend = async () => {
    const q = input.trim();
    if (!q || thinking) return;
    setInput("");
    addMessage("user", q);
    setThinking(true);
    setMascotState("speaking");

    try {
      const resp = await counselQuestion({ question: q, jurisdiction: "NEPAL" });
      addMessage("lawyer", resp.answer);
    } catch {
      addMessage("lawyer", "I need my legal backend connected to give you a precise answer. Please make sure the server is running, or try again.");
    } finally {
      setThinking(false);
      setMascotState("idle");
    }
  };

  const addMessage = (role: "user" | "lawyer", text: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setMessages((prev) => [...prev, { role, text, id }]);
  };

  const speakMessage = async (text: string, id: string) => {
    if (playingId === id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    try {
      const blob = await textToSpeech(text);
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      setPlayingId(id);
      audio.onended = () => {
        setPlayingId(null);
        URL.revokeObjectURL(url);
      };
      audio.play().catch(() => setPlayingId(null));
    } catch {
      // TTS unavailable — fail silently
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (mode === "chat") handleSend();
    }
  };

  // ── Analysis ──
  const handleGenerateAnalysis = async () => {
    const issue = analysisIssue.trim();
    if (!issue || analyzing) return;
    setAnalyzing(true);
    setAnalysisResult(null);
    setAnalysisPdf(null);
    try {
      const blob = await generateAnalysisReport(issue);
      setAnalysisPdf(blob);
      setAnalysisResult("Analysis report generated. Click Download to save as PDF.");
    } catch (e: any) {
      setAnalysisResult(`Error: ${e.message || "Backend unavailable"}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const downloadPdf = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Complaint ──
  const handleDraftComplaint = async () => {
    if (!cmplName.trim() || !cmplDesc.trim() || drafting) return;
    setDrafting(true);
    setCmplResult(null);
    setCmplPdf(null);
    try {
      const blob = await draftComplaint(
        cmplName, cmplPermAddr, cmplTempAddr, cmplCitNo,
        cmplPhone, cmplEmail, cmplDesc,
      );
      setCmplPdf(blob);
      setCmplResult("Complaint letter drafted. Click Download to save as PDF.");
    } catch (e: any) {
      setCmplResult(`Error: ${e.message || "Backend unavailable"}`);
    } finally {
      setDrafting(false);
    }
  };

  return (
    <main className="relative flex h-screen w-full flex-col bg-[color:var(--noir)] text-cream">
      <Backdrop />
      <audio ref={audioRef} className="hidden" />

      {/* Top bar */}
      <header className="relative z-20 flex items-center justify-between px-4 py-3 md:px-8 md:py-4">
        <Link to="/constitution" className="text-xs tracking-[0.24em] uppercase transition-colors hover:text-[color:var(--gold)]" style={{ color: "var(--muted-ink)" }}>
          Constitution
        </Link>
        <span className="text-[13px] tracking-[0.32em] uppercase" style={{ color: "var(--cream)" }}>
          KaloKoT
        </span>
        <Link to="/analysis-report" className="text-xs tracking-[0.24em] uppercase transition-colors hover:text-[color:var(--gold)]" style={{ color: "var(--muted-ink)" }}>
          Report
        </Link>
      </header>

      {/* Main area: mascot left, content right */}
      <div className="relative z-10 flex flex-1 overflow-hidden">
        {/* Mascot — fixed left */}
        <div className="hidden w-48 shrink-0 flex-col items-center justify-center md:flex">
          <div className="pointer-events-none flex flex-col items-center">
            <LowPolyLawyer
              state={mascotState}
              className="h-44 w-auto drop-shadow-[0_20px_50px_rgba(0,0,0,0.5)]"
            />
            <p className="mt-2 text-center text-[10px] tracking-[0.2em] uppercase" style={{ color: "var(--muted-ink)" }}>
              {mascotState === "speaking" ? "Analyzing…" : `${mode === "chat" ? "Chat" : mode === "analysis" ? "Analysis" : "Complaint"} Mode`}
            </p>
          </div>
        </div>

        {/* Right content area */}
        <div className="flex flex-1 flex-col overflow-hidden pr-2 md:pr-6">
          {/* Mode tabs */}
          <div className="flex gap-1 border-b px-4 pb-2 pt-2 md:px-2" style={{ borderColor: "color-mix(in oklab, white 8%, transparent)" }}>
            {(["chat", "analysis", "complaint"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setAnalysisResult(null); setCmplResult(null); }}
                className={`rounded-xl px-4 py-1.5 text-[11px] font-medium tracking-[0.12em] uppercase transition-all ${
                  mode === m
                    ? "text-[color:var(--noir)]"
                    : "text-muted-ink hover:text-cream"
                }`}
                style={{
                  background: mode === m ? "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))" : "transparent",
                }}
              >
                {m === "chat" ? "💬 Chat" : m === "analysis" ? "📋 Analysis" : "⚖️ Complaint"}
              </button>
            ))}
          </div>

          {/* Content area — scrollable */}
          <div className="flex-1 overflow-y-auto px-4 pt-3 md:px-2">
            <div className="mx-auto max-w-3xl">
              {mode === "chat" && (
                /* ── Chat Messages ── */
                <div className="space-y-4">
                  {messages.map((msg) => (
                    <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                      {/* Avatar */}
                      {msg.role === "lawyer" && (
                        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[color:var(--noir-2)] ring-1 ring-[color:var(--gold)]/20">
                          <Scale className="h-4 w-4" style={{ color: "var(--gold)" }} />
                        </div>
                      )}
                      {msg.role === "user" && (
                        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/5 text-[10px] tracking-[0.12em] uppercase text-muted-ink">
                          You
                        </div>
                      )}
                      {/* Bubble */}
                      <div
                        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed relative group ${
                          msg.role === "user" ? "rounded-tr-md" : "rounded-tl-md"
                        }`}
                        style={{
                          background: msg.role === "user"
                            ? "linear-gradient(135deg, color-mix(in oklab, var(--gold) 20%, transparent), color-mix(in oklab, var(--gold) 8%, transparent))"
                            : "color-mix(in oklab, white 6%, transparent)",
                          border: msg.role === "user"
                            ? "1px solid color-mix(in oklab, var(--gold) 20%, transparent)"
                            : "1px solid color-mix(in oklab, white 8%, transparent)",
                        }}
                      >
                        {msg.text}
                        {/* Speaker button */}
                        {msg.role === "lawyer" && (
                          <button
                            onClick={() => speakMessage(msg.text, msg.id)}
                            className="absolute -bottom-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full opacity-0 transition-opacity hover:opacity-100 group-hover:opacity-100"
                            style={{
                              background: "color-mix(in oklab, var(--gold) 20%, transparent)",
                              border: "1px solid color-mix(in oklab, var(--gold) 30%, transparent)",
                            }}
                            title={playingId === msg.id ? "Stop" : "Listen"}
                          >
                            {playingId === msg.id ? (
                              <span className="inline-block h-2 w-2 rounded-sm bg-[color:var(--gold)]" />
                            ) : (
                              <Volume2 className="h-3 w-3" style={{ color: "var(--gold)" }} />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                  {thinking && (
                    <div className="flex gap-3">
                      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[color:var(--noir-2)] ring-1 ring-[color:var(--gold)]/20">
                        <Scale className="h-4 w-4" style={{ color: "var(--gold)" }} />
                      </div>
                      <div className="flex items-center gap-2 rounded-2xl rounded-tl-md px-4 py-3" style={{ background: "color-mix(in oklab, white 6%, transparent)", border: "1px solid color-mix(in oklab, white 8%, transparent)" }}>
                        <span className="inline-block h-2 w-2 animate-pulse rounded-full" style={{ backgroundColor: "var(--gold)" }} />
                        <span className="inline-block h-2 w-2 animate-pulse rounded-full" style={{ backgroundColor: "var(--gold)", animationDelay: "0.15s" }} />
                        <span className="inline-block h-2 w-2 animate-pulse rounded-full" style={{ backgroundColor: "var(--gold)", animationDelay: "0.3s" }} />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {mode === "analysis" && (
                /* ── Analysis Mode ── */
                <div className="space-y-5 pb-4">
                  <div>
                    <h2 className="text-lg font-medium tracking-tight" style={{ color: "var(--cream)" }}>Legal Analysis</h2>
                    <p className="mt-1 text-sm" style={{ color: "var(--muted-ink)" }}>
                      Describe the tender, contract, or legal issue you need analyzed.
                    </p>
                  </div>
                  <textarea
                    value={analysisIssue}
                    onChange={(e) => setAnalysisIssue(e.target.value)}
                    placeholder="Describe the issue in detail. For example: 'A road construction tender awarded to a company with no prior experience, at 40% above market rate…'"
                    rows={5}
                    className="w-full resize-none rounded-2xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none focus:ring-1"
                    style={{
                      border: "1px solid color-mix(in oklab, white 10%, transparent)",
                    }}
                  />
                  <button
                    onClick={handleGenerateAnalysis}
                    disabled={analyzing || !analysisIssue.trim()}
                    className="inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-medium transition-all hover:scale-[1.02] disabled:opacity-40"
                    style={{
                      background: "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                      color: "var(--noir)",
                    }}
                  >
                    {analyzing ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> Generating Analysis…</>
                    ) : (
                      <><Shield className="h-4 w-4" /> Generate Analysis Report</>
                    )}
                  </button>

                  {analysisResult && (
                    <div className="rounded-2xl p-4" style={{ background: "color-mix(in oklab, white 4%, transparent)", border: "1px solid color-mix(in oklab, white 8%, transparent)" }}>
                      <p className="mb-3 text-sm" style={{ color: "var(--muted-ink)" }}>{analysisResult}</p>
                      {analysisPdf && (
                        <button
                          onClick={() => downloadPdf(analysisPdf, "legal_analysis_report.pdf")}
                          className="inline-flex items-center gap-2 rounded-xl px-5 py-2 text-sm font-medium transition-all hover:scale-[1.02]"
                          style={{
                            background: "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                            color: "var(--noir)",
                          }}
                        >
                          <Download className="h-4 w-4" /> Download PDF
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {mode === "complaint" && (
                /* ── Complaint Mode ── */
                <div className="space-y-4 pb-4">
                  <div>
                    <h2 className="text-lg font-medium tracking-tight" style={{ color: "var(--cream)" }}>Draft a Complaint</h2>
                    <p className="mt-1 text-sm" style={{ color: "var(--muted-ink)" }}>
                      Fill in your details and describe the complaint. The lawyer will draft a formal legal letter.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <input value={cmplName} onChange={e => setCmplName(e.target.value)} placeholder="Full Name *" className="rounded-xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none" style={{ border: "1px solid color-mix(in oklab, white 10%, transparent)" }} />
                    <input value={cmplCitNo} onChange={e => setCmplCitNo(e.target.value)} placeholder="Citizenship No." className="rounded-xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none" style={{ border: "1px solid color-mix(in oklab, white 10%, transparent)" }} />
                    <input value={cmplPermAddr} onChange={e => setCmplPermAddr(e.target.value)} placeholder="Permanent Address" className="rounded-xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none" style={{ border: "1px solid color-mix(in oklab, white 10%, transparent)" }} />
                    <input value={cmplTempAddr} onChange={e => setCmplTempAddr(e.target.value)} placeholder="Temporary Address" className="rounded-xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none" style={{ border: "1px solid color-mix(in oklab, white 10%, transparent)" }} />
                    <input value={cmplPhone} onChange={e => setCmplPhone(e.target.value)} placeholder="Phone No." className="rounded-xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none" style={{ border: "1px solid color-mix(in oklab, white 10%, transparent)" }} />
                    <input value={cmplEmail} onChange={e => setCmplEmail(e.target.value)} placeholder="Email" className="rounded-xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none" style={{ border: "1px solid color-mix(in oklab, white 10%, transparent)" }} />
                  </div>
                  <textarea
                    value={cmplDesc} onChange={e => setCmplDesc(e.target.value)}
                    placeholder="Describe your complaint in detail — what happened, when, who was involved, what evidence you have… *"
                    rows={4}
                    className="w-full resize-none rounded-2xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none"
                    style={{ border: "1px solid color-mix(in oklab, white 10%, transparent)" }}
                  />
                  <button
                    onClick={handleDraftComplaint}
                    disabled={drafting || !cmplName.trim() || !cmplDesc.trim()}
                    className="inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-medium transition-all hover:scale-[1.02] disabled:opacity-40"
                    style={{
                      background: "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                      color: "var(--noir)",
                    }}
                  >
                    {drafting ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> Drafting Complaint…</>
                    ) : (
                      <><FileText className="h-4 w-4" /> Draft Complaint Letter</>
                    )}
                  </button>

                  {cmplResult && (
                    <div className="rounded-2xl p-4" style={{ background: "color-mix(in oklab, white 4%, transparent)", border: "1px solid color-mix(in oklab, white 8%, transparent)" }}>
                      <p className="mb-3 text-sm" style={{ color: "var(--muted-ink)" }}>{cmplResult}</p>
                      {cmplPdf && (
                        <button
                          onClick={() => downloadPdf(cmplPdf, "complaint_letter.pdf")}
                          className="inline-flex items-center gap-2 rounded-xl px-5 py-2 text-sm font-medium transition-all hover:scale-[1.02]"
                          style={{
                            background: "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                            color: "var(--noir)",
                          }}
                        >
                          <Download className="h-4 w-4" /> Download PDF
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div ref={bottomRef} />
          </div>

          {/* Chat input bar — always available */}
          <div className="border-t px-4 py-3 md:px-2" style={{ borderColor: "color-mix(in oklab, white 8%, transparent)" }}>
            <div className="mx-auto flex max-w-3xl items-center gap-3">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={mode === "chat" ? "Ask about a tender, the law, or your rights…" : "Type a chat message while you work…"}
                className="flex-1 rounded-2xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none focus:ring-1"
                style={{
                  border: "1px solid color-mix(in oklab, white 10%, transparent)",
                }}
                disabled={thinking}
              />
              <button
                onClick={handleSend}
                disabled={thinking || !input.trim()}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all hover:scale-105 disabled:opacity-40"
                style={{
                  background: "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                  color: "var(--noir)",
                  boxShadow: "0 8px 24px -8px color-mix(in oklab, var(--gold) 60%, transparent)",
                }}
                aria-label="Send"
              >
                <Send className="h-4 w-4" strokeWidth={2.5} />
              </button>
            </div>
            {mode !== "chat" && (
              <p className="mt-1.5 text-[10px] tracking-[0.15em] text-center" style={{ color: "var(--muted-ink)" }}>
                Chat is always available — your message above goes to the Digital Lawyer
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Mobile mascot */}
      <div className="pointer-events-none fixed bottom-28 left-3 z-30 md:hidden">
        <LowPolyLawyer state={mascotState} className="h-16 w-auto opacity-35 drop-shadow-[0_10px_30px_rgba(0,0,0,0.6)]" />
      </div>
    </main>
  );
}

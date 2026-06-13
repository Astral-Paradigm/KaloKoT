import { createFileRoute } from "@tanstack/react-router";
import { useState, useRef, useEffect, useCallback } from "react";
import { Backdrop } from "@/components/lawyer/Backdrop";
import { LowPolyLawyer } from "@/components/lawyer/LowPolyLawyer";
import {
  counselQuestion,
  textToSpeech,
  analyzeTender,
  analyzeTenderText,
  draftComplaint,
  generateAnalysisReport,
  type CounselResponse,
} from "@/lib/api";

// ── Types ───────────────────────────────────

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
}

interface AnalysisResult {
  report_id: string;
  overall_risk: string;
  summary: string;
  section_scores: Record<string, string>;
  flagged_clauses: FlaggedClause[];
}

// ── Risk helpers ─────────────────────────────

function riskColor(level: string): string {
  switch (level) {
    case "critical":
      return "oklch(0.52 0.18 30)";
    case "high":
      return "oklch(0.6 0.16 40)";
    case "medium":
      return "oklch(0.7 0.14 70)";
    default:
      return "oklch(0.6 0.1 150)";
  }
}

function riskBadge(level: string): string {
  const map: Record<string, string> = {
    critical: "CRITICAL",
    high: "HIGH",
    medium: "MEDIUM",
    low: "LOW",
  };
  return map[level] || level.toUpperCase();
}

function severityIcon(sev: string): string {
  switch (sev) {
    case "critical":
      return "🔴";
    case "high":
      return "🟠";
    case "medium":
      return "🟡";
    default:
      return "🟢";
  }
}

// ── Component ────────────────────────────────

function HomePage() {
  const [mode, setMode] = useState<Mode>("chat");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "lawyer",
      text: "Hello, I'm KaloKoT's Digital Lawyer. Ask me anything about tender corruption, your constitutional rights, or how to report a violation. You can also upload a tender for review, or switch to Analysis/Complaint mode.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [speakingId, setSpeakingId] = useState<number | null>(null);
  const [tenderContext, setTenderContext] = useState("");

  // Tender Review state
  const [uploadedFileName, setUploadedFileName] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  // Complaint state
  const [complaintForm, setComplaintForm] = useState({
    name: "",
    permanent_address: "",
    temporary_address: "",
    citizenship_no: "",
    phone: "",
    email: "",
    description: "",
  });
  const [complaintPdf, setComplaintPdf] = useState<Blob | null>(null);
  const [draftingComplaint, setDraftingComplaint] = useState(false);

  // Analysis report state
  const [issueText, setIssueText] = useState("");
  const [analysisPdf, setAnalysisPdf] = useState<Blob | null>(null);
  const [generatingAnalysis, setGeneratingAnalysis] = useState(false);

  const chatEnd = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Chat ───────────────────────────────────

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
      });
      setMessages((m) => [...m, { role: "lawyer", text: res.answer }]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "lawyer",
          text: "I need my legal backend connected to give you a precise answer. Please make sure the server is running, or try again.",
        },
      ]);
    }
    setLoading(false);
  }, [input, loading, tenderContext]);

  const handleTts = useCallback(async (text: string, idx: number) => {
    if (speakingId !== null) return;
    setSpeakingId(idx);
    try {
      const blob = await textToSpeech(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        setSpeakingId(null);
        URL.revokeObjectURL(url);
      };
      audio.play();
    } catch {
      setSpeakingId(null);
    }
  }, [speakingId]);

  // ── Tender Review ──────────────────────────

  const handleFileUpload = useCallback(async (file: File) => {
    setUploadedFileName(file.name);
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const result = await analyzeTender(file);
      setAnalysisResult(result as unknown as AnalysisResult);
    } catch (e) {
      console.error("Tender analysis failed", e);
    }
    setAnalyzing(false);
  }, []);

  const handleAnalyzeText = useCallback(async () => {
    if (!pasteText.trim()) return;
    setUploadedFileName("Pasted text");
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const result = await analyzeTenderText(pasteText);
      setAnalysisResult(result as unknown as AnalysisResult);
    } catch {
      console.error("Analyze text failed");
    }
    setAnalyzing(false);
  }, [pasteText]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileUpload(file);
    },
    [handleFileUpload],
  );

  const discussWithLawyer = useCallback(() => {
    if (analysisResult) {
      setTenderContext(analysisResult.summary);
    }
    setMode("chat");
  }, [analysisResult]);

  // ── Complaint ──────────────────────────────

  const handleDraftComplaint = useCallback(async () => {
    if (!complaintForm.description.trim()) return;
    setDraftingComplaint(true);
    try {
      const blob = await draftComplaint(
        complaintForm.name,
        complaintForm.permanent_address,
        complaintForm.temporary_address,
        complaintForm.citizenship_no,
        complaintForm.phone,
        complaintForm.email,
        complaintForm.description,
      );
      setComplaintPdf(blob);
    } catch {
      console.error("Draft complaint failed");
    }
    setDraftingComplaint(false);
  }, [complaintForm]);

  const handleDownloadComplaint = useCallback(() => {
    if (!complaintPdf) return;
    const url = URL.createObjectURL(complaintPdf);
    const a = document.createElement("a");
    a.href = url;
    a.download = "complaint-letter.pdf";
    a.click();
    URL.revokeObjectURL(url);
  }, [complaintPdf]);

  // ── Analysis Report ────────────────────────

  const handleGenerateAnalysis = useCallback(async () => {
    if (!issueText.trim()) return;
    setGeneratingAnalysis(true);
    try {
      const blob = await generateAnalysisReport(issueText);
      setAnalysisPdf(blob);
    } catch {
      console.error("Generate analysis failed");
    }
    setGeneratingAnalysis(false);
  }, [issueText]);

  const handleDownloadAnalysis = useCallback(() => {
    if (!analysisPdf) return;
    const url = URL.createObjectURL(analysisPdf);
    const a = document.createElement("a");
    a.href = url;
    a.download = "analysis-report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  }, [analysisPdf]);

  // ── Render ─────────────────────────────────

  const modeTab = (key: Mode, label: string, icon: string) => (
    <button
      onClick={() => setMode(key)}
      style={{
        padding: "6px 16px",
        borderRadius: "8px",
        border: `1px solid ${mode === key ? "oklch(0.72 0.14 85)" : "transparent"}`,
        background: mode === key
          ? "color-mix(in oklab, oklch(0.72 0.14 85) 15%, transparent)"
          : "transparent",
        color: mode === key ? "oklch(0.88 0.02 80)" : "oklch(0.5 0.02 80)",
        cursor: "pointer",
        fontSize: "13px",
        fontWeight: mode === key ? 600 : 400,
        transition: "all 0.2s",
      }}
    >
      {icon} {label}
    </button>
  );

  return (
    <div
      className="fixed inset-0 flex flex-col md:flex-row overflow-hidden"
      style={{ background: "oklch(0.14 0.01 260)" }}
    >
      <Backdrop />
      <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
        rel="stylesheet"
      />

      {/* ── Mascot (desktop) ── */}
      <div
        className="hidden md:flex"
        style={{
          flex: "0 0 220px",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "flex-start",
          paddingTop: "40px",
          position: "relative",
          zIndex: 2,
        }}
      >
        <LowPolyLawyer />
        <div
          style={{
            marginTop: "8px",
            fontSize: "11px",
            color: "oklch(0.72 0.14 85)",
            letterSpacing: "2px",
            textTransform: "uppercase",
          }}
        >
          KaloKoT
        </div>
      </div>

      {/* ── Mobile header ── */}
      <div
        className="flex md:hidden"
        style={{
          alignItems: "center",
          gap: "8px",
          padding: "8px 12px",
          borderBottom: "1px solid oklch(0.2 0.01 260)",
          position: "relative",
          zIndex: 2,
          flexShrink: 0,
        }}
      >
        <LowPolyLawyer />
        <div
          style={{
            fontSize: "10px",
            color: "oklch(0.72 0.14 85)",
            letterSpacing: "2px",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
          }}
        >
          KaloKoT
        </div>
        <div style={{ flex: 1 }} />
        <div
          className="no-scrollbar"
          style={{
            display: "flex",
            gap: "3px",
            overflowX: "auto",
            flexShrink: 1,
            minWidth: 0,
            msOverflowStyle: "none",
            scrollbarWidth: "none",
          }}
        >
          <button
            onClick={() => setMode("chat")}
            style={{
              padding: "4px 10px",
              borderRadius: "6px",
              border: `1px solid ${mode === "chat" ? "oklch(0.72 0.14 85)" : "transparent"}`,
              background: mode === "chat"
                ? "color-mix(in oklab, oklch(0.72 0.14 85) 15%, transparent)"
                : "transparent",
              color: mode === "chat" ? "oklch(0.88 0.02 80)" : "oklch(0.5 0.02 80)",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: mode === "chat" ? 600 : 400,
              transition: "all 0.2s",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            💬 Chat
          </button>
          <button
            onClick={() => setMode("tender")}
            style={{
              padding: "4px 10px",
              borderRadius: "6px",
              border: `1px solid ${mode === "tender" ? "oklch(0.72 0.14 85)" : "transparent"}`,
              background: mode === "tender"
                ? "color-mix(in oklab, oklch(0.72 0.14 85) 15%, transparent)"
                : "transparent",
              color: mode === "tender" ? "oklch(0.88 0.02 80)" : "oklch(0.5 0.02 80)",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: mode === "tender" ? 600 : 400,
              transition: "all 0.2s",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            📄 Review
          </button>
          <button
            onClick={() => setMode("analysis")}
            style={{
              padding: "4px 10px",
              borderRadius: "6px",
              border: `1px solid ${mode === "analysis" ? "oklch(0.72 0.14 85)" : "transparent"}`,
              background: mode === "analysis"
                ? "color-mix(in oklab, oklch(0.72 0.14 85) 15%, transparent)"
                : "transparent",
              color: mode === "analysis" ? "oklch(0.88 0.02 80)" : "oklch(0.5 0.02 80)",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: mode === "analysis" ? 600 : 400,
              transition: "all 0.2s",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            📋 Analysis
          </button>
          <button
            onClick={() => setMode("complaint")}
            style={{
              padding: "4px 10px",
              borderRadius: "6px",
              border: `1px solid ${mode === "complaint" ? "oklch(0.72 0.14 85)" : "transparent"}`,
              background: mode === "complaint"
                ? "color-mix(in oklab, oklch(0.72 0.14 85) 15%, transparent)"
                : "transparent",
              color: mode === "complaint" ? "oklch(0.88 0.02 80)" : "oklch(0.5 0.02 80)",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: mode === "complaint" ? 600 : 400,
              transition: "all 0.2s",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            ⚖️ Complaint
          </button>
        </div>
      </div>

      {/* ── Main Panel ── */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          position: "relative",
          zIndex: 2,
          minWidth: 0,
        }}
      >
        {/* Mode Tabs (desktop) */}
        <div
          className="hidden md:flex"
          style={{
            gap: "6px",
            padding: "12px 20px 0",
            borderBottom: "1px solid oklch(0.2 0.01 260)",
          }}
        >
          {modeTab("chat", "Chat", "💬")}
          {modeTab("tender", "Tender Review", "📄")}
          {modeTab("analysis", "Analysis", "📋")}
          {modeTab("complaint", "Complaint", "⚖️")}
        </div>

        {/* ── Content Area ── */}
        <div
          className="p-4 md:p-[16px_20px]"
          style={{
            flex: 1,
            overflowY: "auto",
            fontFamily: "Inter, system-ui, sans-serif",
            fontSize: "14px",
            color: "oklch(0.88 0.02 80)",
            lineHeight: 1.6,
          }}
        >
          {/* ═══ CHAT MODE ═══ */}
          {mode === "chat" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {messages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexDirection: msg.role === "user" ? "row-reverse" : "row",
                    alignItems: "flex-start",
                  }}
                >
                  <div
                    style={{
                      width: "28px",
                      height: "28px",
                      borderRadius: "50%",
                      background:
                        msg.role === "user"
                          ? "oklch(0.25 0.02 260)"
                          : "oklch(0.72 0.14 85 / 0.2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "12px",
                      flexShrink: 0,
                    }}
                  >
                    {msg.role === "user" ? "👤" : "⚖️"}
                  </div>
                  <div
                    className="max-w-[88%] md:max-w-[70%]"
                    style={{
                      padding: "10px 14px",
                      borderRadius: "12px",
                      background:
                        msg.role === "user"
                          ? "oklch(0.22 0.02 260)"
                          : "oklch(0.18 0.01 260)",
                      border: `1px solid ${
                        msg.role === "user"
                          ? "oklch(0.3 0.02 260)"
                          : "oklch(0.25 0.02 260)"
                      }`,
                      position: "relative",
                      whiteSpace: "pre-wrap",
                    }}
                    onMouseEnter={(e) => {
                      if (msg.role === "lawyer") {
                        const btn = e.currentTarget.querySelector(".tts-btn") as HTMLElement;
                        if (btn) btn.style.opacity = "1";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (msg.role === "lawyer") {
                        const btn = e.currentTarget.querySelector(".tts-btn") as HTMLElement;
                        if (btn) btn.style.opacity = "0";
                      }
                    }}
                  >
                    {msg.text}
                    {msg.role === "lawyer" && (
                      <button
                        className="tts-btn md:opacity-0"
                        onClick={() => handleTts(msg.text, i)}
                        disabled={speakingId !== null}
                          style={{
                            position: "absolute",
                            bottom: "-12px",
                            right: "8px",
                            transition: "opacity 0.2s",
                          background: "oklch(0.72 0.14 85 / 0.3)",
                          border: "1px solid oklch(0.72 0.14 85 / 0.4)",
                          borderRadius: "6px",
                          color: "oklch(0.88 0.02 80)",
                          cursor: "pointer",
                          fontSize: "11px",
                          padding: "2px 6px",
                          zIndex: 3,
                        }}
                        title="Read aloud"
                      >
                        {speakingId === i ? "🔊" : "🔈"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div
                  style={{
                    display: "flex",
                    gap: "6px",
                    alignItems: "center",
                    color: "oklch(0.72 0.14 85)",
                    fontSize: "12px",
                    paddingLeft: "38px",
                  }}
                >
                  <span>Thinking</span>
                  <span
                    style={{
                      display: "inline-flex",
                      gap: "3px",
                    }}
                  >
                    {[0, 1, 2].map((d) => (
                      <span
                        key={d}
                        style={{
                          width: "6px",
                          height: "6px",
                          borderRadius: "50%",
                          background: "oklch(0.72 0.14 85)",
                          animation: `pulse 1.2s ${d * 0.3}s infinite`,
                        }}
                      />
                    ))}
                  </span>
                </div>
              )}
              <div ref={chatEnd} />
            </div>
          )}

          {/* ═══ TENDER REVIEW MODE ═══ */}
          {mode === "tender" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {!analysisResult && !analyzing && (
                <>
                  {/* Upload zone */}
                  <div
                    className="p-6 md:p-[40px_20px]"
                    style={{
                      border: "2px dashed oklch(0.3 0.02 260)",
                      borderRadius: "12px",
                      textAlign: "center",
                      cursor: "pointer",
                      transition: "border-color 0.2s",
                    }}
                    onClick={() => fileInput.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.currentTarget.style.borderColor = "oklch(0.72 0.14 85)";
                    }}
                    onDragLeave={(e) => {
                      e.currentTarget.style.borderColor = "oklch(0.3 0.02 260)";
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      const file = e.dataTransfer.files?.[0];
                      if (file) handleFileUpload(file);
                    }}
                  >
                    <input
                      ref={fileInput}
                      type="file"
                      accept=".pdf,.txt,.html,.htm"
                      style={{ display: "none" }}
                      onChange={handleFileChange}
                    />
                    <div style={{ fontSize: "32px", marginBottom: "8px" }}>📄</div>
                    <div style={{ fontWeight: 600, marginBottom: "4px" }}>
                      Upload a tender document (PDF, TXT, HTML)
                    </div>
                    <div style={{ color: "oklch(0.5 0.02 80)", fontSize: "12px" }}>
                      Drag & drop or click to browse
                    </div>
                  </div>

                  {/* OR divider */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      color: "oklch(0.4 0.02 260)",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ flex: 1, height: "1px", background: "oklch(0.2 0.01 260)" }} />
                    OR PASTE TEXT
                    <div style={{ flex: 1, height: "1px", background: "oklch(0.2 0.01 260)" }} />
                  </div>

                  {/* Paste text area */}
                  <textarea
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    placeholder="Paste the tender text here..."
                    style={{
                      width: "100%",
                      minHeight: "120px",
                      padding: "12px",
                      borderRadius: "8px",
                      border: "1px solid oklch(0.25 0.02 260)",
                      background: "oklch(0.16 0.01 260)",
                      color: "oklch(0.88 0.02 80)",
                      fontFamily: "Inter, system-ui, sans-serif",
                      fontSize: "13px",
                      resize: "vertical",
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                  <button
                    onClick={handleAnalyzeText}
                    disabled={!pasteText.trim()}
                    className="w-full md:w-auto"
                    style={{
                      padding: "10px 20px",
                      borderRadius: "8px",
                      border: "none",
                      background: pasteText.trim()
                        ? "oklch(0.72 0.14 85)"
                        : "oklch(0.2 0.01 260)",
                      color: pasteText.trim() ? "#000" : "oklch(0.4 0.02 260)",
                      fontWeight: 600,
                      cursor: pasteText.trim() ? "pointer" : "not-allowed",
                      fontSize: "13px",
                      alignSelf: "flex-start",
                    }}
                  >
                    Analyze Text
                  </button>
                </>
              )}

              {/* Analyzing spinner */}
              {analyzing && (
                <div style={{ textAlign: "center", padding: "40px" }}>
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      border: "3px solid oklch(0.2 0.01 260)",
                      borderTop: "3px solid oklch(0.72 0.14 85)",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                      margin: "0 auto 16px",
                    }}
                  />
                  <div style={{ color: "oklch(0.5 0.02 80)" }}>
                    Analyzing tender...
                  </div>
                  <div style={{ color: "oklch(0.4 0.02 260)", fontSize: "12px", marginTop: "4px" }}>
                    {uploadedFileName}
                  </div>
                </div>
              )}

              {/* ── Analysis Results ── */}
              {analysisResult && !analyzing && (
                <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  {/* Risk Badge + Title */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                    }}
                  >
                    <div
                      style={{
                        padding: "6px 16px",
                        borderRadius: "20px",
                        background: riskColor(analysisResult.overall_risk),
                        color: "#fff",
                        fontWeight: 700,
                        fontSize: "13px",
                        letterSpacing: "1px",
                      }}
                    >
                      {riskBadge(analysisResult.overall_risk)} RISK
                    </div>
                    <div style={{ fontSize: "12px", color: "oklch(0.5 0.02 80)" }}>
                      {uploadedFileName}
                    </div>
                  </div>

                  {/* Summary */}
                  <div
                    style={{
                      padding: "12px",
                      borderRadius: "8px",
                      background: "oklch(0.16 0.01 260)",
                      border: "1px solid oklch(0.22 0.01 260)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "11px",
                        color: "oklch(0.5 0.02 80)",
                        textTransform: "uppercase",
                        letterSpacing: "1px",
                        marginBottom: "6px",
                      }}
                    >
                      Summary
                    </div>
                    <div style={{ whiteSpace: "pre-wrap" }}>
                      {analysisResult.summary}
                    </div>
                  </div>

                  {/* Section Scores */}
                  <div>
                    <div
                      style={{
                        fontSize: "11px",
                        color: "oklch(0.5 0.02 80)",
                        textTransform: "uppercase",
                        letterSpacing: "1px",
                        marginBottom: "8px",
                      }}
                    >
                      Section Risk Scores
                    </div>
                    {Object.entries(analysisResult.section_scores || {}).map(
                      ([section, level]) => (
                        <div
                          key={section}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            marginBottom: "6px",
                          }}
                        >
                          <div
                            className="min-w-0 shrink-0"
                            style={{
                              flex: "0 0 90px",
                              fontSize: "11px",
                              color: "oklch(0.7 0.02 80)",
                              textTransform: "capitalize",
                            }}
                          >
                            {section.replace(/_/g, " ")}
                          </div>
                          <div
                            style={{
                              flex: 1,
                              minWidth: "40px",
                              height: "6px",
                              borderRadius: "4px",
                              background: "oklch(0.2 0.01 260)",
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                height: "100%",
                                width:
                                  level === "critical"
                                    ? "100%"
                                    : level === "high"
                                      ? "75%"
                                      : level === "medium"
                                        ? "50%"
                                        : "25%",
                                borderRadius: "4px",
                                background: riskColor(level),
                                transition: "width 0.5s ease",
                              }}
                            />
                          </div>
                          <div
                            className="shrink-0"
                            style={{
                              flex: "0 0 50px",
                              fontSize: "10px",
                              fontWeight: 600,
                              color: riskColor(level),
                              textAlign: "right",
                            }}
                          >
                            {level.toUpperCase()}
                          </div>
                        </div>
                      ),
                    )}
                  </div>

                  {/* Flagged Clauses */}
                  <div>
                    <div
                      style={{
                        fontSize: "11px",
                        color: "oklch(0.5 0.02 80)",
                        textTransform: "uppercase",
                        letterSpacing: "1px",
                        marginBottom: "8px",
                      }}
                    >
                      Flagged Clauses ({analysisResult.flagged_clauses.length})
                    </div>
                    {analysisResult.flagged_clauses.map((clause) => (
                      <div
                        key={clause.id}
                        style={{
                          padding: "12px",
                          borderRadius: "8px",
                          background: "oklch(0.16 0.01 260)",
                          border: `1px solid ${riskColor(clause.severity)}40`,
                          marginBottom: "8px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            marginBottom: "6px",
                          }}
                        >
                          <span>{severityIcon(clause.severity)}</span>
                          <span style={{ fontWeight: 600, fontSize: "13px" }}>
                            {clause.label}
                          </span>
                          <span
                            style={{
                              fontSize: "10px",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              background: riskColor(clause.severity),
                              color: "#fff",
                              marginLeft: "auto",
                            }}
                          >
                            {clause.severity.toUpperCase()}
                          </span>
                        </div>
                        {clause.location && (
                          <div
                            style={{
                              fontSize: "11px",
                              color: "oklch(0.5 0.02 80)",
                              marginBottom: "4px",
                            }}
                          >
                            📍 {clause.location}
                          </div>
                        )}
                        <div style={{ fontSize: "12px", marginBottom: "6px" }}>
                          {clause.description}
                        </div>
                        {clause.suggestion && (
                          <div
                            style={{
                              fontSize: "12px",
                              color: "oklch(0.72 0.14 85)",
                              padding: "6px 8px",
                              borderRadius: "6px",
                              background: "oklch(0.72 0.14 85 / 0.08)",
                              border: "1px solid oklch(0.72 0.14 85 / 0.15)",
                            }}
                          >
                            💡 {clause.suggestion}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Discuss with Lawyer */}
                  <button
                    onClick={discussWithLawyer}
                    className="w-full md:w-auto"
                    style={{
                      padding: "10px 20px",
                      borderRadius: "8px",
                      border: "1px solid oklch(0.72 0.14 85 / 0.4)",
                      background: "oklch(0.72 0.14 85 / 0.1)",
                      color: "oklch(0.72 0.14 85)",
                      fontWeight: 600,
                      cursor: "pointer",
                      fontSize: "13px",
                      alignSelf: "center",
                    }}
                  >
                    💬 Discuss this with the Digital Lawyer
                  </button>

                  {/* Analyze another button */}
                  <button
                    onClick={() => {
                      setAnalysisResult(null);
                      setUploadedFileName("");
                      setPasteText("");
                    }}
                    className="w-full md:w-auto"
                    style={{
                      padding: "8px 16px",
                      borderRadius: "8px",
                      border: "1px solid oklch(0.3 0.02 260)",
                      background: "transparent",
                      color: "oklch(0.6 0.02 80)",
                      cursor: "pointer",
                      fontSize: "12px",
                      alignSelf: "center",
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
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div
                style={{
                  fontSize: "12px",
                  color: "oklch(0.5 0.02 80)",
                  marginBottom: "4px",
                }}
              >
                Describe the legal issue or tender concern you'd like analyzed.
              </div>
              <textarea
                value={issueText}
                onChange={(e) => setIssueText(e.target.value)}
                placeholder="e.g., A road construction contract was awarded at 40% above market rate with no competitive bidding..."
                style={{
                  width: "100%",
                  minHeight: "150px",
                  padding: "12px",
                  borderRadius: "8px",
                  border: "1px solid oklch(0.25 0.02 260)",
                  background: "oklch(0.16 0.01 260)",
                  color: "oklch(0.88 0.02 80)",
                  fontFamily: "Inter, system-ui, sans-serif",
                  fontSize: "13px",
                  resize: "vertical",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              <button
                onClick={handleGenerateAnalysis}
                disabled={!issueText.trim() || generatingAnalysis}
                className="w-full md:w-auto"
                style={{
                  padding: "10px 20px",
                  borderRadius: "8px",
                  border: "none",
                  background:
                    !issueText.trim() || generatingAnalysis
                      ? "oklch(0.2 0.01 260)"
                      : "oklch(0.72 0.14 85)",
                  color:
                    !issueText.trim() || generatingAnalysis
                      ? "oklch(0.4 0.02 260)"
                      : "#000",
                  fontWeight: 600,
                  cursor:
                    !issueText.trim() || generatingAnalysis
                      ? "not-allowed"
                      : "pointer",
                  fontSize: "13px",
                  alignSelf: "flex-start",
                }}
              >
                {generatingAnalysis ? "Generating..." : "Generate Analysis Report"}
              </button>
              {analysisPdf && (
                <button
                  onClick={handleDownloadAnalysis}
                  className="w-full md:w-auto"
                  style={{
                    padding: "10px 20px",
                    borderRadius: "8px",
                    border: "1px solid oklch(0.72 0.14 85 / 0.4)",
                    background: "oklch(0.72 0.14 85 / 0.1)",
                    color: "oklch(0.72 0.14 85)",
                    fontWeight: 600,
                    cursor: "pointer",
                    fontSize: "13px",
                    alignSelf: "flex-start",
                  }}
                >
                  ⬇ Download Analysis Report (PDF)
                </button>
              )}
            </div>
          )}

          {/* ═══ COMPLAINT MODE ═══ */}
          {mode === "complaint" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div
                style={{
                  fontSize: "12px",
                  color: "oklch(0.5 0.02 80)",
                  marginBottom: "4px",
                }}
              >
                Fill in your details and describe the complaint. The Digital Lawyer will draft a formal complaint letter.
              </div>

              {(["name", "permanent_address", "temporary_address", "citizenship_no", "phone", "email"] as const).map((field) => (
                <input
                  key={field}
                  type={field === "email" ? "email" : "text"}
                  value={complaintForm[field]}
                  onChange={(e) =>
                    setComplaintForm((f) => ({ ...f, [field]: e.target.value }))
                  }
                  placeholder={
                    field === "name"
                      ? "Full Name"
                      : field === "permanent_address"
                        ? "Permanent Address"
                        : field === "temporary_address"
                          ? "Temporary Address"
                          : field === "citizenship_no"
                            ? "Citizenship No."
                            : field === "phone"
                              ? "Phone"
                              : "Email"
                  }
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid oklch(0.25 0.02 260)",
                    background: "oklch(0.16 0.01 260)",
                    color: "oklch(0.88 0.02 80)",
                    fontSize: "13px",
                    outline: "none",
                    fontFamily: "Inter, system-ui, sans-serif",
                    boxSizing: "border-box",
                  }}
                />
              ))}

              <textarea
                value={complaintForm.description}
                onChange={(e) =>
                  setComplaintForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="Describe the complaint in detail..."
                style={{
                  width: "100%",
                  minHeight: "120px",
                  padding: "12px",
                  borderRadius: "8px",
                  border: "1px solid oklch(0.25 0.02 260)",
                  background: "oklch(0.16 0.01 260)",
                  color: "oklch(0.88 0.02 80)",
                  fontFamily: "Inter, system-ui, sans-serif",
                  fontSize: "13px",
                  resize: "vertical",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />

              <button
                onClick={handleDraftComplaint}
                disabled={!complaintForm.description.trim() || draftingComplaint}
                className="w-full md:w-auto"
                style={{
                  padding: "10px 20px",
                  borderRadius: "8px",
                  border: "none",
                  background:
                    !complaintForm.description.trim() || draftingComplaint
                      ? "oklch(0.2 0.01 260)"
                      : "oklch(0.72 0.14 85)",
                  color:
                    !complaintForm.description.trim() || draftingComplaint
                      ? "oklch(0.4 0.02 260)"
                      : "#000",
                  fontWeight: 600,
                  cursor:
                    !complaintForm.description.trim() || draftingComplaint
                      ? "not-allowed"
                      : "pointer",
                  fontSize: "13px",
                  alignSelf: "flex-start",
                }}
              >
                {draftingComplaint ? "Drafting..." : "📝 Draft Complaint Letter"}
              </button>

              {complaintPdf && (
                <button
                  onClick={handleDownloadComplaint}
                  className="w-full md:w-auto"
                  style={{
                    padding: "10px 20px",
                    borderRadius: "8px",
                    border: "1px solid oklch(0.72 0.14 85 / 0.4)",
                    background: "oklch(0.72 0.14 85 / 0.1)",
                    color: "oklch(0.72 0.14 85)",
                    fontWeight: 600,
                    cursor: "pointer",
                    fontSize: "13px",
                    alignSelf: "flex-start",
                  }}
                >
                  ⬇ Download Complaint Letter (PDF)
                </button>
              )}
            </div>
          )}
        </div>

        {/* ── Chat Input Bar (always present) ── */}
        <div
          className="p-2 md:p-[10px_20px_16px]"
          style={{
            borderTop: "1px solid oklch(0.2 0.01 260)",
            display: "flex",
            gap: "6px",
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask the Digital Lawyer anything..."
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: "8px",
              border: "1px solid oklch(0.25 0.02 260)",
              background: "oklch(0.16 0.01 260)",
              color: "oklch(0.88 0.02 80)",
              fontFamily: "Inter, system-ui, sans-serif",
              fontSize: "13px",
              outline: "none",
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              border: "none",
              background:
                !input.trim() || loading
                  ? "oklch(0.2 0.01 260)"
                  : "oklch(0.72 0.14 85)",
              color:
                !input.trim() || loading ? "oklch(0.4 0.02 260)" : "#000",
              fontWeight: 600,
              cursor:
                !input.trim() || loading ? "not-allowed" : "pointer",
              fontSize: "13px",
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export const Route = createFileRoute("/")({
  component: HomePage,
});

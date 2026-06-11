import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  AlertTriangle,
  FileText,
  Scale,
  ClipboardCheck,
  FileDown,
  CheckCircle2,
  Circle,
  Download,
  Printer,
} from "lucide-react";
import { Backdrop } from "@/components/lawyer/Backdrop";

export const Route = createFileRoute("/analysis-report")({
  head: () => ({
    meta: [
      { title: "Analysis Report — KaloKoT" },
      {
        name: "description",
        content:
          "Detailed corruption-risk analysis of the uploaded tender, evidence checklist, and complaint export.",
      },
      { property: "og:title", content: "Analysis Report — KaloKoT" },
      {
        property: "og:description",
        content:
          "Question-by-question findings, PDF analysis, evidence checklist, and exportable complaint.",
      },
    ],
  }),
  component: AnalysisReport,
});

type Risk = "high" | "medium" | "low";

const riskTone: Record<Risk, { label: string; color: string; bg: string }> = {
  high: { label: "High risk", color: "#ff7a7a", bg: "rgba(255,80,80,0.12)" },
  medium: { label: "Medium risk", color: "#f0c36d", bg: "rgba(240,195,109,0.12)" },
  low: { label: "Low risk", color: "#9ad7a4", bg: "rgba(154,215,164,0.12)" },
};

const qa = [
  {
    q: "Who is the issuing authority and is the scope clearly defined?",
    a: "The tender is issued by the District Public Works Department. Scope language is vague — uses 'allied works' without itemisation, leaving room for unbounded change orders.",
    risk: "medium" as Risk,
    law: "Rule 173, GFR 2017 — scope and quantities must be specific.",
  },
  {
    q: "Is the eligibility criteria fair and non-restrictive?",
    a: "Turnover threshold (₹25 Cr) and single-work experience clause appear tailored — only 2 bidders in the district can satisfy both. Classic restrictive-eligibility pattern.",
    risk: "high" as Risk,
    law: "CVC Circular 03/01/12 — tailored eligibility = cartelisation flag.",
  },
  {
    q: "Is the timeline reasonable for serious bidders?",
    a: "Bid submission window is 7 days from publication. Standard for works of this value is 21 days minimum.",
    risk: "high" as Risk,
    law: "Manual for Procurement of Works 2022, §4.6.2.",
  },
  {
    q: "Are evaluation criteria objective and pre-disclosed?",
    a: "Technical evaluation includes a 30% 'subjective suitability' weight with no rubric. This is the single largest manipulation vector in the document.",
    risk: "high" as Risk,
    law: "GFR Rule 173(iv) — evaluation criteria must be objective and measurable.",
  },
  {
    q: "Are EMD and performance security clauses standard?",
    a: "EMD of 5% is on the higher end but within bounds. Performance security at 10% is standard.",
    risk: "low" as Risk,
    law: "GFR Rule 170 — within permitted range.",
  },
];

const pdfFindings = [
  {
    title: "Restrictive eligibility clause",
    page: "p. 4, §2.3",
    detail:
      "Requires single completed work ≥ ₹18 Cr in the same district in the last 3 years — geographically narrows the bidder pool to a known set.",
    risk: "high" as Risk,
  },
  {
    title: "Short bid window",
    page: "p. 2, §1.4",
    detail:
      "Only 7 calendar days between publication and bid submission deadline.",
    risk: "high" as Risk,
  },
  {
    title: "Subjective technical scoring",
    page: "p. 9, §5.2",
    detail:
      "30% weightage to 'overall suitability' with no published rubric or sub-criteria.",
    risk: "high" as Risk,
  },
  {
    title: "Vague scope language",
    page: "p. 6, §3.1",
    detail:
      "'Allied and ancillary works as directed' — enables unbounded change orders post-award.",
    risk: "medium" as Risk,
  },
  {
    title: "Unitemised BOQ rows",
    page: "p. 12, BOQ #18–22",
    detail:
      "Lump-sum entries without unit breakdowns prevent line-item comparison.",
    risk: "medium" as Risk,
  },
];

const evidence = [
  { label: "Original tender PDF (as published)", done: true },
  { label: "Corrigenda and addenda (if any)", done: true },
  { label: "Pre-bid meeting minutes", done: false },
  { label: "Bidder list / participation record", done: false },
  { label: "Technical evaluation sheet with scoring", done: false },
  { label: "Comparison with prior tenders by same authority", done: true },
  { label: "Screenshots of portal listing with timestamps", done: true },
  { label: "RTI reply (if filed) on evaluation criteria", done: false },
];

function RiskBadge({ risk }: { risk: Risk }) {
  const t = riskTone[risk];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium tracking-[0.12em] uppercase"
      style={{ color: t.color, background: t.bg, border: `1px solid ${t.color}33` }}
    >
      <AlertTriangle className="h-3 w-3" />
      {t.label}
    </span>
  );
}

function AnalysisReport() {
  const highCount = [...qa, ...pdfFindings].filter((x) => x.risk === "high").length;

  return (
    <main className="relative min-h-screen w-full overflow-x-hidden bg-[color:var(--noir)] text-cream">
      <Backdrop />

      {/* Top bar */}
      <header className="relative z-20 flex items-center justify-between px-8 py-6">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs tracking-[0.24em] uppercase transition-colors hover:text-[color:var(--gold)]"
          style={{ color: "var(--muted-ink)" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </Link>
        <span
          className="text-[15px] tracking-[0.32em] uppercase"
          style={{ color: "var(--cream)" }}
        >
          KaloKoT
        </span>
        <span className="w-16" />
      </header>

      <div className="relative z-10 mx-auto w-full max-w-5xl px-6 pb-24">
        {/* Title */}
        <section className="mb-10 text-center">
          <p
            className="mb-3 text-xs tracking-[0.32em] uppercase"
            style={{ color: "var(--gold)" }}
          >
            Analysis Report
          </p>
          <h1
            className="font-display text-4xl leading-[1.05] tracking-tight md:text-5xl"
            style={{ color: "var(--cream)" }}
          >
            What's wrong with this tender.
          </h1>
          <p
            className="mx-auto mt-3 max-w-xl text-sm md:text-base"
            style={{ color: "var(--muted-ink)" }}
          >
            {highCount} high-risk findings across questions and the PDF. Cited
            to the law, ready to file.
          </p>
        </section>

        {/* Q & A Analysis */}
        <section className="mb-10">
          <div className="mb-4 flex items-center gap-2">
            <Scale className="h-4 w-4" style={{ color: "var(--gold)" }} />
            <h2
              className="text-xs tracking-[0.28em] uppercase"
              style={{ color: "var(--cream)" }}
            >
              Question analysis
            </h2>
          </div>
          <div className="space-y-3">
            {qa.map((item, i) => (
              <article key={i} className="glass rounded-2xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <h3
                    className="text-base font-medium md:text-lg"
                    style={{ color: "var(--cream)" }}
                  >
                    {item.q}
                  </h3>
                  <RiskBadge risk={item.risk} />
                </div>
                <p className="mt-2 text-sm" style={{ color: "var(--muted-ink)" }}>
                  {item.a}
                </p>
                <p
                  className="mt-3 text-[11px] tracking-[0.16em] uppercase"
                  style={{ color: "var(--gold-soft)" }}
                >
                  {item.law}
                </p>
              </article>
            ))}
          </div>
        </section>

        {/* PDF analysis */}
        <section className="mb-10">
          <div className="mb-4 flex items-center gap-2">
            <FileText className="h-4 w-4" style={{ color: "var(--gold)" }} />
            <h2
              className="text-xs tracking-[0.28em] uppercase"
              style={{ color: "var(--cream)" }}
            >
              PDF analysis
            </h2>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {pdfFindings.map((f, i) => (
              <article key={i} className="glass rounded-2xl p-5">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-medium" style={{ color: "var(--cream)" }}>
                    {f.title}
                  </h3>
                  <RiskBadge risk={f.risk} />
                </div>
                <p
                  className="mt-2 text-[11px] tracking-[0.16em] uppercase"
                  style={{ color: "var(--gold-soft)" }}
                >
                  {f.page}
                </p>
                <p className="mt-2 text-sm" style={{ color: "var(--muted-ink)" }}>
                  {f.detail}
                </p>
              </article>
            ))}
          </div>
        </section>

        {/* Evidence checklist */}
        <section id="evidence-checklist" className="mb-10 scroll-mt-24">
          <div className="mb-4 flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4" style={{ color: "var(--gold)" }} />
            <h2
              className="text-xs tracking-[0.28em] uppercase"
              style={{ color: "var(--cream)" }}
            >
              Evidence checklist
            </h2>
          </div>
          <div className="glass rounded-2xl p-6">
            <ul className="grid gap-3 md:grid-cols-2">
              {evidence.map((e, i) => (
                <li key={i} className="flex items-start gap-3">
                  {e.done ? (
                    <CheckCircle2
                      className="mt-0.5 h-5 w-5 shrink-0"
                      style={{ color: "var(--gold)" }}
                    />
                  ) : (
                    <Circle
                      className="mt-0.5 h-5 w-5 shrink-0"
                      style={{ color: "var(--muted-ink)" }}
                    />
                  )}
                  <span
                    className="text-sm"
                    style={{
                      color: e.done ? "var(--cream)" : "var(--muted-ink)",
                      textDecoration: e.done ? "none" : "none",
                    }}
                  >
                    {e.label}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Export complaint */}
        <section id="export-complaint" className="scroll-mt-24">
          <div className="mb-4 flex items-center gap-2">
            <FileDown className="h-4 w-4" style={{ color: "var(--gold)" }} />
            <h2
              className="text-xs tracking-[0.28em] uppercase"
              style={{ color: "var(--cream)" }}
            >
              Export complaint
            </h2>
          </div>
          <div className="glass rounded-2xl p-6">
            <p
              className="text-sm"
              style={{ color: "var(--muted-ink)" }}
            >
              A pre-filled complaint addressed to the{" "}
              <span style={{ color: "var(--cream)" }}>
                Central Vigilance Commission
              </span>{" "}
              and the{" "}
              <span style={{ color: "var(--cream)" }}>
                Chief Technical Examiner
              </span>
              , citing every high-risk clause above with the relevant rule
              references. Review it once before filing.
            </p>

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-transform hover:scale-[1.02]"
                style={{
                  background:
                    "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                  color: "var(--noir)",
                  boxShadow:
                    "0 8px 24px -8px color-mix(in oklab, var(--gold) 60%, transparent)",
                }}
              >
                <Download className="h-4 w-4" />
                Download complaint (PDF)
              </button>
              <button
                type="button"
                className="glass inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium text-cream transition-all hover:scale-[1.02]"
                style={{ color: "var(--cream)" }}
              >
                <Printer className="h-4 w-4" style={{ color: "var(--gold)" }} />
                Print version
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

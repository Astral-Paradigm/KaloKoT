import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { ArrowLeft, Search, BookOpen, Scale, FileText } from "lucide-react";
import { Backdrop } from "@/components/lawyer/Backdrop";
import { searchConstitution, getConstitutionContext } from "@/lib/api";

export const Route = createFileRoute("/constitution")({
  head: () => ({
    meta: [
      { title: "Constitution — KaloKoT" },
      {
        name: "description",
        content:
          "Search and browse the Constitution of Nepal 2015. Find constitutional articles relevant to your case.",
      },
    ],
  }),
  component: ConstitutionPage,
});

interface Result {
  child_id: string;
  child_text: string;
  score: number;
  parent_id: string;
  parent_title: string;
  part_title: string;
  path: string[];
}

function ConstitutionPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [context, setContext] = useState("");
  const [searching, setSearching] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [fullText, setFullText] = useState("");
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setSearched(true);
    setBrowsing(false);
    try {
      const resp = await searchConstitution(q, 6);
      setResults(resp.results || []);
      setContext(resp.context || "");
    } catch {
      setResults([]);
      setContext("Backend offline — start the API server to search the constitution.");
    } finally {
      setSearching(false);
    }
  };

  const handleBrowse = async () => {
    setBrowsing(true);
    setSearched(true);
    setSearching(true);
    try {
      const text = await getConstitutionContext();
      setFullText(text);
    } catch {
      setFullText("Backend offline — start the API server to browse the constitution.");
    } finally {
      setSearching(false);
    }
  };

  return (
    <main className="relative min-h-screen w-full overflow-x-hidden bg-[color:var(--noir)] text-cream">
      <Backdrop />

      {/* Top bar */}
      <header className="relative z-20 flex items-center justify-between px-4 py-3 md:px-6 md:py-4">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs tracking-[0.24em] uppercase transition-colors hover:text-[color:var(--gold)]"
          style={{ color: "var(--muted-ink)" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </Link>
        <span
          className="text-[13px] tracking-[0.32em] uppercase"
          style={{ color: "var(--cream)" }}
        >
          Constitution of Nepal
        </span>
        <Link
          to="/chat"
          className="inline-flex items-center gap-2 text-xs tracking-[0.24em] uppercase transition-colors hover:text-[color:var(--gold)]"
          style={{ color: "var(--muted-ink)" }}
        >
          <Scale className="h-3.5 w-3.5" />
          Lawyer
        </Link>
      </header>

      <div className="relative z-10 mx-auto w-full max-w-5xl px-4 pb-20 md:px-6 md:pb-24">
        {/* Title */}
        <section className="mb-8 text-center">
          <p
            className="mb-3 text-xs tracking-[0.32em] uppercase"
            style={{ color: "var(--gold)" }}
          >
            Legal Reference
          </p>
          <h1
            className="font-display text-4xl leading-[1.05] tracking-tight md:text-5xl"
            style={{ color: "var(--cream)" }}
          >
            Constitution of Nepal 2015
          </h1>
          <p
            className="mx-auto mt-3 max-w-xl text-sm md:text-base"
            style={{ color: "var(--muted-ink)" }}
          >
            Search specific articles or browse the full text. Every result is
            linked to its parent article for full legal context.
          </p>
        </section>

        {/* Search bar */}
        <section className="mb-8">
          <div
            className="mx-auto flex max-w-2xl items-center gap-3 rounded-2xl px-4 py-2"
            style={{
              background: "color-mix(in oklab, white 6%, transparent)",
              border: "1px solid color-mix(in oklab, white 10%, transparent)",
            }}
          >
            <Search className="h-5 w-5 shrink-0" style={{ color: "var(--muted-ink)" }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search the constitution… e.g., right to information, corruption, judiciary"
              className="flex-1 bg-transparent text-[15px] text-cream placeholder:text-muted-ink focus:outline-none"
              style={{ color: "var(--cream)" }}
            />
            <button
              onClick={handleSearch}
              disabled={searching || !query.trim()}
              className="rounded-xl px-5 py-2 text-sm font-medium transition-all hover:scale-[1.02] disabled:opacity-40"
              style={{
                background:
                  "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                color: "var(--noir)",
              }}
            >
              {searching ? "Searching…" : "Search"}
            </button>
          </div>
          <div className="mt-3 text-center">
            <button
              onClick={handleBrowse}
              disabled={searching}
              className="inline-flex items-center gap-2 text-xs tracking-[0.18em] uppercase transition-colors hover:text-[color:var(--gold)] disabled:opacity-40"
              style={{ color: "var(--muted-ink)" }}
            >
              <BookOpen className="h-3.5 w-3.5" />
              Or browse the full text
            </button>
          </div>
        </section>

        {/* Results */}
        {searched && (
          <section>
            {searching ? (
              <div className="flex items-center justify-center py-16">
                <div className="flex gap-2">
                  <span
                    className="inline-block h-3 w-3 animate-pulse rounded-full"
                    style={{ backgroundColor: "var(--gold)" }}
                  />
                  <span
                    className="inline-block h-3 w-3 animate-pulse rounded-full"
                    style={{ backgroundColor: "var(--gold)", animationDelay: "0.15s" }}
                  />
                  <span
                    className="inline-block h-3 w-3 animate-pulse rounded-full"
                    style={{ backgroundColor: "var(--gold)", animationDelay: "0.3s" }}
                  />
                </div>
              </div>
            ) : browsing ? (
              /* Full text browser */
              <div
                className="rounded-2xl p-6"
                style={{
                  background: "color-mix(in oklab, white 4%, transparent)",
                  border: "1px solid color-mix(in oklab, white 8%, transparent)",
                }}
              >
                <div className="mb-4 flex items-center gap-2">
                  <BookOpen className="h-4 w-4" style={{ color: "var(--gold)" }} />
                  <h2
                    className="text-xs tracking-[0.28em] uppercase"
                    style={{ color: "var(--cream)" }}
                  >
                    Full Text
                  </h2>
                </div>
                <pre
                  className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed"
                  style={{ color: "var(--muted-ink)" }}
                >
                  {fullText || "No text loaded."}
                </pre>
              </div>
            ) : results.length === 0 ? (
              <div className="py-16 text-center">
                <p className="text-sm" style={{ color: "var(--muted-ink)" }}>
                  No matching articles found. Try a different search term or
                  browse the full text.
                </p>
              </div>
            ) : (
              /* Search results */
              <div className="space-y-3">
                <p className="text-xs tracking-[0.18em] uppercase" style={{ color: "var(--muted-ink)" }}>
                  {results.length} result{results.length !== 1 ? "s" : ""}
                </p>
                {results.map((r, i) => (
                  <article
                    key={i}
                    className="rounded-2xl p-5"
                    style={{
                      background: "color-mix(in oklab, white 4%, transparent)",
                      border: "1px solid color-mix(in oklab, white 8%, transparent)",
                    }}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3
                          className="text-sm font-medium"
                          style={{ color: "var(--cream)" }}
                        >
                          {r.parent_title}
                        </h3>
                        <p
                          className="mt-1 text-xs tracking-[0.16em] uppercase"
                          style={{ color: "var(--gold-soft)" }}
                        >
                          {r.part_title} · {r.parent_id}
                        </p>
                      </div>
                      <span
                        className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium tracking-[0.12em] uppercase"
                        style={{
                          color: "color-mix(in oklab, var(--gold) 80%, white)",
                          background: "color-mix(in oklab, var(--gold) 12%, transparent)",
                          border: "1px solid color-mix(in oklab, var(--gold) 20%, transparent)",
                        }}
                      >
                        {Math.round(r.score * 100)}% match
                      </span>
                    </div>
                    <p
                      className="mt-3 text-sm leading-relaxed"
                      style={{ color: "var(--muted-ink)" }}
                    >
                      {r.child_text}
                    </p>
                    {r.path.length > 0 && (
                      <p
                        className="mt-2 text-[11px]"
                        style={{ color: "color-mix(in oklab, var(--muted-ink) 60%, transparent)" }}
                      >
                        {r.path.join(" → ")}
                      </p>
                    )}
                  </article>
                ))}

                {/* Context section */}
                {context && (
                  <div
                    className="mt-6 rounded-2xl p-6"
                    style={{
                      background: "color-mix(in oklab, white 4%, transparent)",
                      border: "1px solid color-mix(in oklab, var(--gold) 15%, transparent)",
                    }}
                  >
                    <div className="mb-3 flex items-center gap-2">
                      <FileText className="h-4 w-4" style={{ color: "var(--gold)" }} />
                      <h3
                        className="text-xs tracking-[0.28em] uppercase"
                        style={{ color: "var(--cream)" }}
                      >
                        Full Article Context
                      </h3>
                    </div>
                    <pre
                      className="max-h-80 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed"
                      style={{ color: "var(--muted-ink)" }}
                    >
                      {context}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

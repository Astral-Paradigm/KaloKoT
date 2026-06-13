/* ===================================================================
 * KaloKoT — Constitution Search
 *
 * Search and browse the Constitution of Nepal 2015.
 * Results show relevance scores, parent-article context, and breadcrumbs.
 * Styled to match the homepage glass-morphism light theme.
 * =================================================================== */

import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowLeft, Search, BookOpen, Scale, FileText } from "lucide-react";
import { searchConstitution, getConstitutionContext } from "@/lib/api";

// ── Route (SEO meta) ───────────────────────────────

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

// ── Types ──────────────────────────────────────────

interface Result {
  child_id: string;
  child_text: string;
  score: number;
  parent_id: string;
  parent_title: string;
  part_title: string;
  path: string[];
}

// ── Component ──────────────────────────────────────

function ConstitutionPage() {
  // ── State ──────────────────────────────────────
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [context, setContext] = useState("");
  const [searching, setSearching] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [fullText, setFullText] = useState("");
  const [searched, setSearched] = useState(false);

  // ── Handlers ───────────────────────────────────

  /** Submit a semantic search query against the constitution text. */
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

  /** Fetch and display the full constitution text for browsing. */
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

  // ── Render ─────────────────────────────────────
  return (
    <div className="min-h-screen w-full text-ink">

      {/* ── Header (same as homepage) ── */}
      <header className="glass sticky top-3 z-30 mx-3 flex h-14 items-center justify-between gap-3 rounded-2xl px-4 sm:px-5">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs tracking-[0.24em] uppercase transition-colors hover:text-gold text-ink/60"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </Link>
        <span className="font-serif text-xl sm:text-2xl italic tracking-tight text-deep">
          Constitution of Nepal
        </span>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs tracking-[0.24em] uppercase transition-colors hover:text-gold text-ink/60"
        >
          <Scale className="h-3.5 w-3.5" />
          Lawyer
        </Link>
      </header>

      {/* ── Two-column layout (same as homepage) ── */}
      <div className="mx-3 mt-3 flex gap-3" style={{ minHeight: "calc(100vh - 5rem)" }}>

        {/* ── Sidebar (desktop only, same as homepage) ── */}
        <aside className="glass hidden w-64 shrink-0 flex-col rounded-2xl p-4 md:flex">
          <div className="mb-4">
            <p className="text-kicker mb-2 px-2">Navigation</p>
            <ul className="space-y-0.5">
              <li>
                <Link
                  to="/"
                  className="group interactive flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition text-ink/75 hover:bg-paper-dark/60"
                >
                  <FileText className="h-4 w-4" />
                  Home
                </Link>
              </li>
              <li>
                <button
                  onClick={handleBrowse}
                  disabled={searching}
                  className="group interactive flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition bg-ink/8 text-deep font-medium"
                >
                  <BookOpen className="h-4 w-4" />
                  Browse Full Text
                </button>
              </li>
            </ul>
          </div>

          <div className="h-px bg-ink/10 my-2" />

          <div className="flex-1 overflow-hidden">
            <p className="text-kicker mb-2 px-2">Quick Search</p>
            <ul className="space-y-1">
              {[
                "right to information",
                "corruption",
                "fundamental rights",
                "judiciary",
                "citizenship",
              ].map((topic) => (
                <li
                  key={topic}
                  onClick={() => { setQuery(topic); handleSearch(); }}
                  className="rounded-lg px-3 py-2 hover:bg-paper-dark/60 cursor-pointer"
                >
                  <p className="text-sm text-ink/80 capitalize">{topic}</p>
                </li>
              ))}
            </ul>
          </div>

          {/* Live indicator */}
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-ink/10 px-3 py-2 bg-paper/40">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gold opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-gold" />
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink/60">
              Constitution DB
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
            <div className="flex flex-1 flex-col items-center w-full overflow-y-auto animate-fade-in">

              {/* ── Title section ── */}
              <section className="mb-8 text-center">
                <p className="text-kicker mb-3">
                  Legal Reference
                </p>
                <h1 className="font-serif text-4xl leading-[1.05] tracking-tight md:text-5xl text-deep">
                  Constitution of Nepal 2015
                </h1>
                <p className="mx-auto mt-3 max-w-xl text-sm md:text-base text-ink/60">
                  Search specific articles or browse the full text. Every result is
                  linked to its parent article for full legal context.
                </p>
              </section>

              {/* ── Search bar ── */}
              <section className="mb-8 w-full max-w-2xl">
                <div className="glass flex items-center gap-3 rounded-2xl px-4 py-2">
                  <Search className="h-5 w-5 shrink-0 text-ink/40" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    placeholder="Search the constitution… e.g., right to information, corruption, judiciary"
                    className="flex-1 bg-transparent text-[15px] text-deep placeholder:text-ink/40 focus:outline-none"
                  />
                  <button
                    onClick={handleSearch}
                    disabled={searching || !query.trim()}
                    className="rounded-xl px-5 py-2 text-sm font-medium transition-all hover:scale-[1.02] disabled:opacity-40"
                    style={{
                      background:
                        "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                      color: "var(--paper)",
                    }}
                  >
                    {searching ? "Searching…" : "Search"}
                  </button>
                </div>
                <div className="mt-3 text-center">
                  <button
                    onClick={handleBrowse}
                    disabled={searching}
                    className="inline-flex items-center gap-2 text-xs tracking-[0.18em] uppercase transition-colors hover:text-gold disabled:opacity-40 text-ink/50"
                  >
                    <BookOpen className="h-3.5 w-3.5" />
                    Or browse the full text
                  </button>
                </div>
              </section>

              {/* ── Results area ── */}
              {searched && (
                <section className="w-full max-w-3xl">
                  {/* Loading spinner */}
                  {searching ? (
                    <div className="flex items-center justify-center py-16">
                      <div className="flex gap-2">
                        <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-gold" />
                        <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-gold" style={{ animationDelay: "0.15s" }} />
                        <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-gold" style={{ animationDelay: "0.3s" }} />
                      </div>
                    </div>
                  ) : browsing ? (
                    /* ── Full-text browser ── */
                    <div className="glass rounded-2xl p-6">
                      <div className="mb-4 flex items-center gap-2">
                        <BookOpen className="h-4 w-4 text-gold" />
                        <h2 className="text-kicker">
                          Full Text
                        </h2>
                      </div>
                      <pre className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink/70">
                        {fullText || "No text loaded."}
                      </pre>
                    </div>
                  ) : results.length === 0 ? (
                    /* ── Empty state ── */
                    <div className="py-16 text-center">
                      <p className="text-sm text-ink/50">
                        No matching articles found. Try a different search term or
                        browse the full text.
                      </p>
                    </div>
                  ) : (
                    /* ── Search results list ── */
                    <div className="space-y-3">
                      <p className="text-kicker">
                        {results.length} result{results.length !== 1 ? "s" : ""}
                      </p>
                      {results.map((r, i) => (
                        <article key={i} className="glass rounded-2xl p-5">
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="text-kicker mb-1">
                                {r.parent_title}
                              </p>
                              <p className="font-serif text-sm text-deep leading-relaxed">
                                {r.child_text}
                              </p>
                            </div>
                            <span className="shrink-0 rounded-lg bg-ink/5 px-2 py-1 font-mono text-[10px] text-ink/50">
                              {(r.score * 100).toFixed(0)}%
                            </span>
                          </div>

                          {/* Breadcrumbs */}
                          {r.path && r.path.length > 0 && (
                            <div className="mt-3 flex flex-wrap items-center gap-1 text-[10px] text-ink/40">
                              {r.path.map((p, j) => (
                                <span key={j} className="flex items-center gap-1">
                                  {j > 0 && <span className="text-ink/20">›</span>}
                                  <span>{p}</span>
                                </span>
                              ))}
                            </div>
                          )}
                        </article>
                      ))}

                      {/* Context panel */}
                      {context && (
                        <div className="glass rounded-2xl p-5 mt-4">
                          <div className="flex items-center gap-2 mb-2">
                            <FileText className="h-4 w-4 text-gold" />
                            <p className="text-kicker">
                              Full Context
                            </p>
                          </div>
                          <pre className="whitespace-pre-wrap text-sm leading-relaxed text-ink/70 max-h-[40vh] overflow-y-auto">
                            {context}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </section>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

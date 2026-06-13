import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useRef, useEffect } from "react";
import { ArrowLeft, Send, Scale, FileText, Menu } from "lucide-react";
import { Backdrop } from "@/components/lawyer/Backdrop";
import { LowPolyLawyer } from "@/components/lawyer/LowPolyLawyer";
import { counselQuestion, searchConstitution } from "@/lib/api";

export const Route = createFileRoute("/chat")({
  head: () => ({
    meta: [
      { title: "Digital Lawyer — KaloKoT" },
      {
        name: "description",
        content:
          "Chat with KaloKoT's Digital Lawyer. Ask about tender corruption, constitutional rights, and next steps.",
      },
    ],
  }),
  component: ChatPage,
});

type Message = {
  role: "user" | "lawyer";
  text: string;
};

function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "lawyer",
      text: "Hello, I'm KaloKoT's Digital Lawyer. Upload a tender or ask me anything about procurement law, your constitutional rights, or how to file a complaint.",
    },
  ]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [mascotState, setMascotState] = useState<"idle" | "speaking">("idle");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || thinking) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setThinking(true);
    setMascotState("speaking");

    try {
      // Try with constitution context
      let answer = "";
      try {
        const resp = await counselQuestion({
          question: q,
          jurisdiction: "NEPAL",
          tender_context: "General legal inquiry about Nepali law.",
        });
        answer = resp.answer;
      } catch {
        // Fallback if backend not running
        answer = `I understand you're asking about: "${q}". To give you a precise answer grounded in law, I need my backend connected — but I can guide you based on general principles. Could you tell me more about your specific situation or the tender you're looking at?`;
      }

      setMessages((prev) => [...prev, { role: "lawyer", text: answer }]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "lawyer",
          text: "Sorry, I couldn't reach my legal knowledge base. Please make sure the server is running.",
        },
      ]);
    } finally {
      setThinking(false);
      setMascotState("idle");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <main className="relative flex h-screen w-full flex-col bg-[color:var(--noir)] text-cream">
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
          Digital Lawyer
        </span>
        <Link
          to="/analysis-report"
          className="inline-flex items-center gap-2 text-xs tracking-[0.24em] uppercase transition-colors hover:text-[color:var(--gold)]"
          style={{ color: "var(--muted-ink)" }}
        >
          <FileText className="h-3.5 w-3.5" />
          Report
        </Link>
      </header>

      {/* Chat area */}
      <div className="relative z-10 flex flex-1 flex-col overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-3 py-3 md:px-8 md:py-4">
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-3 ${
                  msg.role === "user" ? "flex-row-reverse" : "flex-row"
                }`}
              >
                {/* Avatar */}
                {msg.role === "lawyer" && (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[color:var(--noir-2)] ring-1 ring-[color:var(--gold)]/20">
                    <Scale className="h-4 w-4" style={{ color: "var(--gold)" }} />
                  </div>
                )}
                {msg.role === "user" && (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/5 text-xs tracking-[0.12em] uppercase text-muted-ink">
                    You
                  </div>
                )}

                {/* Bubble */}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "rounded-tr-md"
                      : "rounded-tl-md"
                  }`}
                  style={{
                    background:
                      msg.role === "user"
                        ? "linear-gradient(135deg, color-mix(in oklab, var(--gold) 20%, transparent), color-mix(in oklab, var(--gold) 8%, transparent))"
                        : "color-mix(in oklab, white 6%, transparent)",
                    border:
                      msg.role === "user"
                        ? "1px solid color-mix(in oklab, var(--gold) 20%, transparent)"
                        : "1px solid color-mix(in oklab, white 8%, transparent)",
                    color: msg.role === "user" ? "var(--cream)" : "var(--cream)",
                  }}
                >
                  {msg.text}
                </div>
              </div>
            ))}

            {/* Thinking indicator */}
            {thinking && (
              <div className="flex gap-3">
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[color:var(--noir-2)] ring-1 ring-[color:var(--gold)]/20">
                  <Scale className="h-4 w-4" style={{ color: "var(--gold)" }} />
                </div>
                <div
                  className="flex items-center gap-2 rounded-2xl rounded-tl-md px-4 py-3"
                  style={{
                    background: "color-mix(in oklab, white 6%, transparent)",
                    border: "1px solid color-mix(in oklab, white 8%, transparent)",
                  }}
                >
                  <span
                    className="inline-block h-2 w-2 animate-pulse rounded-full"
                    style={{ backgroundColor: "var(--gold)" }}
                  />
                  <span
                    className="inline-block h-2 w-2 animate-pulse rounded-full"
                    style={{
                      backgroundColor: "var(--gold)",
                      animationDelay: "0.15s",
                    }}
                  />
                  <span
                    className="inline-block h-2 w-2 animate-pulse rounded-full"
                    style={{
                      backgroundColor: "var(--gold)",
                      animationDelay: "0.3s",
                    }}
                  />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input bar */}
        <div
          className="relative z-10 border-t px-3 py-3 md:px-8 md:py-4"
          style={{ borderColor: "color-mix(in oklab, white 8%, transparent)" }}
        >
          <div className="mx-auto flex max-w-3xl items-center gap-3">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about a tender, law, or your rights…"
              className="flex-1 rounded-2xl bg-white/5 px-4 py-3 text-sm text-cream placeholder:text-muted-ink focus:outline-none focus:ring-1"
              style={{
                border: "1px solid color-mix(in oklab, white 10%, transparent)",
                color: "var(--cream)",
                "--tw-ring-color": "color-mix(in oklab, var(--gold) 40%, transparent)",
              } as React.CSSProperties}
              disabled={thinking}
            />
            <button
              onClick={handleSend}
              disabled={thinking || !input.trim()}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all hover:scale-105 disabled:opacity-40"
              style={{
                background:
                  "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
                color: "var(--noir)",
                boxShadow:
                  "0 8px 24px -8px color-mix(in oklab, var(--gold) 60%, transparent)",
              }}
              aria-label="Send"
            >
              <Send className="h-4 w-4" strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>

      {/* Mascot — floating bottom-right */}
      <div className="pointer-events-none fixed bottom-20 right-4 z-30 md:bottom-28 md:right-10">
        <LowPolyLawyer
          state={mascotState}
          className="h-16 w-auto opacity-30 drop-shadow-[0_10px_30px_rgba(0,0,0,0.6)] md:h-32 md:opacity-40"
        />
      </div>
    </main>
  );
}

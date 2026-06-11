import { useRef, useState } from "react";
import { Paperclip, ArrowUp, Plus, ClipboardCheck, FileDown } from "lucide-react";
import { Link } from "@tanstack/react-router";

type Props = {
  onActiveChange?: (active: boolean) => void;
};

export function HeroDock({ onActiveChange }: Props) {
  const [value, setValue] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const setActive = (v: boolean) => onActiveChange?.(v);

  const handleFiles = (files: FileList | null) => {
    const f = files?.[0];
    if (f) {
      setFileName(f.name);
      setActive(true);
      setTimeout(() => setActive(false), 2400);
    }
  };

  return (
    <div
      className="pointer-events-auto w-full max-w-[720px] px-4"
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      {/* Drag-over outline */}
      <div
        className={`mb-3 text-center text-xs tracking-[0.18em] uppercase transition-opacity ${
          dragOver ? "text-gold opacity-100" : "text-muted-ink opacity-70"
        }`}
        style={{ color: dragOver ? "var(--gold)" : "var(--muted-ink)" }}
      >
        {dragOver
          ? "Drop the tender — we'll take it from here"
          : "Not sure where to start? Just paste a link or drop the PDF."}
      </div>

      {/* Chat input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!value.trim()) return;
          setActive(true);
          setTimeout(() => setActive(false), 2800);
          setValue("");
        }}
        className={`glass flex items-center gap-2 rounded-2xl px-3 py-2.5 transition-all ${
          dragOver ? "ring-2 ring-[color:var(--gold)]" : ""
        }`}
      >
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-cream/70 transition-colors hover:bg-white/5 hover:text-[color:var(--gold)]"
          aria-label="Attach a tender PDF"
        >
          <Paperclip className="h-5 w-5" />
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setActive(true)}
          onBlur={() => setActive(false)}
          placeholder="Ask about a tender, or drop the file here…"
          className="flex-1 bg-transparent text-[15px] text-cream placeholder:text-muted-ink focus:outline-none"
          style={{ color: "var(--cream)" }}
        />
        <button
          type="submit"
          aria-label="Send"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-transform hover:scale-105"
          style={{
            background:
              "linear-gradient(135deg, var(--gold), oklch(0.62 0.13 70))",
            color: "var(--noir)",
            boxShadow:
              "0 8px 24px -8px color-mix(in oklab, var(--gold) 60%, transparent)",
          }}
        >
          <ArrowUp className="h-5 w-5" strokeWidth={2.5} />
        </button>
      </form>

      {/* Upload pill + side actions */}
      <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
        <Link
          to="/analysis-report"
          hash="evidence-checklist"
          className="glass inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-cream transition-all hover:scale-[1.02]"
          style={{ color: "var(--cream)" }}
        >
          <ClipboardCheck className="h-4 w-4" style={{ color: "var(--gold)" }} />
          <span>Evidence Checklist</span>
        </Link>

        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="glass inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium text-cream transition-all hover:scale-[1.02]"
          style={{ color: "var(--cream)" }}
        >
          <Plus className="h-4 w-4" style={{ color: "var(--gold)" }} />
          <span>Upload tender PDF</span>
        </button>

        <Link
          to="/analysis-report"
          hash="export-complaint"
          className="glass inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-cream transition-all hover:scale-[1.02]"
          style={{ color: "var(--cream)" }}
        >
          <FileDown className="h-4 w-4" style={{ color: "var(--gold)" }} />
          <span>Export Complaint</span>
        </Link>

        {fileName && (
          <span
            className="w-full text-center text-xs"
            style={{ color: "var(--gold-soft)" }}
          >
            {fileName}
          </span>
        )}
      </div>
    </div>
  );
}

export function Backdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* base gradient */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 90% 60% at 50% 35%, oklch(0.20 0.01 60) 0%, oklch(0.12 0.005 60) 55%, oklch(0.08 0.005 60) 100%)",
        }}
      />
      {/* vertical gold shaft behind figure */}
      <div
        className="absolute left-1/2 top-0 h-full w-[42rem] -translate-x-1/2 opacity-60"
        style={{
          background:
            "radial-gradient(ellipse 40% 80% at 50% 40%, color-mix(in oklab, var(--gold) 14%, transparent), transparent 70%)",
          filter: "blur(20px)",
        }}
      />
      {/* floor glow */}
      <div
        className="absolute bottom-0 left-1/2 h-64 w-[60rem] -translate-x-1/2"
        style={{
          background:
            "radial-gradient(ellipse 50% 100% at 50% 100%, color-mix(in oklab, var(--gold) 10%, transparent), transparent 70%)",
        }}
      />
      {/* vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 100% 80% at 50% 50%, transparent 55%, oklch(0.05 0.005 60) 100%)",
        }}
      />
      {/* grain */}
      <div className="grain absolute inset-0" />
    </div>
  );
}

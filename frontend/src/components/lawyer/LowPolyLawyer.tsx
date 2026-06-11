import type React from "react";

type Props = {
  state?: "idle" | "speaking";
  className?: string;
};

const C: Record<string, string> = {
  W: "#f5efe2", // white hair
  w: "#d8cfbb", // hair shadow
  G: "#c9a84c", // gold (visor, tie)
  K: "#e8c39a", // skin
  M: "#0e0e10", // mustache
  S: "#efe7d2", // shirt
  B: "#1f1d1b", // suit base
  b: "#2c2926", // suit mid
  d: "#080808", // suit outline
  T: "#c9a84c", // tie
  P: "#f0d78c", // pocket square
};

function Pixels({
  art,
  x = 0,
  y = 0,
}: {
  art: string;
  x?: number;
  y?: number;
}) {
  const rows = art.replace(/^\n|\n$/g, "").split("\n");
  const out: React.ReactElement[] = [];
  rows.forEach((row, r) => {
    for (let col = 0; col < row.length; col++) {
      const fill = C[row[col]];
      if (!fill) continue;
      out.push(
        <rect
          key={`${r}-${col}`}
          x={x + col}
          y={y + r}
          width={1.02}
          height={1.02}
          fill={fill}
        />,
      );
    }
  });
  return <>{out}</>;
}

/* -------------------------------------------------------------------------- */
/*  Ultra low-res sprite — ~retro 8/16-bit era                                 */
/* -------------------------------------------------------------------------- */

// HEAD — 8 cols × 8 rows
const HEAD = `
.WWWWWW.
WWwwwwWW
WKKKKKKK
WKKKKKKK
GGGGGGGK
KKKKKKKK
KKKMMMKK
.KKKKKK.
`;

// TORSO — 10 cols × 7 rows
const TORSO = `
..SSSS....
.BSSSSB...
BBSTTSBB..
bBBTTBBb..
bPBTTBBb..
bBBTTBBb..
dddddddd..
`;

// LEGS — 10 cols × 5 rows, two separated pillars
const LEGS = `
.BBB.BBB..
.bBd.bBd..
.bBd.bBd..
.dBd.dBd..
.dd...dd..
`;

// ARM — 2 cols × 5 rows (shoulder → hand)
const ARM = `
BB
bd
bd
SS
KK
`;

/* -------------------------------------------------------------------------- */

export function LowPolyLawyer({ state = "idle", className }: Props) {
  return (
    <svg
      data-state={state}
      viewBox="0 0 16 22"
      preserveAspectRatio="xMidYMid meet"
      className={className}
      role="img"
      aria-label="KaloKoT — pixel mascot lawyer"
      shapeRendering="crispEdges"
      style={{ overflow: "visible", imageRendering: "pixelated" }}
    >
      {/* TORSO */}
      <g>
        <Pixels art={TORSO} x={3} y={8} />
      </g>

      {/* HEAD */}
      <g>
        <Pixels art={HEAD} x={4} y={0} />
      </g>

      {/* LEGS — two separated pillars */}
      <g>
        <Pixels art={LEGS} x={3} y={15} />
      </g>

      {/* BACK ARM */}
      <g>
        <Pixels art={ARM} x={2} y={9} />
      </g>

      {/* FRONT ARM */}
      <g>
        <Pixels art={ARM} x={11} y={10} />
      </g>
    </svg>
  );
}

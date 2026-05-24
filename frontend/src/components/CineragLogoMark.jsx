import { Clapperboard } from "lucide-react";

export function CineragLogoMark({ size = 18, className = "" }) {
  return (
    <span
      className={`cinerag-logo-mark inline-flex items-center justify-center rounded-[0.45rem] ${className}`.trim()}
      aria-hidden
    >
      <Clapperboard size={size} strokeWidth={2.15} />
    </span>
  );
}

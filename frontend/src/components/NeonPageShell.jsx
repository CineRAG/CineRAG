import { CinemaNeonBackdrop } from "./CinemaNeonBackdrop.jsx";
import { useTheme } from "../context/ThemeContext.jsx";

export function NeonPageShell({ children, className = "" }) {
  const { isNeon } = useTheme();

  return (
    <div className={`neon-page-shell ${className}`.trim()}>
      {isNeon ? <CinemaNeonBackdrop /> : null}
      <div className="neon-page-shell__content">{children}</div>
    </div>
  );
}

import { createContext, useCallback, useContext, useMemo, useState } from "react";

const AlertVisualContext = createContext(null);
const VALID_LEVELS = new Set(["none", "medium", "critical"]);

function getInitialLevel() {
  return window.location.pathname === "/" ? "critical" : "none";
}

export function AlertVisualProvider({ children }) {
  const [level, setLevelState] = useState(getInitialLevel);

  const setLevel = useCallback((nextLevel) => {
    setLevelState(VALID_LEVELS.has(nextLevel) ? nextLevel : "none");
  }, []);

  const value = useMemo(() => ({ level, setLevel }), [level, setLevel]);
  return <AlertVisualContext.Provider value={value}>{children}</AlertVisualContext.Provider>;
}

export function useAlertVisual() {
  const context = useContext(AlertVisualContext);
  if (!context) throw new Error("useAlertVisual must be used inside AlertVisualProvider");
  return context;
}

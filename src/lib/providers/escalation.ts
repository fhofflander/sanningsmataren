import type { Verdict } from "../types";

const UNCERTAIN_TEXT =
  /saknas|otillräck|oklar|oklart|kunde inte|hittade inte|går ej|ej att avgöra|kan inte avgöras|ingen träff|inga träff/i;

export function shouldEscalateVerdict(verdict: Verdict): boolean {
  if (verdict.omdome === "GÅR EJ ATT AVGÖRA") return true;
  if (verdict.kallor.length === 0) return true;
  return UNCERTAIN_TEXT.test(`${verdict.osakerhet} ${verdict.motivering}`);
}

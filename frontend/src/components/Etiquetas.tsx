import type { EstadoInfraccion, Severidad } from "../api/types";
import { ESTADOS, SEVERIDADES } from "../viewmodels/format";

/** La severidad nunca depende solo del color: lleva forma (marca) y texto. */
const MARCA: Record<Severidad, string> = { LEVE: "▲", GRAVE: "◆", CRITICA: "■" };

export const Severidad_ = ({ valor }: { valor: Severidad }) => (
  <span className={`sev sev-${valor.toLowerCase()}`}><span aria-hidden="true">{MARCA[valor]}</span> {SEVERIDADES[valor]}</span>
);

export const Estado_ = ({ valor }: { valor: EstadoInfraccion }) => (
  <span className={`estado estado-${valor.toLowerCase()}`}>{ESTADOS[valor]}</span>
);

export const Mensaje = ({ tipo, children }: { tipo: "error" | "ok" | "aviso"; children: React.ReactNode }) => (
  <p className={`mensaje mensaje-${tipo}`} role={tipo === "error" ? "alert" : "status"}>{children}</p>
);

export type AuthorityPlane = "DOMAIN" | "FEDERATION" | "EXECUTION";
export type FederationFunction =
  | "GEOMETRY"
  | "FINANCE_ENTITY"
  | "WATER_POWER"
  | "AVIATION_SKY"
  | "UAP_CASES"
  | "SIGNALS_TRIAGE"
  | "DEPENDENCY"
  | "COMPATIBILITY"
  | "PROVENANCE"
  | "CROSS_REPO_JOB"
  | "RELEASE"
  | "LOCKSTEP"
  | "FEDERATION_CERTIFICATION";

export interface AuthorityBinding {
  fn: FederationFunction;
  plane: AuthorityPlane;
  owner: string;
}

export const REQUIRED_BINDINGS: AuthorityBinding[] = [
  { fn: "GEOMETRY", plane: "DOMAIN", owner: "SPIDERWEB" },
  { fn: "FINANCE_ENTITY", plane: "DOMAIN", owner: "MONEYSWEEP" },
  { fn: "WATER_POWER", plane: "DOMAIN", owner: "AGUAYLUZ" },
  { fn: "AVIATION_SKY", plane: "DOMAIN", owner: "SKYWATCHER" },
  { fn: "UAP_CASES", plane: "DOMAIN", owner: "OVNIS" },
  { fn: "SIGNALS_TRIAGE", plane: "DOMAIN", owner: "CENTINELAS" },
  { fn: "DEPENDENCY", plane: "FEDERATION", owner: "THEHUB" },
  { fn: "COMPATIBILITY", plane: "FEDERATION", owner: "THEHUB" },
  { fn: "PROVENANCE", plane: "FEDERATION", owner: "THEHUB" },
  { fn: "CROSS_REPO_JOB", plane: "EXECUTION", owner: "THEHUB" },
  { fn: "RELEASE", plane: "FEDERATION", owner: "THEHUB" },
  { fn: "LOCKSTEP", plane: "FEDERATION", owner: "THEHUB" },
  { fn: "FEDERATION_CERTIFICATION", plane: "FEDERATION", owner: "THEHUB" },
];

export function validateAuthorityBindings(bindings: AuthorityBinding[]) {
  const reasons: string[] = [];
  const byFn = new Map<FederationFunction, AuthorityBinding[]>();
  for (const b of bindings) byFn.set(b.fn, [...(byFn.get(b.fn) ?? []), b]);
  for (const required of REQUIRED_BINDINGS) {
    const rows = byFn.get(required.fn) ?? [];
    if (rows.length === 0) reasons.push(`UNOWNED:${required.fn}`);
    if (rows.length > 1) reasons.push(`DUPLICATE_OWNER:${required.fn}`);
    if (rows.length === 1 && (rows[0].owner !== required.owner || rows[0].plane !== required.plane)) {
      reasons.push(`AUTHORITY_DRIFT:${required.fn}`);
    }
  }
  return { pass: reasons.length === 0, reasons };
}

export function implicitAuthorityTransferAllowed(): false {
  return false;
}

export function federationCertificationAllowed(args: {
  authorityBindingsPass: boolean;
  producerReceiptsPass: boolean;
  lockstepPass: boolean;
  unresolvedResidue: number;
}) {
  return args.authorityBindingsPass && args.producerReceiptsPass && args.lockstepPass && args.unresolvedResidue === 0;
}

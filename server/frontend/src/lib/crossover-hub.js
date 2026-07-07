// Hub ↔ module crossover generation.
// The Hub (INTSYS-PR parent control plane) governs every module via FederationTasks,
// FederationManifest, ValidationGates, and IntegrationStatus. These are EXPLICIT control
// relationships (a task/gate/manifest/integration literally names a module via program_id),
// so they are emitted as PendingReview control links — never silent Verified.
//
// Module ownership is preserved: the Hub reads module program records, it does not own them.

// Map a Programs record to its federation module name.
function moduleForProgram(program) {
  if (!program) return null;
  const name = (program.name || program.repo_name || "").toString();
  const m = name.match(/(Spiderweb|Ovnis|AguaYLuz|MoneySweep|Skywatcher)/i);
  if (!m) return null;
  const key = m[1].toLowerCase();
  return {
    spiderweb: "Spiderweb-PR", ovnis: "Ovnis-PR", aguayluz: "AguaYLuz-PR",
    moneysweep: "MoneySweep-PR", skywatcher: "Skywatcher-PR",
  }[key] || null;
}

// Build crossovers from a Hub-control ledger keyed on program_id.
// `mk` is the normalized-record factory from the engine.
function hubLinks({ mk, rows, programModule, type, idField, labelField, sourceModule, statusFor, rationaleFor, tier }) {
  const out = [];
  for (const r of rows) {
    const targetModule = programModule[r.program_id];
    if (!targetModule) continue; // only emit links to one of the 5 named modules
    const rid = r[idField] || r.id;
    out.push(mk({
      crossover_id: `hub-${type}-${rid}`,
      source_module: "Hub",
      source_record_id: rid,
      source_label: r[labelField] || rid,
      target_module: targetModule,
      target_record_id: r.program_id,
      target_label: targetModule,
      correlation_type: "Graph",
      status: statusFor ? statusFor(r) : "PendingReview",
      verified: false,
      confidence_score: 60,
      rationale: rationaleFor(r, targetModule),
      evidence_tier: tier || "T2",
      created_from: "explicit_link",
      matching_criteria: [`hub_${type}_control_link`],
    }));
  }
  return out;
}

// Generate all Hub ↔ module control crossovers.
export function computeHubCrossovers({ mk, programs, federationTasks, federationManifests, validationGates, integrationStatus }) {
  const programModule = {};
  for (const p of programs) {
    const mod = moduleForProgram(p);
    if (mod) programModule[p.id] = mod;
  }

  const results = [];

  // Tasks: Hub-tracked work items scoped to a module.
  results.push(...hubLinks({
    mk, rows: federationTasks, programModule, type: "task", idField: "task_id", labelField: "title",
    statusFor: (t) => (t.status === "Done" ? "Verified" : "PendingReview"),
    rationaleFor: (t, m) => `Hub federation task "${t.title || t.task_id}" (${t.status || "—"}) governs ${m}. Control-plane work item — review status reflects task progress.`,
  }));

  // Manifests: Hub capability/readiness declarations per module.
  results.push(...hubLinks({
    mk, rows: federationManifests, programModule, type: "manifest", idField: "manifest_id", labelField: "manifest_id",
    statusFor: (m) => (m.status === "Stable" ? "Verified" : "PendingReview"),
    rationaleFor: (mf, m) => `Hub federation manifest (${mf.module_role || "module"}, ${mf.status || "—"}) declares shared entities/integrations for ${m}.`,
  }));

  // Validation gates: Hub-enforced parity/readiness gates per module.
  results.push(...hubLinks({
    mk, rows: validationGates, programModule, type: "gate", idField: "gate_id", labelField: "gate_name",
    statusFor: (g) => (g.status === "Passed" ? "Verified" : g.status === "Failed" || g.status === "Blocked" ? "Contradicted" : "PendingReview"),
    rationaleFor: (g, m) => `Hub validation gate "${g.gate_name || g.gate_id}" (${g.status || "—"}${g.blocking ? ", blocking" : ""}) gates ${m} readiness.`,
    tier: "T1",
  }));

  // Integration status: Hub-tracked integration/sync state per module.
  results.push(...hubLinks({
    mk, rows: integrationStatus, programModule, type: "integration", idField: "integration_id", labelField: "integration_name",
    statusFor: (i) => (i.status === "Connected" || i.status === "Ready" ? "Verified" : i.status === "Error" || i.status === "Blocked" ? "Contradicted" : "PendingReview"),
    rationaleFor: (i, m) => `Hub integration "${i.integration_name || i.integration_id}" is ${i.status || "—"} for ${m}.${i.blocking_reason ? ` Blocker: ${i.blocking_reason}.` : ""}`,
  }));

  return results;
}
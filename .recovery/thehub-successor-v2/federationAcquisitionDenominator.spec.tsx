import { FEDERATION_ACQUISITION_ROWS, evaluateFederationAcquisition } from "./federationAcquisitionDenominator";

const byApp = (name: (typeof FEDERATION_ACQUISITION_ROWS)[number]["app"]) =>
  FEDERATION_ACQUISITION_ROWS.find(row => row.app === name)!;

describe("Federation authoritative acquisition denominator v2", () => {
  it("freezes exactly seven unique app rows and all rendered 1440/393/430 evidence as PASS", () => {
    expect(FEDERATION_ACQUISITION_ROWS.length).toBe(7);
    expect(new Set(FEDERATION_ACQUISITION_ROWS.map(row => row.app)).size).toBe(7);
    expect(FEDERATION_ACQUISITION_ROWS.every(row => row.renderedDesktop393430 === "PASS")).toBeTrue();
  });

  it("closes Spiderweb's 16-provider denominator without promoting readiness into acquisition certification", () => {
    const row = byApp("Spiderweb");
    expect(row.denominatorCount).toBe(16);
    expect(
      Number(row.facts.ready) +
      Number(row.facts.providerBindingOpen) +
      Number(row.facts.readyWithCredentials) +
      Number(row.facts.readySpecialized) +
      Number(row.facts.resolverOnly)
    ).toBe(16);
    expect(row.acquisitionStatus).toBe("OPEN");
  });

  it("preserves MoneySweep's 167-source historical denominator while terminal manifestation closure stays open", () => {
    const row = byApp("MoneySweep");
    expect(row.denominatorCount).toBe(167);
    expect(row.terminalCount).toBeNull();
    expect(row.acquisitionStatus).toBe("OPEN");
  });

  it("closes AguaYLuz historical 8-vector arithmetic without substituting it for current conditions", () => {
    const row = byApp("AguaYLuz");
    expect(Number(row.facts.historicalLoaded) + Number(row.facts.historicalEmpty)).toBe(8);
    expect(row.facts.historicalToCurrentSubstitution).toBe("DENY");
    expect(row.acquisitionStatus).toBe("OPEN");
  });

  it("freezes six Skywatcher provider families and keeps credential/RLSM residue explicit", () => {
    const row = byApp("Skywatcher");
    expect(row.denominatorCount).toBe(6);
    expect(row.credentialDeferredCount).toBe(1);
    expect(row.facts.rlsmSeparatePackageResidue).toBe(1);
    expect(row.acquisitionStatus).toBe("OPEN");
  });

  it("preserves OVNIS 244 references and zero verified byte artifacts", () => {
    const row = byApp("OVNIS");
    expect(row.denominatorCount).toBe(244);
    expect(row.facts.verifiedByteArtifacts).toBe(0);
    expect(row.acquisitionStatus).toBe("OPEN");
  });

  it("closes Centinelas feed attempt arithmetic but blocks certification on five external failures", () => {
    const row = byApp("Centinelas");
    expect(Number(row.facts.success) + Number(row.facts.empty) + Number(row.facts.externalFailure)).toBe(60);
    expect(row.facts.recoveredSourceIdentities).toBe(87);
    expect(row.facts.historicalDatabase).toBe("UNAVAILABLE_NO_DUMP");
    expect(row.acquisitionStatus).toBe("BLOCKED");
  });

  it("keeps TheHub outside producer acquisition authority", () => {
    const row = byApp("TheHub");
    expect(row.denominatorStatus).toBe("NOT_APPLICABLE");
    expect(row.acquisitionStatus).toBe("NOT_APPLICABLE");
    expect(row.facts.producerTruthAuthority).toBeFalse();
  });

  it("keeps infrastructure migration blocked while any producer acquisition is open or blocked", () => {
    const result = evaluateFederationAcquisition();
    expect(result.denominatorClosed).toBeTrue();
    expect(result.renderedClosed).toBeTrue();
    expect(result.acquisitionCertified).toBeFalse();
    expect(result.infrastructureMigrationEligible).toBeFalse();
    expect(result.openApps.sort()).toEqual(["AguaYLuz","MoneySweep","OVNIS","Skywatcher","Spiderweb"].sort());
    expect(result.blockedApps).toEqual(["Centinelas"]);
    expect(result.credentialDeferredCount).toBe(3);
    expect(result.residue).toEqual([]);
  });
});

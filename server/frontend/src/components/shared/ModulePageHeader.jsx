import React from "react";
import PageHeader from "@/components/shared/PageHeader";
import { domainAccent } from "@/lib/federation";

// Thin preset over PageHeader: a producer-module header with the domain accent
// tint and domain badge. Keeps module pages on the shared header component.
export default function ModulePageHeader({ module, icon }) {
  return (
    <PageHeader
      icon={icon}
      title={module.name}
      badge={module.domain}
      accent={domainAccent(module.domain)}
      description={<>{module.blurb} · legacy: <span className="font-mono-id">{module.oldName}</span></>}
    />
  );
}

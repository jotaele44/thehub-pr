import React from "react";
import { Inbox } from "lucide-react";
import { FederationEmptyState } from "@pr-federation/react";

// The Hub now renders the same primitive it publishes: this was the reference
// EmptyState the package's FederationEmptyState was modeled on, so consuming it
// here keeps the two from diverging. `icon` stays a component for call-site
// compatibility and is instantiated before being handed over as a node.
export default function EmptyState({ icon: Icon = Inbox, title = "No records", description }) {
  return (
    <FederationEmptyState
      className="py-16"
      icon={<Icon className="h-6 w-6" />}
      title={title}
      description={description}
    />
  );
}
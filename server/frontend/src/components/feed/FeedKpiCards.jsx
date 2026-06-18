import React from "react";
import StatCard from "@/components/shared/StatCard";

// Renders a row of KPI cards. cards: [{ label, value, icon, accent, alert }]
export default function FeedKpiCards({ cards }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
      {cards.map((c) => (
        <StatCard key={c.label} label={c.label} value={c.value} icon={c.icon} accent={c.accent} alert={c.alert} />
      ))}
    </div>
  );
}
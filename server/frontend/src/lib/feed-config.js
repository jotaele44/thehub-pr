// Live-feed polling configuration shared by MoneySweep-PR / AguaYLuz-PR feeds.
// Dashboards auto-refresh every 30s; data older than 2 minutes reads as stale.
export const LIVE_INTERVAL_MS = 30_000;
export const STALE_AFTER_MS = 120_000;

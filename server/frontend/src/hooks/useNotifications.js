import { federation } from "@/api/federationClient";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// "What's new since you last looked." Polls the digest on the same cadence as the
// live feed; the backend ranks critical-first. `ack()` advances the last-seen cursor
// so the badge clears once the user has looked. Degrades to an empty digest if the
// endpoint is unavailable (older backend) so the header never breaks.
const POLL_MS = 30_000;

export function useNotifications() {
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: () => federation.notifications.list(),
    initialData: { count: 0, critical_count: 0, items: [], cursor: null },
    refetchInterval: () => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return false;
      return POLL_MS;
    },
    refetchIntervalInBackground: false,
    retry: 1,
  });

  const ackMut = useMutation({
    mutationFn: (lastSeen) => federation.notifications.ack(lastSeen),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const data = query.data || {};
  const items = data.items || [];
  // Mark everything up to the newest item as seen.
  const markAllRead = () => {
    const newest = items[0]?.occurred_at || items[0]?.observed_at || new Date().toISOString();
    ackMut.mutate(newest);
  };

  return {
    count: data.count || 0,
    criticalCount: data.critical_count || 0,
    items,
    isLoading: query.isLoading,
    markAllRead,
  };
}

import { federation } from "@/api/federationClient";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// Generic list + CRUD hook for a single entity.
// Pass options.refetchInterval (ms) to enable auto-refresh / live polling.
export function useEntityData(entityName, sort = "-created_date", options = {}) {
  const qc = useQueryClient();
  const key = ["entity", entityName, sort];

  const query = useQuery({
    queryKey: key,
    queryFn: () => federation.entities[entityName].list(sort, 500),
    initialData: [],
    // Functional interval: pause polling while the browser tab is hidden so we
    // don't keep hammering sources in background tabs. Returning false skips the
    // tick; Query resumes automatically on the next interval when visible again.
    // TanStack Query also never overlaps fetches and clears the timer on unmount.
    refetchInterval: () => {
      if (!options.refetchInterval) return false;
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return false;
      return options.refetchInterval;
    },
    refetchIntervalInBackground: false,
    retry: 1,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["entity", entityName] });

  const createMut = useMutation({
    mutationFn: (data) => federation.entities[entityName].create(data),
    onSuccess: invalidate,
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => federation.entities[entityName].update(id, data),
    onSuccess: invalidate,
  });

  const deleteMut = useMutation({
    mutationFn: (id) => federation.entities[entityName].delete(id),
    onSuccess: invalidate,
  });

  return {
    rows: query.data || [],
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    dataUpdatedAt: query.dataUpdatedAt,
    create: createMut.mutateAsync,
    update: updateMut.mutateAsync,
    remove: deleteMut.mutateAsync,
    saving: createMut.isPending || updateMut.isPending,
  };
}
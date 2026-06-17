import { useState, useMemo } from "react";

// Generic client-side search + select filtering.
// searchKeys: array of row keys to match against the search string.
// filterDefs: [{ key, label, options }]
export function useTableFilter(rows, searchKeys, filterDefs = []) {
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState(
    Object.fromEntries(filterDefs.map((f) => [f.key, "all"]))
  );

  const onFilterChange = (key, value) => setFilters((f) => ({ ...f, [key]: value }));

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      const matchSearch = !q || searchKeys.some((k) => String(row[k] ?? "").toLowerCase().includes(q));
      const matchFilters = filterDefs.every((f) => filters[f.key] === "all" || String(row[f.key]) === filters[f.key]);
      return matchSearch && matchFilters;
    });
  }, [rows, search, filters, searchKeys, filterDefs]);

  const filterBarProps = {
    search,
    onSearch: setSearch,
    filters: filterDefs.map((f) => ({ ...f, value: filters[f.key] })),
    onFilterChange,
  };

  return { filtered, filterBarProps };
}
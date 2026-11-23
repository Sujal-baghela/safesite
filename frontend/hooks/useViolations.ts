/**
 * TanStack Query hooks for violations.
 * Ready to use in Phase 3 dashboard components.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Violation } from "@/types";

interface ViolationListResponse {
  items: Violation[];
  total: number;
  page: number;
  page_size: number;
}

interface ViolationFilters {
  site_id?: string;
  camera_id?: string;
  type?: string;
  resolved?: boolean;
  page?: number;
  page_size?: number;
}

export function useViolations(filters: ViolationFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });

  return useQuery<ViolationListResponse>({
    queryKey: ["violations", filters],
    queryFn: () => api.get(`/api/v1/violations?${params.toString()}`),
    staleTime: 30_000,
  });
}

export function useViolation(id: string) {
  return useQuery<Violation>({
    queryKey: ["violations", id],
    queryFn: () => api.get(`/api/v1/violations/${id}`),
    enabled: !!id,
  });
}

export function useResolveViolation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, resolved }: { id: string; resolved: boolean }) =>
      api.patch(`/api/v1/violations/${id}/resolve`, { resolved }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
    },
  });
}

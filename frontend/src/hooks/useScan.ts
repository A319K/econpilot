import { useMutation, useQueryClient } from "@tanstack/react-query"
import { scanApi } from "../api/scan"
import type { ScanRequest } from "../api/types"

export function useScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ScanRequest) => scanApi.run(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
  })
}

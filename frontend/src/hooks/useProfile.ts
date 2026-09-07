import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { profileApi } from "../api/profile"
import type { Profile, ProfileWrite } from "../api/types"
import { queryKeys } from "./queryKeys"

export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile(),
    queryFn: () => profileApi.get(),
  })
}

export function useSaveProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ProfileWrite) => profileApi.save(payload),
    onSuccess: (saved: Profile) => {
      // Seed the cache with the server's version so the form immediately
      // reflects what was actually written (and clears is_placeholder).
      queryClient.setQueryData(queryKeys.profile(), saved)
    },
  })
}

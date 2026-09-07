import { request } from "./client"
import type { Profile, ProfileWrite } from "./types"

export const profileApi = {
  get: () => request<Profile>("/profile"),

  save: (payload: ProfileWrite) => request<Profile>("/profile", { method: "PUT", body: payload }),
}

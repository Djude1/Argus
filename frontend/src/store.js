import { create } from "zustand";

import { setAccessToken } from "./api";

const storedToken = window.localStorage.getItem("argus_access_token");
setAccessToken(storedToken);

export const useArgusStore = create((set) => ({
  accessToken: storedToken,
  setToken: (token) => {
    if (token) {
      window.localStorage.setItem("argus_access_token", token);
    } else {
      window.localStorage.removeItem("argus_access_token");
    }
    setAccessToken(token);
    set({ accessToken: token });
  },
}));

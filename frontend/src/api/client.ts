import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "https://parser-bestmoto.onrender.com";

const api = axios.create({
  baseURL: API_BASE_URL.replace(/\/$/, "") + "/api",
  withCredentials: false,
});

let initDataCache = "";

export const initApiClient = (initData: string) => {
  if (!initData) {
    throw new Error("initData отсутствует");
  }
  initDataCache = initData;
  api.defaults.headers.common["X-Telegram-Init-Data"] = initData;
};

api.interceptors.request.use((config) => {
  if (!initDataCache) {
    throw new Error("Нет валидного initData");
  }
  return config;
});

export default api;
export { API_BASE_URL };


import axios from "axios";

// 后端 HTTP API base URL。可通过 Vite 环境变量覆盖。
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  // 索引仓库 / 重建索引可能需要较长时间，这里适当放宽超时时间
  timeout: 180000
});

let adminToken: string | null = null;

export function setAdminToken(token: string | null) {
  adminToken = token;
  if (token) {
    apiClient.defaults.headers.common["X-Admin-Token"] = token;
  } else {
    delete apiClient.defaults.headers.common["X-Admin-Token"];
  }
}

export function getAdminToken(): string | null {
  return adminToken;
}

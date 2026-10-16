import axios, {
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";
import Constants from "expo-constants";

import { useAuthStore } from "../store/auth";

export const API_URL =
  (Constants.expoConfig?.extra?.apiUrl as string | undefined) ??
  process.env.EXPO_PUBLIC_API_URL ??
  "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 15000,
});

type RetriableRequest = InternalAxiosRequestConfig & { _retry?: boolean };

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function performRefresh(): Promise<string | null> {
  const { refreshToken, setAccessToken, clearSession } = useAuthStore.getState();
  if (!refreshToken) return null;

  try {
    const response = await axios.post<{ access_token: string }>(
      `${API_URL}/auth/refresh`,
      { refresh_token: refreshToken },
    );
    await setAccessToken(response.data.access_token);
    return response.data.access_token;
  } catch (err) {
    await clearSession();
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableRequest | undefined;

    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;

      refreshPromise = refreshPromise ?? performRefresh();
      const token = await refreshPromise;
      refreshPromise = null;

      if (token) {
        original.headers.set("Authorization", `Bearer ${token}`);
        return api(original as AxiosRequestConfig);
      }
    }

    error.message = friendlyMessage(error);
    return Promise.reject(error);
  },
);

/**
 * Forms show `err.message` in an alert; Axios' default ("Request failed with
 * status code 422") tells the user nothing. The AxiosError itself is kept,
 * so callers can still branch on `error.response.status`.
 */
function friendlyMessage(error: AxiosError): string {
  const status = error.response?.status;
  if (!error.response) {
    return error.code === "ECONNABORTED"
      ? "El servidor tardó demasiado en responder. Probá de nuevo en un momento."
      : "No hay conexión con el servidor. Revisá tu internet y probá de nuevo.";
  }
  if (status === 422) return "Algún dato no es válido (¿un monto demasiado grande?). Revisalo y probá de nuevo.";
  if (status === 401) return "Tu sesión venció. Volvé a iniciar sesión.";
  if (status === 404) return "No encontramos lo que buscabas; puede que ya se haya borrado.";
  if (status && status >= 500) return "Hubo un error en el servidor. Probá de nuevo en un momento.";
  return error.message;
}

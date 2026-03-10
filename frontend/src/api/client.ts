export type Product = {
  product_id: string;
  handle: string;
  title: string;
  thumbnail_url?: string | null;
};

export type ProductAttributes = {
  product_id: string;
  ancho_cm: number | null;
  composicion: string | null;
};

export type BatchGetOut = {
  ok: boolean;
  mode: "get";
  store_id: string;
  found: number;
  missing_products: string[];
  items: ProductAttributes[];
};

export type BatchUpsertInItem = {
  product_id: string;
  ancho_cm?: number | null;
  composicion?: string | null;
};

export type BatchUpsertOut = {
  ok: boolean;
  mode: "upsert";
  store_id: string;
  received: number;
  inserted: number;
  updated: number;
  deleted: number;
  missing_products: string[];
  items: ProductAttributes[];
};

export type ImportCsvOut = {
  ok: boolean;
  rows_received: number;
  rows_processed: number;
  missing_products: string[];
};

type LoginIn = {
  username: string;
  password: string;
};

type LoginOut = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const STORE_ID = import.meta.env.VITE_STORE_ID || "";

// storage keys
const LS_TOKEN = "tnmvp_token";
const LS_EXPIRES_AT = "tnmvp_token_expires_at";
const SS_TOKEN = "tnmvp_token";
const SS_EXPIRES_AT = "tnmvp_token_expires_at";

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

export function getStoreId(): string {
  return STORE_ID;
}

function buildUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

function readStoredToken():
  | { token: string; expiresAt: number; storage: "local" | "session" }
  | null {
  const lsToken = localStorage.getItem(LS_TOKEN);
  const lsExp = localStorage.getItem(LS_EXPIRES_AT);
  if (lsToken && lsExp) {
    const exp = parseInt(lsExp, 10);
    if (!Number.isNaN(exp)) {
      return { token: lsToken, expiresAt: exp, storage: "local" };
    }
  }

  const ssToken = sessionStorage.getItem(SS_TOKEN);
  const ssExp = sessionStorage.getItem(SS_EXPIRES_AT);
  if (ssToken && ssExp) {
    const exp = parseInt(ssExp, 10);
    if (!Number.isNaN(exp)) {
      return { token: ssToken, expiresAt: exp, storage: "session" };
    }
  }

  return null;
}

export function clearAuth() {
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_EXPIRES_AT);
  sessionStorage.removeItem(SS_TOKEN);
  sessionStorage.removeItem(SS_EXPIRES_AT);
}

export function isAuthed(): boolean {
  const item = readStoredToken();
  if (!item) return false;

  if (nowSeconds() >= item.expiresAt) {
    clearAuth();
    return false;
  }

  return true;
}

function getTokenOrNull(): string | null {
  const item = readStoredToken();
  if (!item) return null;

  if (nowSeconds() >= item.expiresAt) {
    clearAuth();
    return null;
  }

  return item.token;
}

function storeToken(token: string, expiresInSeconds: number, remember: boolean) {
  const exp = nowSeconds() + Math.max(1, expiresInSeconds);

  clearAuth();

  if (remember) {
    localStorage.setItem(LS_TOKEN, token);
    localStorage.setItem(LS_EXPIRES_AT, String(exp));
  } else {
    sessionStorage.setItem(SS_TOKEN, token);
    sessionStorage.setItem(SS_EXPIRES_AT, String(exp));
  }
}

function fixErrorMessage(data: any): string {
  if (data?.error?.message) return String(data.error.message);
  if (data?.detail?.message) return String(data.detail.message);
  if (data?.detail?.code) return String(data.detail.code);
  if (data?.error?.code) return String(data.error.code);
  if (typeof data === "string") return data;
  return "Error";
}

async function http<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getTokenOrNull();

  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string> | undefined),
  };

  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(buildUrl(path), {
    ...opts,
    headers,
  });

  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  const data = isJson ? await res.json() : await res.text();

  if (res.status === 401) {
    clearAuth();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new Error("Sesión expirada.");
  }

  if (!res.ok) {
    throw new Error(fixErrorMessage(data));
  }

  return data as T;
}

async function httpBlob(path: string, opts: RequestInit = {}): Promise<Blob> {
  const token = getTokenOrNull();

  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string> | undefined),
  };

  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(buildUrl(path), {
    ...opts,
    headers,
  });

  if (res.status === 401) {
    clearAuth();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new Error("Sesión expirada.");
  }

  if (!res.ok) {
    const isJson = (res.headers.get("content-type") || "").includes("application/json");
    const data = isJson ? await res.json() : await res.text();
    throw new Error(fixErrorMessage(data));
  }

  return await res.blob();
}

// ------------------------------------------------------
// AUTH
// ------------------------------------------------------
export async function apiLogin(payload: LoginIn, remember: boolean): Promise<LoginOut> {
  const out = await http<LoginOut>("/admin/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  storeToken(out.access_token, out.expires_in, remember);
  return out;
}

// ------------------------------------------------------
// MOJIBAKE
// ------------------------------------------------------
export function fixMojibake(s: string): string {
  return s;
}

// ------------------------------------------------------
// PRODUCTS
// ------------------------------------------------------
export async function listProducts(storeId: string): Promise<Product[]> {
  const sid = storeId || STORE_ID;
  if (!sid) throw new Error("Falta VITE_STORE_ID en .env del frontend.");

  return http<Product[]>(`/admin/products?store_id=${encodeURIComponent(sid)}`);
}

export async function batchGetAttributes(
  productIds: string[],
  storeId: string,
): Promise<BatchGetOut> {
  const sid = storeId || STORE_ID;
  if (!sid) throw new Error("Falta VITE_STORE_ID en .env del frontend.");

  return http<BatchGetOut>("/admin/products/attributes/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: "get",
      store_id: sid,
      product_ids: productIds,
    }),
  });
}

export async function batchUpsertAttributes(
  items: BatchUpsertInItem[],
  storeId: string,
): Promise<BatchUpsertOut> {
  const sid = storeId || STORE_ID;
  if (!sid) throw new Error("Falta VITE_STORE_ID en .env del frontend.");

  const idem = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;

  return http<BatchUpsertOut>("/admin/products/attributes/batch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idem,
    },
    body: JSON.stringify({
      mode: "upsert",
      store_id: sid,
      items,
    }),
  });
}

export async function getProductAttributes(
  productId: string,
  storeId: string,
): Promise<ProductAttributes> {
  const sid = storeId || STORE_ID;
  if (!sid) throw new Error("Falta VITE_STORE_ID en .env del frontend.");

  return http<ProductAttributes>(
    `/admin/products/${encodeURIComponent(productId)}/attributes?store_id=${encodeURIComponent(sid)}`,
  );
}

export async function updateProductAttributes(
  productId: string,
  storeId: string,
  payload: { ancho_cm: number | null; composicion: string | null },
): Promise<{ ok: boolean }> {
  const sid = storeId || STORE_ID;
  if (!sid) throw new Error("Falta VITE_STORE_ID en .env del frontend.");

  return http<{ ok: boolean }>(
    `/admin/products/${encodeURIComponent(productId)}/attributes?store_id=${encodeURIComponent(sid)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

// ------------------------------------------------------
// CSV
// ------------------------------------------------------
export async function exportCsvFile(storeId: string): Promise<Blob> {
  const sid = storeId || STORE_ID;
  if (!sid) throw new Error("Falta VITE_STORE_ID en .env del frontend.");

  return httpBlob(`/admin/export/csv?store_id=${encodeURIComponent(sid)}`, {
    method: "GET",
  });
}

export async function importCsvFile(
  file: File,
  storeId: string,
): Promise<ImportCsvOut> {
  const sid = storeId || STORE_ID;
  if (!sid) throw new Error("Falta VITE_STORE_ID en .env del frontend.");

  const form = new FormData();
  form.append("file", file);

  return http<ImportCsvOut>(
    `/admin/import/csv?store_id=${encodeURIComponent(sid)}`,
    {
      method: "POST",
      body: form,
    },
  );
}
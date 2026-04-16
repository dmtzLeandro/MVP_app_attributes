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
  email: string;
  password: string;
};

type LoginOut = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  store_id: string;
  email: string;
};

export type RegisterIn = {
  registration_token: string;
  email: string;
  password: string;
  password_confirm: string;
};

export type RegisterOut = {
  ok: boolean;
  pending: boolean;
  email: string;
  store_id: string;
  verification_sent: boolean;
  verification_url: string | null;
};

type SessionUser = {
  email: string;
  store_id: string;
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

// storage keys
const LS_TOKEN = "tnmvp_token";
const LS_EXPIRES_AT = "tnmvp_token_expires_at";
const LS_USER = "tnmvp_user";

const SS_TOKEN = "tnmvp_token";
const SS_EXPIRES_AT = "tnmvp_token_expires_at";
const SS_USER = "tnmvp_user";

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
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

function readStoredUser(): SessionUser | null {
  const rawLocal = localStorage.getItem(LS_USER);
  if (rawLocal) {
    try {
      return JSON.parse(rawLocal) as SessionUser;
    } catch {
      localStorage.removeItem(LS_USER);
    }
  }

  const rawSession = sessionStorage.getItem(SS_USER);
  if (rawSession) {
    try {
      return JSON.parse(rawSession) as SessionUser;
    } catch {
      sessionStorage.removeItem(SS_USER);
    }
  }

  return null;
}

export function getSessionUser(): SessionUser | null {
  if (!isAuthed()) return null;
  return readStoredUser();
}

export function getStoreId(): string {
  return getSessionUser()?.store_id || "";
}

export function getSessionEmail(): string {
  return getSessionUser()?.email || "";
}

export function clearAuth() {
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_EXPIRES_AT);
  localStorage.removeItem(LS_USER);

  sessionStorage.removeItem(SS_TOKEN);
  sessionStorage.removeItem(SS_EXPIRES_AT);
  sessionStorage.removeItem(SS_USER);
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

function storeToken(
  token: string,
  expiresInSeconds: number,
  remember: boolean,
  user: SessionUser,
) {
  const exp = nowSeconds() + Math.max(1, expiresInSeconds);

  clearAuth();

  if (remember) {
    localStorage.setItem(LS_TOKEN, token);
    localStorage.setItem(LS_EXPIRES_AT, String(exp));
    localStorage.setItem(LS_USER, JSON.stringify(user));
  } else {
    sessionStorage.setItem(SS_TOKEN, token);
    sessionStorage.setItem(SS_EXPIRES_AT, String(exp));
    sessionStorage.setItem(SS_USER, JSON.stringify(user));
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

  const isJson = (res.headers.get("content-type") || "").includes(
    "application/json",
  );
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
    const isJson = (res.headers.get("content-type") || "").includes(
      "application/json",
    );
    const data = isJson ? await res.json() : await res.text();
    throw new Error(fixErrorMessage(data));
  }

  return await res.blob();
}

// ------------------------------------------------------
// AUTH
// ------------------------------------------------------
export async function apiLogin(
  payload: LoginIn,
  remember: boolean,
): Promise<LoginOut> {
  const out = await http<LoginOut>("/admin/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  storeToken(out.access_token, out.expires_in, remember, {
    email: out.email,
    store_id: out.store_id,
  });

  return out;
}

export async function apiRegister(payload: RegisterIn): Promise<RegisterOut> {
  return http<RegisterOut>("/admin/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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
export async function listProducts(): Promise<Product[]> {
  return http<Product[]>("/admin/products");
}

export async function batchGetAttributes(
  productIds: string[],
): Promise<BatchGetOut> {
  const sessionUser = getSessionUser();
  if (!sessionUser?.store_id) {
    throw new Error("No se encontró la tienda de la sesión.");
  }

  return http<BatchGetOut>("/admin/products/attributes/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: "get",
      product_ids: productIds,
    }),
  });
}

export async function batchUpsertAttributes(
  items: BatchUpsertInItem[],
): Promise<BatchUpsertOut> {
  const sessionUser = getSessionUser();
  if (!sessionUser?.store_id) {
    throw new Error("No se encontró la tienda de la sesión.");
  }

  const idem = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;

  return http<BatchUpsertOut>("/admin/products/attributes/batch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idem,
    },
    body: JSON.stringify({
      mode: "upsert",
      items,
    }),
  });
}

export async function getProductAttributes(
  productId: string,
): Promise<ProductAttributes> {
  const sessionUser = getSessionUser();
  if (!sessionUser?.store_id) {
    throw new Error("No se encontró la tienda de la sesión.");
  }

  return http<ProductAttributes>(
    `/admin/products/${encodeURIComponent(productId)}/attributes`,
  );
}

export async function updateProductAttributes(
  productId: string,
  payload: { ancho_cm: number | null; composicion: string | null },
): Promise<{ ok: boolean }> {
  const sessionUser = getSessionUser();
  if (!sessionUser?.store_id) {
    throw new Error("No se encontró la tienda de la sesión.");
  }

  return http<{ ok: boolean }>(
    `/admin/products/${encodeURIComponent(productId)}/attributes`,
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
export async function exportCsvFile(): Promise<Blob> {
  const sessionUser = getSessionUser();
  if (!sessionUser?.store_id) {
    throw new Error("No se encontró la tienda de la sesión.");
  }

  return httpBlob("/admin/export/csv", {
    method: "GET",
  });
}

export async function importCsvFile(file: File): Promise<ImportCsvOut> {
  const sessionUser = getSessionUser();
  if (!sessionUser?.store_id) {
    throw new Error("No se encontró la tienda de la sesión.");
  }

  const form = new FormData();
  form.append("file", file);

  return http<ImportCsvOut>("/admin/import/csv", {
    method: "POST",
    body: form,
  });
}

const API_BASE = import.meta.env.VITE_API_BASE as string;
const STORE_ID = import.meta.env.VITE_STORE_ID as string;

export type Product = {
  product_id: string;
  handle: string;
  title: string;
};

export type ProductAttributes = {
  product_id: string;
  store_id: string;
  ancho_cm: number | null;
  composicion: string | null;
};

type BatchGetResponse = {
  ok: true;
  mode: "get";
  store_id: string;
  found: number;
  missing_products: string[];
  items: ProductAttributes[];
};

type BatchUpsertResponse = {
  ok: true;
  mode: "upsert";
  store_id: string;
  received: number;
  inserted: number;
  updated: number;
  deleted: number;
  missing_products: string[];
  items: ProductAttributes[];
};

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText} - ${text}`);
  }

  return (await res.json()) as T;
}

// Fix mojibake simple para demo (UTF-8 interpretado como Latin-1).
// No toca backend: solo presenta correctamente en UI.
export function fixMojibake(input: string | null | undefined): string {
  if (!input) return "";
  try {
    // Convertimos de "latin1 bytes" -> utf8 string
    const bytes = Uint8Array.from(input, (c) => c.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
  } catch {
    return input;
  }
}

export function getStoreId(): string {
  return STORE_ID;
}

export async function listProducts(storeId: string = STORE_ID): Promise<Product[]> {
  return http<Product[]>(`/admin/products?store_id=${encodeURIComponent(storeId)}`);
}

export async function getProductAttributes(productId: string, storeId: string = STORE_ID): Promise<ProductAttributes> {
  return http<ProductAttributes>(
    `/admin/products/${encodeURIComponent(productId)}/attributes?store_id=${encodeURIComponent(storeId)}`
  );
}

export async function updateProductAttributes(
  productId: string,
  payload: { ancho_cm: number | null; composicion: string | null },
  storeId: string = STORE_ID
): Promise<{ ok: true }> {
  return http<{ ok: true }>(
    `/admin/products/${encodeURIComponent(productId)}/attributes?store_id=${encodeURIComponent(storeId)}`,
    { method: "PUT", body: JSON.stringify(payload) }
  );
}

export async function batchGetAttributes(
  productIds: string[],
  storeId: string = STORE_ID
): Promise<BatchGetResponse> {
  const body = { mode: "get", store_id: storeId, product_ids: productIds };
  return http<BatchGetResponse>(`/admin/products/attributes/batch`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function batchUpsertAttributes(
  items: Array<{ product_id: string; ancho_cm: number | null; composicion: string | null }>,
  storeId: string = STORE_ID
): Promise<BatchUpsertResponse> {
  const body = { mode: "upsert", store_id: storeId, items };
  return http<BatchUpsertResponse>(`/admin/products/attributes/batch`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
import { useEffect, useMemo, useState } from "react";
import {
  batchGetAttributes,
  fixMojibake,
  getStoreId,
  listProducts,
} from "../api/client";
import type { Product, ProductAttributes } from "../api/client";

const PAGE_SIZE = 24;

export default function Preview() {
  const storeId = getStoreId();

  const [products, setProducts] = useState<Product[]>([]);
  const [attrs, setAttrs] = useState<Record<string, ProductAttributes>>({});
  const [page, setPage] = useState(1);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const rows = await listProducts(storeId);
        setProducts(rows);
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      }
    })();
  }, [storeId]);

  const totalPages = Math.max(1, Math.ceil(products.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(1, page), totalPages);

  const pageItems = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return products.slice(start, start + PAGE_SIZE);
  }, [products, safePage]);

  useEffect(() => {
    (async () => {
      try {
        if (pageItems.length === 0) return;
        const ids = pageItems.map((p) => p.product_id);
        const res = await batchGetAttributes(ids, storeId);
        const map: Record<string, ProductAttributes> = {};
        for (const it of res.items) map[it.product_id] = it;
        setAttrs((prev) => ({ ...prev, ...map }));
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      }
    })();
  }, [pageItems, storeId]);

  return (
    <div style={{ padding: 16 }}>
      <h2>Preview</h2>
      {err && <pre style={{ color: "crimson" }}>{err}</pre>}

      <div
        style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}
      >
        {pageItems.map((p) => {
          const a = attrs[p.product_id];
          return (
            <div
              key={p.product_id}
              style={{ border: "1px solid #ddd", borderRadius: 10, padding: 12 }}
            >
              <div style={{ fontWeight: 600 }}>{fixMojibake(p.title)}</div>
              <div style={{ opacity: 0.7, fontSize: 12 }}>{p.handle}</div>
              <div style={{ marginTop: 10, fontSize: 13 }}>
                <div>Ancho: {a ? (a.ancho_cm ?? "—") : "…"}</div>
                <div>Comp: {a ? (fixMojibake(a.composicion ?? "") || "—") : "…"}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button disabled={safePage === 1} onClick={() => setPage((p) => p - 1)}>
          Anterior
        </button>
        <button disabled={safePage === totalPages} onClick={() => setPage((p) => p + 1)}>
          Siguiente
        </button>
      </div>
    </div>
  );
}
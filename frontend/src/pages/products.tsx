import { useEffect, useMemo, useState } from "react";
import { batchGetAttributes, fixMojibake, getStoreId, listProducts } from "../api/client";
import type { Product, ProductAttributes } from "../api/client";
import { Link } from "react-router-dom";

const PAGE_SIZE = 20;

export default function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [attrs, setAttrs] = useState<Record<string, ProductAttributes>>({});
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const storeId = getStoreId();
        const rows = await listProducts(storeId);
        setProducts(rows);
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return products;
    return products.filter((p) => {
      const t = fixMojibake(p.title).toLowerCase();
      return t.includes(query) || p.handle.toLowerCase().includes(query) || p.product_id.includes(query);
    });
  }, [products, q]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(1, page), totalPages);

  const pageItems = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, safePage]);

  useEffect(() => {
    (async () => {
      try {
        if (pageItems.length === 0) return;
        const storeId = getStoreId();
        const ids = pageItems.map((p) => p.product_id);
        const res = await batchGetAttributes(ids, storeId);
        const map: Record<string, ProductAttributes> = {};
        for (const it of res.items) map[it.product_id] = it;
        setAttrs((prev) => ({ ...prev, ...map }));
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      }
    })();
  }, [pageItems]);

  return (
    <div style={{ padding: 16 }}>
      <h2>Productos</h2>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar por título / handle / id…"
          style={{ padding: 8, width: 360 }}
        />
        <span style={{ opacity: 0.7 }}>
          {filtered.length} resultados — página {safePage}/{totalPages}
        </span>
      </div>

      {err && <pre style={{ color: "crimson" }}>{err}</pre>}

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Producto</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Handle</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Ancho (cm)</th>
            <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>Composición</th>
            <th style={{ borderBottom: "1px solid #ddd", padding: 8 }}></th>
          </tr>
        </thead>
        <tbody>
          {pageItems.map((p) => {
            const a = attrs[p.product_id];
            return (
              <tr key={p.product_id}>
                <td style={{ padding: 8 }}>{fixMojibake(p.title)}</td>
                <td style={{ padding: 8, opacity: 0.8 }}>{p.handle}</td>
                <td style={{ padding: 8 }}>{a ? (a.ancho_cm ?? "—") : "…"}</td>
                <td style={{ padding: 8 }}>{a ? (fixMojibake(a.composicion) || "—") : "…"}</td>
                <td style={{ padding: 8, textAlign: "right" }}>
                  <Link to={`/productos/${p.product_id}`}>Editar</Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

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
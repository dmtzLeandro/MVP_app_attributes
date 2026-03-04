import { useEffect, useState } from "react";
import { listProducts, getStoreId } from "../api/client";

export default function Dashboard() {
  const [count, setCount] = useState<number | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const storeId = getStoreId();
        const products = await listProducts(storeId);
        setCount(products.length);
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      }
    })();
  }, []);

  return (
    <div style={{ padding: 16 }}>
      <h2>Dashboard</h2>
      <p>Store: {getStoreId()}</p>
      {err && <pre style={{ color: "crimson" }}>{err}</pre>}
      {count === null ? <p>Cargando…</p> : <p>Total productos: {count}</p>}
      <p style={{ opacity: 0.7 }}>
        Demo: listado, editor de atributos, preview tipo Tiendanube (sin N+1).
      </p>
    </div>
  );
}
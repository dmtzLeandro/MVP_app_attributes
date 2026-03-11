import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  fixMojibake,
  getProductAttributes,
  getStoreId,
  updateProductAttributes,
} from "../api/client";

export default function ProductEditor() {
  const { id } = useParams();
  const productId = id ?? "";
  const storeId = getStoreId();

  const [loading, setLoading] = useState(true);
  const [ancho, setAncho] = useState<string>("");
  const [comp, setComp] = useState<string>("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setErr("");
        const a = await getProductAttributes(productId, storeId);
        setAncho(a.ancho_cm === null ? "" : String(a.ancho_cm));
        setComp(a.composicion ?? "");
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [productId, storeId]);

  async function onSave() {
    try {
      setMsg("");
      setErr("");

      const anchoVal = ancho.trim() === "" ? null : Number(ancho);
      if (anchoVal !== null && Number.isNaN(anchoVal)) {
        setErr("Ancho debe ser número o vacío.");
        return;
      }

      await updateProductAttributes(productId, storeId, {
        ancho_cm: anchoVal,
        composicion: comp,
      });

      setMsg("Guardado ✅");
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    }
  }

  async function onClear() {
    try {
      setMsg("");
      setErr("");
      await updateProductAttributes(productId, storeId, {
        ancho_cm: null,
        composicion: "",
      });
      setAncho("");
      setComp("");
      setMsg("Borrado ✅");
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 560 }}>
      <h2>Editar atributos</h2>
      <p style={{ opacity: 0.7 }}>Product ID: {productId}</p>

      {loading ? (
        <p>Cargando…</p>
      ) : (
        <>
          {err && <pre style={{ color: "crimson" }}>{err}</pre>}
          {msg && <p style={{ color: "green" }}>{msg}</p>}

          <div style={{ display: "grid", gap: 10 }}>
            <label>
              Ancho (cm)
              <input
                value={ancho}
                onChange={(e) => setAncho(e.target.value)}
                placeholder="Ej: 150"
                style={{ width: "100%", padding: 8 }}
              />
            </label>

            <label>
              Composición
              <input
                value={comp}
                onChange={(e) => setComp(e.target.value)}
                placeholder="Ej: Algodón 100%"
                style={{ width: "100%", padding: 8 }}
              />
              <div style={{ fontSize: 12, opacity: 0.7, marginTop: 4 }}>
                Vista: {fixMojibake(comp)}
              </div>
            </label>

            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={onSave}>Guardar</button>
              <button onClick={onClear}>Borrar</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
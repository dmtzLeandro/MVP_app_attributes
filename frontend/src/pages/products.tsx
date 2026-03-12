import { useEffect, useMemo, useRef, useState } from "react";
import {
  batchGetAttributes,
  batchUpsertAttributes,
  exportCsvFile,
  fixMojibake,
  getStoreId,
  importCsvFile,
  listProducts,
} from "../api/client";
import type {
  BatchUpsertInItem,
  ImportCsvOut,
  Product,
  ProductAttributes,
} from "../api/client";
import styles from "./products.module.css";

const PAGE_SIZE = 25;

type DraftRow = {
  ancho_cm?: number | null;
  composicion?: string | null;
};

type BulkFieldMode = "set" | "skip" | "clear";

function clampNumberOrNull(raw: string): number | null {
  const v = raw.trim();
  if (v === "") return null;
  const n = Number(v.replace(",", "."));
  if (!Number.isFinite(n)) return null;
  if (n < 0) return 0;
  return n;
}

function normTextOrNull(raw: string): string | null {
  const v = raw.trim();
  return v === "" ? null : v;
}

function getFinalValues(
  pid: string,
  attrs: Record<string, ProductAttributes>,
  draft: Record<string, DraftRow>,
) {
  const cur = attrs[pid] || {
    product_id: pid,
    ancho_cm: null,
    composicion: null,
  };

  const d = draft[pid] || {};

  const finalAncho = d.ancho_cm !== undefined ? d.ancho_cm : cur.ancho_cm;
  const finalComp =
    d.composicion !== undefined ? d.composicion : cur.composicion;

  const changed =
    finalAncho !== (cur.ancho_cm ?? null) ||
    finalComp !== (cur.composicion ?? null);

  const missing = finalAncho === null || !finalComp;

  return {
    current: cur,
    draftRow: d,
    finalAncho,
    finalComp,
    changed,
    missing,
  };
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [attrs, setAttrs] = useState<Record<string, ProductAttributes>>({});
  const [draft, setDraft] = useState<Record<string, DraftRow>>({});

  const [q, setQ] = useState("");
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [page, setPage] = useState(1);

  const [loading, setLoading] = useState(true);
  const [loadingAttrs, setLoadingAttrs] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [importingCsv, setImportingCsv] = useState(false);

  const [err, setErr] = useState<string>("");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkOpen, setBulkOpen] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);

  async function loadProducts() {
    setErr("");
    setLoading(true);
    try {
      const storeId = getStoreId();
      const rows = await listProducts(storeId);
      setProducts(rows);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }

  async function loadAttrsForIds(ids: string[]) {
    if (ids.length === 0) return;

    setLoadingAttrs(true);
    setErr("");

    try {
      const storeId = getStoreId();
      const res = await batchGetAttributes(ids, storeId);

      const map: Record<string, ProductAttributes> = {};
      for (const it of res.items) map[it.product_id] = it;

      setAttrs((prev) => ({ ...prev, ...map }));
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setLoadingAttrs(false);
    }
  }

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3200);
  }

  useEffect(() => {
    return () => {
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
    };
  }, []);

  useEffect(() => {
    loadProducts();
  }, []);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();

    const base = !query
      ? products
      : products.filter((p) => {
          const t = fixMojibake(p.title).toLowerCase();
          return t.includes(query) || p.product_id.includes(query);
        });

    if (!onlyMissing) return base;

    return base.filter((p) => {
      const state = getFinalValues(p.product_id, attrs, draft);
      return state.missing;
    });
  }, [products, q, onlyMissing, attrs, draft]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(1, page), totalPages);

  const pageItems = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, safePage]);

  const pageProductIds = useMemo(
    () => pageItems.map((p) => p.product_id),
    [pageItems],
  );

  const pageProductIdsKey = useMemo(
    () => pageProductIds.join("|"),
    [pageProductIds],
  );

  useEffect(() => {
    const idsToLoad = pageProductIds.filter((pid) => !(pid in attrs));
    if (idsToLoad.length === 0) return;
    loadAttrsForIds(idsToLoad);
  }, [pageProductIdsKey]);

  const pendingCount = useMemo(() => {
    let count = 0;

    for (const pid of Object.keys(draft)) {
      const state = getFinalValues(pid, attrs, draft);
      if (state.changed) count += 1;
    }

    return count;
  }, [draft, attrs]);

  function setDraftValue(pid: string, patch: DraftRow) {
    setDraft((prev) => {
      const cur = prev[pid] || {};
      return { ...prev, [pid]: { ...cur, ...patch } };
    });
  }

  function toggleSelect(pid: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid);
      else next.add(pid);
      return next;
    });
  }

  function selectAllOnPage(checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const p of pageItems) {
        if (checked) next.add(p.product_id);
        else next.delete(p.product_id);
      }
      return next;
    });
  }

  function discardAllDraft() {
    setDraft({});
    showToast("Cambios descartados.");
  }

  async function saveAll() {
    try {
      setSaving(true);
      setErr("");

      const storeId = getStoreId();
      const items: BatchUpsertInItem[] = [];

      for (const pid of Object.keys(draft)) {
        const state = getFinalValues(pid, attrs, draft);
        if (!state.changed) continue;

        items.push({
          product_id: pid,
          ancho_cm: state.finalAncho ?? null,
          composicion: state.finalComp ?? null,
        });
      }

      if (items.length === 0) {
        showToast("No hay cambios para guardar.");
        return;
      }

      const res = await batchUpsertAttributes(items, storeId);

      const map: Record<string, ProductAttributes> = {};
      for (const it of res.items) map[it.product_id] = it;
      setAttrs((prev) => ({ ...prev, ...map }));

      setDraft({});
      showToast(
        `Guardado OK • updated ${res.updated}, inserted ${res.inserted}, deleted ${res.deleted}`,
      );
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleExportCsv() {
    try {
      setExportingCsv(true);
      setErr("");

      const storeId = getStoreId();
      const blob = await exportCsvFile(storeId);

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `products_${storeId}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      showToast("CSV exportado correctamente.");
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setExportingCsv(false);
    }
  }

  function openBulk() {
    if (selected.size === 0) {
      showToast("Seleccioná al menos un producto.");
      return;
    }
    setBulkOpen(true);
  }

  function openCsvImport() {
    setCsvOpen(true);
  }

  function applyBulk(values: {
    ancho_cm: number | null | "skip";
    composicion: string | null | "skip";
  }) {
    if (values.ancho_cm === "skip" && values.composicion === "skip") {
      showToast("Elegí al menos una acción para aplicar.");
      return;
    }

    setDraft((prev) => {
      const next = { ...prev };

      for (const pid of selected) {
        const cur = next[pid] || {};
        const patch: DraftRow = { ...cur };

        if (values.ancho_cm !== "skip") patch.ancho_cm = values.ancho_cm;
        if (values.composicion !== "skip") {
          patch.composicion = values.composicion;
        }

        next[pid] = patch;
      }

      return next;
    });

    setBulkOpen(false);
    showToast(`Aplicado a ${selected.size} producto(s).`);
  }

  async function handleImportCsv(file: File): Promise<ImportCsvOut> {
    const storeId = getStoreId();
    setImportingCsv(true);
    setErr("");

    try {
      const result = await importCsvFile(file, storeId);

      setDraft({});
      setAttrs({});
      setSelected(new Set());

      await loadProducts();

      const refreshedIds = pageItems.map((p) => p.product_id);
      if (refreshedIds.length > 0) {
        await loadAttrsForIds(refreshedIds);
      }

      return result;
    } finally {
      setImportingCsv(false);
    }
  }

  const allSelectedOnPage =
    pageItems.length > 0 && pageItems.every((p) => selected.has(p.product_id));

  return (
    <div className={styles.shell}>
      <div className={styles.container}>
        <div className={styles.topbar}>
          <div className={styles.titleBlock}>
            <h1 className={styles.title}>Productos</h1>
            <p className={styles.subtitle}>
              Click en <b>Ancho</b> o <b>Composición</b> para editar. Guardá al
              final.
            </p>
          </div>

          <div className={styles.actions}>
            <button
              className={styles.ghostButton}
              disabled={exportingCsv || importingCsv}
              onClick={handleExportCsv}
            >
              {exportingCsv ? "Exportando..." : "Exportar CSV"}
            </button>

            <button
              className={styles.ghostButton}
              disabled={importingCsv || exportingCsv}
              onClick={openCsvImport}
            >
              Importar CSV
            </button>

            <button
              className={styles.ghostButton}
              disabled={selected.size === 0}
              onClick={openBulk}
            >
              Aplicar a selección
            </button>

            <button
              className={styles.ghostButton}
              disabled={pendingCount === 0 || saving}
              onClick={discardAllDraft}
            >
              Descartar
            </button>

            <button
              className={styles.primaryButton}
              disabled={pendingCount === 0 || saving}
              onClick={saveAll}
            >
              {saving ? "Guardando..." : `Guardar (${pendingCount})`}
            </button>
          </div>
        </div>

        <div className={styles.toolbar}>
          <div className={styles.searchWrap}>
            <input
              className={styles.search}
              placeholder="Buscar por título o ID"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={onlyMissing}
              onChange={(e) => {
                setOnlyMissing(e.target.checked);
                setPage(1);
              }}
            />
            Solo faltantes
          </label>
        </div>

        {err ? <div className={styles.errorBox}>{err}</div> : null}
        {toast ? <div className={styles.toast}>{toast}</div> : null}

        <div className={styles.metaRow}>
          <div className={styles.meta}>
            {loading
              ? "Cargando productos..."
              : `${filtered.length} resultado(s) • página ${safePage} de ${totalPages}`}
          </div>

          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={allSelectedOnPage}
              onChange={(e) => selectAllOnPage(e.target.checked)}
            />
            Seleccionar página
          </label>
        </div>

        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th></th>
                <th>Imagen</th>
                <th>ID</th>
                <th>Título</th>
                <th>Ancho</th>
                <th>Composición</th>
                <th>Estado</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className={styles.emptyRow}>
                    Cargando...
                  </td>
                </tr>
              ) : pageItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className={styles.emptyRow}>
                    No hay productos.
                  </td>
                </tr>
              ) : (
                pageItems.map((p) => {
                  const state = getFinalValues(p.product_id, attrs, draft);
                  const selectedRow = selected.has(p.product_id);

                  return (
                    <tr
                      key={p.product_id}
                      className={selectedRow ? styles.rowSelected : undefined}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedRow}
                          onChange={() => toggleSelect(p.product_id)}
                        />
                      </td>

                      <td>
                        {p.thumbnail_url ? (
                          <img
                            src={p.thumbnail_url}
                            alt={fixMojibake(p.title)}
                            className={styles.thumb}
                          />
                        ) : (
                          <div className={styles.thumbPlaceholder}>—</div>
                        )}
                      </td>

                      <td className={styles.idCell}>{p.product_id}</td>
                      <td className={styles.titleCell}>{fixMojibake(p.title)}</td>

                      <td>
                        <InlineNumberEditor
                          value={state.finalAncho}
                          onSave={(next) =>
                            setDraftValue(p.product_id, { ancho_cm: next })
                          }
                        />
                      </td>

                      <td>
                        <InlineTextEditor
                          value={state.finalComp}
                          onSave={(next) =>
                            setDraftValue(p.product_id, { composicion: next })
                          }
                        />
                      </td>

                      <td>
                        {state.changed ? (
                          <span className={styles.badgeWarning}>Pendiente</span>
                        ) : state.missing ? (
                          <span className={styles.badgeDanger}>Faltante</span>
                        ) : (
                          <span className={styles.badgeOk}>OK</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className={styles.pagination}>
          <button
            className={styles.ghostButton}
            disabled={safePage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </button>

          <span className={styles.pageIndicator}>
            Página {safePage} / {totalPages}
          </span>

          <button
            className={styles.ghostButton}
            disabled={safePage >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Siguiente
          </button>
        </div>
      </div>

      {bulkOpen ? (
        <BulkModal
          count={selected.size}
          onClose={() => setBulkOpen(false)}
          onApply={applyBulk}
        />
      ) : null}

      {csvOpen ? (
        <CsvImportModal
          loading={importingCsv}
          onClose={() => setCsvOpen(false)}
          onImport={handleImportCsv}
        />
      ) : null}

      {loadingAttrs ? <div className={styles.loadingBar}>Cargando atributos…</div> : null}
    </div>
  );
}

function InlineNumberEditor({
  value,
  onSave,
}: {
  value: number | null;
  onSave: (next: number | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value == null ? "" : String(value));

  useEffect(() => {
    setText(value == null ? "" : String(value));
  }, [value]);

  function commit() {
    onSave(clampNumberOrNull(text));
    setEditing(false);
  }

  if (editing) {
    return (
      <div className={styles.inlineEditor}>
        <input
          autoFocus
          className={styles.inlineInput}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setText(value == null ? "" : String(value));
              setEditing(false);
            }
          }}
        />
      </div>
    );
  }

  return (
    <button className={styles.inlineButton} onClick={() => setEditing(true)}>
      {value == null ? "—" : value}
    </button>
  );
}

function InlineTextEditor({
  value,
  onSave,
}: {
  value: string | null;
  onSave: (next: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value ?? "");

  useEffect(() => {
    setText(value ?? "");
  }, [value]);

  function commit() {
    onSave(normTextOrNull(text));
    setEditing(false);
  }

  if (editing) {
    return (
      <div className={styles.inlineEditor}>
        <input
          autoFocus
          className={styles.inlineInput}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setText(value ?? "");
              setEditing(false);
            }
          }}
        />
      </div>
    );
  }

  return (
    <button className={styles.inlineButton} onClick={() => setEditing(true)}>
      {value || "—"}
    </button>
  );
}

function BulkModal({
  count,
  onClose,
  onApply,
}: {
  count: number;
  onClose: () => void;
  onApply: (values: {
    ancho_cm: number | null | "skip";
    composicion: string | null | "skip";
  }) => void;
}) {
  const [anchoMode, setAnchoMode] = useState<BulkFieldMode>("skip");
  const [compMode, setCompMode] = useState<BulkFieldMode>("skip");

  const [anchoText, setAnchoText] = useState("");
  const [compText, setCompText] = useState("");

  function submit() {
    const ancho =
      anchoMode === "skip"
        ? "skip"
        : anchoMode === "clear"
          ? null
          : clampNumberOrNull(anchoText);

    const comp =
      compMode === "skip"
        ? "skip"
        : compMode === "clear"
          ? null
          : normTextOrNull(compText);

    onApply({
      ancho_cm: ancho,
      composicion: comp,
    });
  }

  return (
    <div className={styles.modalBackdrop}>
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <h3>Aplicar a selección</h3>
          <button className={styles.closeButton} onClick={onClose}>
            ×
          </button>
        </div>

        <p className={styles.modalText}>
          Vas a aplicar cambios sobre <b>{count}</b> producto(s).
        </p>

        <div className={styles.bulkGrid}>
          <div className={styles.bulkField}>
            <label>Ancho</label>
            <select
              value={anchoMode}
              onChange={(e) => setAnchoMode(e.target.value as BulkFieldMode)}
            >
              <option value="skip">No cambiar</option>
              <option value="set">Asignar valor</option>
              <option value="clear">Vaciar</option>
            </select>

            {anchoMode === "set" ? (
              <input
                value={anchoText}
                onChange={(e) => setAnchoText(e.target.value)}
                placeholder="Ej: 120"
              />
            ) : null}
          </div>

          <div className={styles.bulkField}>
            <label>Composición</label>
            <select
              value={compMode}
              onChange={(e) => setCompMode(e.target.value as BulkFieldMode)}
            >
              <option value="skip">No cambiar</option>
              <option value="set">Asignar valor</option>
              <option value="clear">Vaciar</option>
            </select>

            {compMode === "set" ? (
              <input
                value={compText}
                onChange={(e) => setCompText(e.target.value)}
                placeholder="Ej: 100% algodón"
              />
            ) : null}
          </div>
        </div>

        <div className={styles.modalActions}>
          <button className={styles.ghostButton} onClick={onClose}>
            Cancelar
          </button>
          <button className={styles.primaryButton} onClick={submit}>
            Aplicar
          </button>
        </div>
      </div>
    </div>
  );
}

function CsvImportModal({
  loading,
  onClose,
  onImport,
}: {
  loading: boolean;
  onClose: () => void;
  onImport: (file: File) => Promise<ImportCsvOut>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportCsvOut | null>(null);
  const [error, setError] = useState<string>("");

  async function submit() {
    if (!file) {
      setError("Seleccioná un archivo CSV.");
      return;
    }

    try {
      setError("");
      const res = await onImport(file);
      setResult(res);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  }

  return (
    <div className={styles.modalBackdrop}>
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <h3>Importar CSV</h3>
          <button className={styles.closeButton} onClick={onClose}>
            ×
          </button>
        </div>

        <p className={styles.modalText}>
          Importá un CSV con columnas para actualizar atributos de productos.
        </p>

        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />

        {error ? <div className={styles.errorBox}>{error}</div> : null}

        {result ? (
          <div className={styles.importResult}>
            <div>Importados: {result.updated}</div>
            <div>Omitidos: {result.skipped}</div>
            <div>Errores: {result.errors.length}</div>
          </div>
        ) : null}

        <div className={styles.modalActions}>
          <button className={styles.ghostButton} onClick={onClose}>
            Cerrar
          </button>
          <button
            className={styles.primaryButton}
            disabled={loading}
            onClick={submit}
          >
            {loading ? "Importando..." : "Importar"}
          </button>
        </div>
      </div>
    </div>
  );
}
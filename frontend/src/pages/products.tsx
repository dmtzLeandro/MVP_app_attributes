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

  useEffect(() => {
    const ids = pageItems.map((p) => p.product_id);
    loadAttrsForIds(ids);
  }, [pageItems]);

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

        <div className={styles.filtersRow}>
          <div className={styles.searchWrap}>
            <input
              className={styles.searchInput}
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder="Buscar por título / id…"
            />
          </div>

          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={onlyMissing}
              onChange={(e) => {
                setOnlyMissing(e.target.checked);
                setPage(1);
              }}
            />
            <span>Solo faltantes</span>
          </label>

          <div className={styles.resultsInfo}>
            {filtered.length} resultados — página {safePage}/{totalPages}
          </div>

          <div
            className={`${styles.loadingInfo} ${
              loadingAttrs ? styles.loadingInfoVisible : ""
            }`}
            aria-live="polite"
          >
            Cargando atributos…
          </div>
        </div>

        {toast && <div className={styles.toast}>{toast}</div>}

        {err && <pre className={styles.errorBox}>{err}</pre>}

        <div className={styles.tableCard}>
          <table className={styles.table}>
            <colgroup>
              <col className={styles.colCheck} />
              <col className={styles.colProduct} />
              <col className={styles.colAncho} />
              <col className={styles.colComp} />
              <col className={styles.colStatus} />
            </colgroup>

            <thead>
              <tr>
                <th className={styles.th}></th>
                <th className={styles.th}>Producto</th>
                <th className={styles.th}>Ancho (cm)</th>
                <th className={styles.th}>Composición</th>
                <th className={styles.th}>Estado</th>
              </tr>
            </thead>

            <tbody>
              <tr className={styles.selectRow}>
                <td className={styles.tdCheck}>
                  <input
                    type="checkbox"
                    checked={allSelectedOnPage}
                    onChange={(e) => selectAllOnPage(e.target.checked)}
                  />
                </td>
                <td className={styles.selectPageText} colSpan={4}>
                  Seleccionar página
                </td>
              </tr>

              {loading ? (
                <tr>
                  <td colSpan={5} className={styles.emptyState}>
                    Cargando productos…
                  </td>
                </tr>
              ) : pageItems.length === 0 ? (
                <tr>
                  <td colSpan={5} className={styles.emptyState}>
                    No se encontraron productos con ese criterio.
                  </td>
                </tr>
              ) : (
                pageItems.map((p) => {
                  const state = getFinalValues(p.product_id, attrs, draft);

                  return (
                    <tr key={p.product_id} className={styles.row}>
                      <td className={styles.tdCheck}>
                        <input
                          type="checkbox"
                          checked={selected.has(p.product_id)}
                          onChange={() => toggleSelect(p.product_id)}
                        />
                      </td>

                      <td className={styles.td}>
                        <div className={styles.productCell}>
                          <Thumb
                            url={p.thumbnail_url ?? null}
                            title={fixMojibake(p.title)}
                          />

                          <div className={styles.productText}>
                            <div className={styles.productTitle}>
                              {fixMojibake(p.title)}
                            </div>
                            <div className={styles.productId}>
                              {p.product_id}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td className={styles.td}>
                        <div className={styles.fieldSlot}>
                          <InlineNumber
                            value={state.finalAncho}
                            placeholder={attrs[p.product_id] ? "—" : "…"}
                            onCommit={(raw) =>
                              setDraftValue(p.product_id, {
                                ancho_cm: clampNumberOrNull(raw),
                              })
                            }
                          />
                        </div>
                      </td>

                      <td className={styles.td}>
                        <div className={styles.fieldSlot}>
                          <InlineText
                            value={state.finalComp}
                            placeholder={attrs[p.product_id] ? "—" : "…"}
                            onCommit={(raw) =>
                              setDraftValue(p.product_id, {
                                composicion: normTextOrNull(raw),
                              })
                            }
                          />
                        </div>
                      </td>

                      <td className={styles.td}>
                        <StatusPill
                          missing={state.missing}
                          changed={state.changed}
                        />
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
            className={styles.pageButton}
            disabled={safePage === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Anterior
          </button>

          <button
            className={styles.pageButton}
            disabled={safePage === totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Siguiente
          </button>
        </div>

        {bulkOpen && (
          <BulkModal
            count={selected.size}
            onClose={() => setBulkOpen(false)}
            onApply={applyBulk}
          />
        )}

        {csvOpen && (
          <CsvImportModal
            pendingCount={pendingCount}
            importing={importingCsv}
            onClose={() => {
              if (!importingCsv) setCsvOpen(false);
            }}
            onImported={async (file) => {
              const result = await handleImportCsv(file);

              setCsvOpen(false);

              const missingCount = result.missing_products.length;
              if (missingCount > 0) {
                showToast(
                  `Importación OK • procesadas ${result.rows_processed} fila(s). ${missingCount} producto(s) no existían y se ignoraron.`,
                );
              } else {
                showToast(
                  `Importación OK • procesadas ${result.rows_processed} fila(s).`,
                );
              }
            }}
          />
        )}
      </div>
    </div>
  );
}

function Thumb({ url, title }: { url?: string | null; title: string }) {
  const initials = (title || "P").trim().slice(0, 1).toUpperCase();
  const [failed, setFailed] = useState(false);

  if (!url || failed) {
    return (
      <div className={styles.thumbFallback} aria-hidden="true">
        {initials}
      </div>
    );
  }

  return (
    <img
      src={url}
      alt={title}
      onError={() => setFailed(true)}
      className={styles.thumb}
      loading="lazy"
      decoding="async"
    />
  );
}

function StatusPill({
  missing,
  changed,
}: {
  missing: boolean;
  changed: boolean;
}) {
  let toneClass = styles.statusOk;
  let text = "OK";

  if (missing) {
    toneClass = styles.statusMissing;
    text = "Faltante";
  }

  if (changed) {
    toneClass = styles.statusPending;
    text = missing ? "Faltante + pendiente" : "Pendiente";
  }

  return <span className={`${styles.statusPill} ${toneClass}`}>{text}</span>;
}

function InlineText({
  value,
  placeholder,
  onCommit,
}: {
  value: string | null;
  placeholder: string;
  onCommit: (raw: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState(value ?? "");

  useEffect(() => {
    if (!editing) setLocal(value ?? "");
  }, [value, editing]);

  if (!editing) {
    return (
      <div
        className={`${styles.inlineField} ${styles.inlineDisplay} ${
          !value ? styles.inlinePlaceholder : ""
        }`}
        onMouseDown={(e) => {
          e.preventDefault();
          setEditing(true);
        }}
        title="Click para editar"
      >
        {value ?? placeholder}
      </div>
    );
  }

  return (
    <input
      autoFocus
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={() => {
        setEditing(false);
        onCommit(local);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") {
          setEditing(false);
          setLocal(value ?? "");
        }
      }}
      className={`${styles.inlineField} ${styles.inlineInput}`}
    />
  );
}

function InlineNumber({
  value,
  placeholder,
  onCommit,
}: {
  value: number | null;
  placeholder: string;
  onCommit: (raw: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState(value === null ? "" : String(value));

  useEffect(() => {
    if (!editing) setLocal(value === null ? "" : String(value));
  }, [value, editing]);

  if (!editing) {
    return (
      <div
        className={`${styles.inlineField} ${styles.inlineDisplay} ${
          value === null ? styles.inlinePlaceholder : ""
        }`}
        onMouseDown={(e) => {
          e.preventDefault();
          setEditing(true);
        }}
        title="Click para editar"
      >
        {value !== null ? value : placeholder}
      </div>
    );
  }

  return (
    <input
      autoFocus
      inputMode="decimal"
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={() => {
        setEditing(false);
        onCommit(local);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") {
          setEditing(false);
          setLocal(value === null ? "" : String(value));
        }
      }}
      className={`${styles.inlineField} ${styles.inlineInput}`}
    />
  );
}

function BulkModal({
  count,
  onClose,
  onApply,
}: {
  count: number;
  onClose: () => void;
  onApply: (v: {
    ancho_cm: number | null | "skip";
    composicion: string | null | "skip";
  }) => void;
}) {
  const [anchoMode, setAnchoMode] = useState<BulkFieldMode>("set");
  const [compMode, setCompMode] = useState<BulkFieldMode>("set");
  const [ancho, setAncho] = useState("");
  const [comp, setComp] = useState("");

  function handleApply() {
    const anchoAction =
      anchoMode === "skip"
        ? "skip"
        : anchoMode === "clear"
          ? null
          : clampNumberOrNull(ancho);

    const compAction =
      compMode === "skip"
        ? "skip"
        : compMode === "clear"
          ? null
          : normTextOrNull(comp);

    const invalidSetAncho = anchoMode === "set" && ancho.trim() === "";
    const invalidSetComp = compMode === "set" && comp.trim() === "";

    if (invalidSetAncho && invalidSetComp) return;
    if (invalidSetAncho && compMode === "skip") return;
    if (invalidSetComp && anchoMode === "skip") return;

    if (anchoMode === "set" && ancho.trim() === "") {
      onApply({
        ancho_cm: "skip",
        composicion: compAction,
      });
      return;
    }

    if (compMode === "set" && comp.trim() === "") {
      onApply({
        ancho_cm: anchoAction,
        composicion: "skip",
      });
      return;
    }

    onApply({
      ancho_cm: anchoAction,
      composicion: compAction,
    });
  }

  const disableAnchoInput = anchoMode !== "set";
  const disableCompInput = compMode !== "set";

  const noRealAction =
    (anchoMode === "skip" || (anchoMode === "set" && ancho.trim() === "")) &&
    (compMode === "skip" || (compMode === "set" && comp.trim() === ""));

  return (
    <div className={styles.modalBackdrop} onMouseDown={onClose}>
      <div
        className={styles.modal}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className={styles.modalHeader}>
          <div>
            <div className={styles.modalTitle}>Aplicar a selección</div>
            <div className={styles.modalSubtitle}>
              Se aplicará a <b>{count}</b> producto(s).
            </div>
          </div>

          <button className={styles.ghostButton} onClick={onClose}>
            Cerrar
          </button>
        </div>

        <div className={styles.bulkGrid}>
          <div className={styles.bulkCard}>
            <div className={styles.bulkLabel}>Ancho (cm)</div>

            <div className={styles.bulkModes}>
              <label className={styles.bulkModeOption}>
                <input
                  type="radio"
                  name="bulk-ancho-mode"
                  checked={anchoMode === "set"}
                  onChange={() => setAnchoMode("set")}
                />
                <span>Asignar valor</span>
              </label>

              <label className={styles.bulkModeOption}>
                <input
                  type="radio"
                  name="bulk-ancho-mode"
                  checked={anchoMode === "skip"}
                  onChange={() => setAnchoMode("skip")}
                />
                <span>No modificar</span>
              </label>

              <label className={styles.bulkModeOption}>
                <input
                  type="radio"
                  name="bulk-ancho-mode"
                  checked={anchoMode === "clear"}
                  onChange={() => setAnchoMode("clear")}
                />
                <span>Borrar valor</span>
              </label>
            </div>

            <input
              className={styles.bulkInput}
              value={ancho}
              onChange={(e) => setAncho(e.target.value)}
              placeholder="Ej: 55"
              inputMode="decimal"
              disabled={disableAnchoInput}
            />

            <div className={styles.bulkHint}>
              {anchoMode === "set"
                ? "Ingresá el valor a asignar."
                : anchoMode === "skip"
                  ? "Este campo no se modificará."
                  : "Se eliminará el valor actual de ancho."}
            </div>
          </div>

          <div className={styles.bulkCard}>
            <div className={styles.bulkLabel}>Composición</div>

            <div className={styles.bulkModes}>
              <label className={styles.bulkModeOption}>
                <input
                  type="radio"
                  name="bulk-comp-mode"
                  checked={compMode === "set"}
                  onChange={() => setCompMode("set")}
                />
                <span>Asignar valor</span>
              </label>

              <label className={styles.bulkModeOption}>
                <input
                  type="radio"
                  name="bulk-comp-mode"
                  checked={compMode === "skip"}
                  onChange={() => setCompMode("skip")}
                />
                <span>No modificar</span>
              </label>

              <label className={styles.bulkModeOption}>
                <input
                  type="radio"
                  name="bulk-comp-mode"
                  checked={compMode === "clear"}
                  onChange={() => setCompMode("clear")}
                />
                <span>Borrar valor</span>
              </label>
            </div>

            <input
              className={styles.bulkInput}
              value={comp}
              onChange={(e) => setComp(e.target.value)}
              placeholder="Ej: 100% algodón"
              disabled={disableCompInput}
            />

            <div className={styles.bulkHint}>
              {compMode === "set"
                ? "Ingresá el valor a asignar."
                : compMode === "skip"
                  ? "Este campo no se modificará."
                  : "Se eliminará el valor actual de composición."}
            </div>
          </div>
        </div>

        <div className={styles.modalFooter}>
          <button className={styles.ghostButton} onClick={onClose}>
            Cancelar
          </button>

          <button
            className={styles.primaryButton}
            onClick={handleApply}
            disabled={noRealAction}
          >
            Aplicar
          </button>
        </div>
      </div>
    </div>
  );
}

function CsvImportModal({
  pendingCount,
  importing,
  onClose,
  onImported,
}: {
  pendingCount: number;
  importing: boolean;
  onClose: () => void;
  onImported: (file: File) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [localError, setLocalError] = useState<string>("");

  async function handleSubmit() {
    if (!file) {
      setLocalError("Seleccioná un archivo CSV para importar.");
      return;
    }

    setLocalError("");

    try {
      await onImported(file);
    } catch (e: any) {
      setLocalError(e?.message ?? String(e));
    }
  }

  return (
    <div className={styles.modalBackdrop} onMouseDown={onClose}>
      <div
        className={styles.modal}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className={styles.modalHeader}>
          <div>
            <div className={styles.modalTitle}>Importar CSV</div>
            <div className={styles.modalSubtitle}>
              Usá el archivo exportado como plantilla para editar y volver a
              subirlo.
            </div>
          </div>

          <button
            className={styles.ghostButton}
            onClick={onClose}
            disabled={importing}
          >
            Cerrar
          </button>
        </div>

        <div className={styles.csvInfoBox}>
          <div className={styles.csvInfoTitle}>Formato esperado</div>
          <ul className={styles.csvInfoList}>
            <li>Headers requeridos: product_id, ancho_cm, composicion</li>
            <li>Codificación: UTF-8</li>
            <li>ancho_cm acepta número entero o decimal</li>
            <li>Una celda vacía borra ese valor</li>
            <li>Productos inexistentes se ignoran</li>
          </ul>
        </div>

        {pendingCount > 0 && (
          <div className={styles.csvWarningBox}>
            Tenés <b>{pendingCount}</b> cambio(s) manual(es) sin guardar. Si
            importás un CSV, esos cambios locales se descartarán para refrescar
            los datos importados.
          </div>
        )}

        <div className={styles.csvFileBlock}>
          <label className={styles.csvFileLabel}>Archivo CSV</label>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={importing}
          />
          <div className={styles.csvFileName}>
            {file ? file.name : "Ningún archivo seleccionado"}
          </div>
        </div>

        {localError && <div className={styles.csvErrorBox}>{localError}</div>}

        <div className={styles.modalFooter}>
          <button
            className={styles.ghostButton}
            onClick={onClose}
            disabled={importing}
          >
            Cancelar
          </button>

          <button
            className={styles.primaryButton}
            onClick={handleSubmit}
            disabled={!file || importing}
          >
            {importing ? "Importando..." : "Importar archivo"}
          </button>
        </div>
      </div>
    </div>
  );
}
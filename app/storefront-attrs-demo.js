(function () {
  const GLOBAL_KEY = "__TN_APP_ATTRS_STOREFRONT__";
  const existingInstance = window[GLOBAL_KEY];
  if (existingInstance) {
    existingInstance.scan();
    return;
  }

  const script = document.currentScript;
  const runtimeConfig = window.TN_APP_ATTRS_CONFIG || {};
  const scriptStoreId = script?.dataset.storeId || null;
  const scriptSearchParams = script?.src
    ? new URL(script.src, document.baseURI).searchParams
    : null;
  const queryStoreId = scriptSearchParams?.get("store_id") || null;
  const queryStore = scriptSearchParams?.get("store") || null;

  const BACKEND_BASE_URL = (
    runtimeConfig.backendBaseUrl ||
    script?.dataset.backendBaseUrl ||
    "https://mvp-app-attributes.onrender.com"
  ).replace(/\/+$/, "");

  const ITEM_SELECTOR = ".js-item-product[data-product-id]";
  const IMAGE_CONTAINER_SELECTOR = ".product-item-image-container";
  const ATTRS_BLOCK_CLASS = "tn-app-attrs-block";
  const BATCH_SIZE = 100;
  const INITIAL_RETRY_DELAY_MS = 2000;
  const MAX_RETRY_DELAY_MS = 60000;

  const pendingIds = new Set();
  const loadedIds = new Set();
  const attributesById = new Map();
  let retryDelayMs = INITIAL_RETRY_DELAY_MS;
  let retryTimer = null;
  let scanScheduled = false;
  let missingStoreIdWarningShown = false;

  function normalizeStoreId(value) {
    if (value === null || value === undefined) return null;
    const normalized = String(value).trim();
    return normalized || null;
  }

  function resolveStoreId() {
    return (
      normalizeStoreId(window.TN_APP_ATTRS_CONFIG?.storeId) ||
      normalizeStoreId(scriptStoreId) ||
      normalizeStoreId(document.body?.dataset.tnAppStoreId) ||
      normalizeStoreId(queryStoreId) ||
      normalizeStoreId(queryStore) ||
      normalizeStoreId(window.LS?.store?.id)
    );
  }

  function ensureStyles() {
    if (document.getElementById("tn-app-attrs-styles")) return;

    const style = document.createElement("style");
    style.id = "tn-app-attrs-styles";
    style.textContent = `
      .${ATTRS_BLOCK_CLASS} {
        background: #dcecf7;
        color: #163247;
        padding: 8px 10px;
        margin: 0;
        font-size: 12px;
        line-height: 1.35;
      }

      .${ATTRS_BLOCK_CLASS} .tn-app-attrs-line + .tn-app-attrs-line {
        margin-top: 2px;
      }

      .${ATTRS_BLOCK_CLASS} .tn-app-attrs-label {
        font-weight: 700;
      }
    `;
    document.head.appendChild(style);
  }

  function getProductItems(root = document) {
    return Array.from(root.querySelectorAll(ITEM_SELECTOR));
  }

  function extractPendingProductIds(items) {
    const ids = [];
    const seen = new Set();

    for (const item of items) {
      const id = normalizeStoreId(item.getAttribute("data-product-id"));
      if (!id || seen.has(id) || pendingIds.has(id) || loadedIds.has(id)) {
        continue;
      }
      seen.add(id);
      ids.push(id);
    }

    return ids;
  }

  function chunk(values, size) {
    const chunks = [];
    for (let index = 0; index < values.length; index += size) {
      chunks.push(values.slice(index, index + size));
    }
    return chunks;
  }

  async function fetchAttributes(storeId, productIds) {
    const response = await fetch(
      `${BACKEND_BASE_URL}/admin/storefront/attributes/batch`,
      {
        method: "POST",
        mode: "cors",
        credentials: "omit",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          store_id: storeId,
          product_ids: productIds,
        }),
      }
    );

    if (!response.ok) {
      throw new Error(`Storefront attrs fetch failed: ${response.status}`);
    }

    return response.json();
  }

  function buildAttrsBlock(itemData) {
    const lines = [];

    if (itemData.ancho_cm !== null && itemData.ancho_cm !== undefined) {
      lines.push(
        `<div class="tn-app-attrs-line"><span class="tn-app-attrs-label">Ancho:</span> ${itemData.ancho_cm} cm</div>`
      );
    }

    if (itemData.composicion) {
      lines.push(
        `<div class="tn-app-attrs-line"><span class="tn-app-attrs-label">Composición:</span> ${escapeHtml(itemData.composicion)}</div>`
      );
    }

    if (!lines.length) return null;

    const wrapper = document.createElement("div");
    wrapper.className = ATTRS_BLOCK_CLASS;
    wrapper.innerHTML = lines.join("");
    return wrapper;
  }

  function renderAttributes(items) {
    for (const item of items) {
      const productId = normalizeStoreId(item.getAttribute("data-product-id"));
      if (!productId || item.querySelector(`.${ATTRS_BLOCK_CLASS}`)) continue;

      const itemData = attributesById.get(productId);
      if (!itemData) continue;

      const block = buildAttrsBlock(itemData);
      if (!block) continue;

      const imageContainer = item.querySelector(IMAGE_CONTAINER_SELECTOR);
      if (!imageContainer || !imageContainer.parentNode) continue;

      imageContainer.insertAdjacentElement("afterend", block);
    }
  }

  function scheduleRetry() {
    if (retryTimer !== null) return;

    retryTimer = window.setTimeout(() => {
      retryTimer = null;
      scheduleScan();
    }, retryDelayMs);
    retryDelayMs = Math.min(retryDelayMs * 2, MAX_RETRY_DELAY_MS);
  }

  async function processBatch(storeId, productIds) {
    productIds.forEach((id) => pendingIds.add(id));

    try {
      const result = await fetchAttributes(storeId, productIds);
      for (const item of result.items || []) {
        const productId = normalizeStoreId(item.product_id);
        if (productId) attributesById.set(productId, item);
      }
      productIds.forEach((id) => loadedIds.add(id));
      retryDelayMs = INITIAL_RETRY_DELAY_MS;
      renderAttributes(getProductItems());
    } catch (error) {
      console.error("[tn-app-attrs] Attribute request failed", error);
      scheduleRetry();
    } finally {
      productIds.forEach((id) => pendingIds.delete(id));
    }
  }

  function scan() {
    const items = getProductItems();
    if (!items.length) return;

    renderAttributes(items);

    const storeId = resolveStoreId();
    if (!storeId) {
      if (!missingStoreIdWarningShown) {
        console.warn("[tn-app-attrs] Missing storeId configuration");
        missingStoreIdWarningShown = true;
      }
      return;
    }
    missingStoreIdWarningShown = false;

    const productIds = extractPendingProductIds(items);
    for (const productIdBatch of chunk(productIds, BATCH_SIZE)) {
      void processBatch(storeId, productIdBatch);
    }
  }

  function scheduleScan() {
    if (scanScheduled) return;
    scanScheduled = true;
    window.requestAnimationFrame(() => {
      scanScheduled = false;
      scan();
    });
  }

  function observeDocument() {
    const observer = new MutationObserver(scheduleScan);
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function init() {
    ensureStyles();
    observeDocument();
    scheduleScan();
  }

  window[GLOBAL_KEY] = { scan: scheduleScan };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();

(function () {
  const BACKEND_BASE_URL = "https://mvp-app-attributes.onrender.com";
  const STORE_ID = "1984753";

  const GRID_SELECTOR = ".js-product-table";
  const ITEM_SELECTOR = ".js-item-product[data-product-id]";
  const IMAGE_CONTAINER_SELECTOR = ".product-item-image-container";
  const ATTRS_BLOCK_CLASS = "tn-app-attrs-block";

  const requestedIds = new Set();

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

  function getUnprocessedItems(root = document) {
    return getProductItems(root).filter((item) => {
      return !item.querySelector(`.${ATTRS_BLOCK_CLASS}`);
    });
  }

  function extractProductIds(items) {
    const ids = [];

    for (const item of items) {
      const id = item.getAttribute("data-product-id");
      if (!id) continue;
      if (requestedIds.has(id)) continue;
      ids.push(id);
    }

    return ids;
  }

  async function fetchAttributes(productIds) {
    if (!productIds.length) return { ok: true, items: [] };

    const response = await fetch(
      `${BACKEND_BASE_URL}/admin/storefront/attributes/batch`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          store_id: STORE_ID,
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

  function renderAttributes(items, dataById) {
    for (const item of items) {
      const productId = item.getAttribute("data-product-id");
      if (!productId) continue;

      const existing = item.querySelector(`.${ATTRS_BLOCK_CLASS}`);
      if (existing) continue;

      const itemData = dataById.get(productId);
      if (!itemData) continue;

      const block = buildAttrsBlock(itemData);
      if (!block) continue;

      const imageContainer = item.querySelector(IMAGE_CONTAINER_SELECTOR);
      if (!imageContainer || !imageContainer.parentNode) continue;

      imageContainer.insertAdjacentElement("afterend", block);
    }
  }

  async function processItems(root = document) {
    const items = getUnprocessedItems(root);
    if (!items.length) return;

    const ids = extractProductIds(items);
    if (!ids.length) return;

    ids.forEach((id) => requestedIds.add(id));

    try {
      const result = await fetchAttributes(ids);
      const dataById = new Map(
        (result.items || []).map((it) => [String(it.product_id), it])
      );
      renderAttributes(items, dataById);
    } catch (error) {
      console.error("[tn-app-attrs]", error);
    }
  }

  function observeGrid() {
    const grid = document.querySelector(GRID_SELECTOR);
    if (!grid) return;

    const observer = new MutationObserver(() => {
      processItems(grid);
    });

    observer.observe(grid, {
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
    if (!document.querySelector(`${GRID_SELECTOR} ${ITEM_SELECTOR}`)) return;
    ensureStyles();
    processItems(document);
    observeGrid();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
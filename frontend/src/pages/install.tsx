import { useState } from "react";
import { Link } from "react-router-dom";

import { apiGetInstallUrl } from "../api/client";
import styles from "./login.module.css";

export default function InstallPage() {
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleInstall() {
    setInstalling(true);
    setError(null);

    try {
      const result = await apiGetInstallUrl();

      if (!result.authorize_url) {
        throw new Error(
          "No se recibió una URL válida para iniciar la instalación.",
        );
      }

      window.location.assign(result.authorize_url);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo iniciar la instalación.",
      );
      setInstalling(false);
    }
  }

  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.eyebrow}>TN Attributes App</div>
          <h1 className={styles.title}>Instalar aplicación</h1>
          <p className={styles.subtitle}>
            Conectá tu tienda de Tiendanube para importar el catálogo y comenzar
            a administrar sus atributos.
          </p>
        </div>

        {error && (
          <div className={styles.errorBox}>
            <div className={styles.errorText}>{error}</div>
          </div>
        )}

        <button
          type="button"
          className={styles.submitButton}
          disabled={installing}
          onClick={handleInstall}
        >
          {installing ? "Iniciando instalación..." : "Instalar en Tiendanube"}
        </button>

        <div className={styles.footerLinks}>
          <Link to="/login" className={styles.linkButton}>
            Ya tengo una cuenta
          </Link>
        </div>
      </div>
    </div>
  );
}

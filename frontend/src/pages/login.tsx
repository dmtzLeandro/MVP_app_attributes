import { useEffect, useState } from "react";
import { apiLogin, isAuthed } from "../api/client";
import styles from "./login.module.css";

export default function LoginPage() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthed()) {
      window.location.href = "/productos";
    }
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiLogin({ username, password }, remember);
      window.location.href = "/productos";
    } catch (err: any) {
      setError(err?.message || "No se pudo iniciar sesión.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.eyebrow}>Panel de administración</div>
          <h1 className={styles.title}>Ingreso</h1>
          <p className={styles.subtitle}>
            Iniciá sesión para administrar atributos del catálogo.
          </p>
        </div>

        <form onSubmit={onSubmit} className={styles.form}>
          <label className={styles.field}>
            <span className={styles.label}>Usuario</span>
            <input
              className={styles.input}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              disabled={loading}
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>Contraseña</span>
            <input
              className={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="current-password"
              disabled={loading}
            />
          </label>

          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              disabled={loading}
            />
            <span>Recordarme</span>
          </label>

          {error && (
            <div className={styles.errorBox}>
              <div className={styles.errorText}>{error}</div>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password.trim()}
            className={styles.submitButton}
          >
            {loading ? "Ingresando..." : "Ingresar"}
          </button>
        </form>
      </div>
    </div>
  );
}
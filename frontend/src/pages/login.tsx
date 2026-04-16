import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { apiLogin, isAuthed } from "../api/client";
import styles from "./login.module.css";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const registerHref = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const registrationToken = params.get("registration_token");
    return registrationToken
      ? `/register?registration_token=${encodeURIComponent(registrationToken)}`
      : "/register";
  }, [location.search]);

  useEffect(() => {
    if (isAuthed()) {
      navigate("/productos", { replace: true });
    }
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiLogin({ email, password }, remember);
      navigate("/productos", { replace: true });
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
            <span className={styles.label}>Email</span>
            <input
              className={styles.input}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              disabled={loading}
              type="email"
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
            disabled={loading || !email.trim() || !password.trim()}
            className={styles.submitButton}
          >
            {loading ? "Ingresando..." : "Ingresar"}
          </button>
        </form>

        <div className={styles.footerLinks}>
          <Link to={registerHref} className={styles.linkButton}>
            ¿No tenés cuenta? Registrarme
          </Link>
        </div>
      </div>
    </div>
  );
}
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiForgotPassword, isAuthed } from "../api/client";
import styles from "./login.module.css";

export default function ForgotPasswordPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [resetUrl, setResetUrl] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthed()) {
      navigate("/productos", { replace: true });
    }
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setResetUrl(null);
    setLoading(true);

    try {
      const out = await apiForgotPassword({ email });
      setSuccessMessage(out.message);
      setResetUrl(out.reset_url || null);
    } catch (err: any) {
      setError(err?.message || "No se pudo iniciar el recupero.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.eyebrow}>Panel de administración</div>
          <h1 className={styles.title}>Recuperar acceso</h1>
          <p className={styles.subtitle}>
            Ingresá tu email y te enviaremos un enlace para restablecer tu contraseña.
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

          {error && (
            <div className={styles.errorBox}>
              <div className={styles.errorText}>{error}</div>
            </div>
          )}

          {successMessage && (
            <div className={styles.successBox}>
              <div className={styles.successText}>{successMessage}</div>
            </div>
          )}

          {resetUrl && (
            <div className={styles.successBox}>
              <div className={styles.successText}>
                <a
                  href={resetUrl}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.inlineLink}
                >
                  Abrir enlace de recuperación
                </a>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !email.trim()}
            className={styles.submitButton}
          >
            {loading ? "Enviando..." : "Enviar enlace"}
          </button>
        </form>

        <div className={styles.footerLinks}>
          <Link to="/login" className={styles.linkButton}>
            Volver a iniciar sesión
          </Link>
        </div>
      </div>
    </div>
  );
}
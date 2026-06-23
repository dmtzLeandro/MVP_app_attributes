import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { apiResetPassword, isAuthed } from "../api/client";
import styles from "./login.module.css";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const token = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("token") || "";
  }, [location.search]);

  useEffect(() => {
    if (isAuthed()) {
      navigate("/productos", { replace: true });
    }
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!token) {
      setError("No se encontró un token válido para restablecer la contraseña.");
      return;
    }

    if (password !== passwordConfirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setLoading(true);

    try {
      await apiResetPassword({
        token,
        password,
        password_confirm: passwordConfirm,
      });
      setSuccessMessage("La contraseña fue actualizada correctamente. Ya podés iniciar sesión.");
    } catch (err: any) {
      setError(err?.message || "No se pudo restablecer la contraseña.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.eyebrow}>Panel de administración</div>
          <h1 className={styles.title}>Nueva contraseña</h1>
          <p className={styles.subtitle}>
            Definí una nueva contraseña para recuperar el acceso al panel.
          </p>
        </div>

        <form onSubmit={onSubmit} className={styles.form}>
          <label className={styles.field}>
            <span className={styles.label}>Nueva contraseña</span>
            <input
              className={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="new-password"
              disabled={loading}
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>Repetir contraseña</span>
            <input
              className={styles.input}
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              type="password"
              autoComplete="new-password"
              disabled={loading}
            />
          </label>

          {!token && (
            <div className={styles.errorBox}>
              <div className={styles.errorText}>
                Falta el token de recuperación en la URL.
              </div>
            </div>
          )}

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

          <button
            type="submit"
            disabled={
              loading ||
              !token ||
              !password.trim() ||
              !passwordConfirm.trim()
            }
            className={styles.submitButton}
          >
            {loading ? "Guardando..." : "Guardar nueva contraseña"}
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
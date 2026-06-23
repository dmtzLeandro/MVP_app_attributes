import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { apiRegister, isAuthed } from "../api/client";
import styles from "./login.module.css";

export default function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [verificationUrl, setVerificationUrl] = useState<string | null>(null);

  const registrationToken = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("registration_token") || "";
  }, [location.search]);

  const loginHref = useMemo(() => {
    return registrationToken
      ? `/login?registration_token=${encodeURIComponent(registrationToken)}`
      : "/login";
  }, [registrationToken]);

  useEffect(() => {
    if (isAuthed()) {
      navigate("/productos", { replace: true });
    }
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setVerificationUrl(null);

    if (!registrationToken) {
      setError(
        "No encontramos un enlace válido para crear la cuenta. Instalá la aplicación nuevamente o solicitá un nuevo acceso.",
      );
      return;
    }

    if (password !== passwordConfirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setLoading(true);

    try {
      const out = await apiRegister({
        registration_token: registrationToken,
        email,
        password,
        password_confirm: passwordConfirm,
      });

      if (out.email_sent) {
        setSuccessMessage("Te enviamos un mail para verificar tu cuenta.");
      } else {
        setSuccessMessage(out.message);
      }

      setVerificationUrl(out.verification_url ?? null);
    } catch (err: any) {
      setError(err?.message || "No se pudo crear la cuenta.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.eyebrow}>Panel de administración</div>
          <h1 className={styles.title}>Crear cuenta</h1>
          <p className={styles.subtitle}>
            Registrate para acceder al panel de la app.
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

          {!registrationToken && (
            <div className={styles.errorBox}>
              <div className={styles.errorText}>
                No encontramos un enlace válido para crear la cuenta. Instalá la aplicación nuevamente o solicitá un nuevo acceso.
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

          {verificationUrl && (
            <div className={styles.successBox}>
              <div className={styles.successText}>
                <a
                  href={verificationUrl}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.inlineLink}
                >
                  Verificar cuenta
                </a>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={
              loading ||
              !registrationToken ||
              !email.trim() ||
              !password.trim() ||
              !passwordConfirm.trim()
            }
            className={styles.submitButton}
          >
            {loading ? "Creando cuenta..." : "Registrarme"}
          </button>
        </form>

        <div className={styles.footerLinks}>
          <Link to={loginHref} className={styles.linkButton}>
            Volver a iniciar sesión
          </Link>
        </div>
      </div>
    </div>
  );
}

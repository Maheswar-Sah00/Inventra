import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, type Location } from "react-router-dom";

import { AuthLayout } from "../components/layout/AuthLayout";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/FormField";
import { DEFAULT_AUTHENTICATED_PATH, useAuth } from "../modules/auth";
import { collectErrors, validateEmail, type FieldErrors } from "../modules/auth/validation";
import { ApiError } from "../services/apiClient";

type LoginLocationState = { from?: Location; message?: string } | null;

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LoginLocationState;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = collectErrors({ email: validateEmail(email), password: password ? null : "Password is required" });
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;

    setSubmitting(true);
    try {
      await login(email, password);
      const from = state?.from;
      const target = from && from.pathname !== "/login" ? `${from.pathname}${from.search}` : DEFAULT_AUTHENTICATED_PATH;
      navigate(target, { replace: true });
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Unable to sign in. Please try again.");
      if (error instanceof ApiError) setErrors(error.fieldErrors);
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Welcome back. Sign in to manage your inventory."
      footer={
        <>
          New to StockSense? <Link to="/signup">Create an account</Link>
        </>
      }
    >
      {state?.message && !formError && <Alert variant="success">{state.message}</Alert>}
      {formError && <Alert variant="error">{formError}</Alert>}
      <form onSubmit={handleSubmit} noValidate>
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
          autoFocus
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.password}
        />
        <div className="form-row-end">
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <Button type="submit" loading={submitting} loadingText="Signing in…">
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}

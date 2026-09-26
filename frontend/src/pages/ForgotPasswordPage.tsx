import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AuthLayout } from "../components/layout/AuthLayout";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/FormField";
import { authApi } from "../modules/auth/authApi";
import { validateEmail } from "../modules/auth/validation";
import { ApiError } from "../services/apiClient";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const emailError = validateEmail(email);
    setError(emailError);
    setFormError(null);
    if (emailError) return;

    setSubmitting(true);
    try {
      const { message } = await authApi.forgotPassword(email.trim());
      navigate(`/reset-password?email=${encodeURIComponent(email.trim())}`, { state: { message } });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to send the code. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      subtitle="Enter your account email and we'll send you a one-time verification code."
      footer={<Link to="/login">Back to sign in</Link>}
    >
      {formError && <Alert variant="error">{formError}</Alert>}
      <form onSubmit={handleSubmit} noValidate>
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={error}
          autoFocus
        />
        <Button type="submit" loading={submitting} loadingText="Sending code…">
          Send verification code
        </Button>
      </form>
    </AuthLayout>
  );
}

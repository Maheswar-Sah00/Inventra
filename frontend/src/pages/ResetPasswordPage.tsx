import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { AuthLayout } from "../components/layout/AuthLayout";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/FormField";
import { LOGIN_PATH } from "../modules/auth";
import { authApi } from "../modules/auth/authApi";
import {
  collectErrors,
  validateEmail,
  validateOtp,
  validatePassword,
  validatePasswordConfirmation,
  type FieldErrors,
} from "../modules/auth/validation";
import { ApiError } from "../services/apiClient";

const RESEND_COOLDOWN_SECONDS = 60;

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const [step, setStep] = useState<"verify" | "reset">("verify");
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [otp, setOtp] = useState("");
  // Held in memory only: the reset token is short-lived and single-use.
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>((location.state as { message?: string } | null)?.message ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(searchParams.get("email") ? RESEND_COOLDOWN_SECONDS : 0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function handleVerify(event: FormEvent) {
    event.preventDefault();
    const found = collectErrors({ email: validateEmail(email), otp: validateOtp(otp) });
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;

    setSubmitting(true);
    try {
      const result = await authApi.verifyOtp(email.trim(), otp.trim());
      setResetToken(result.reset_token);
      setStep("reset");
      setInfo("Code verified. Choose a new password.");
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Unable to verify the code. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    const emailError = validateEmail(email);
    setErrors(emailError ? { email: emailError } : {});
    if (emailError) return;
    setFormError(null);
    try {
      const { message } = await authApi.forgotPassword(email.trim());
      setInfo(message);
      setOtp("");
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Unable to resend the code.");
    }
  }

  async function handleReset(event: FormEvent) {
    event.preventDefault();
    const found = collectErrors({
      password: validatePassword(password),
      confirm_password: validatePasswordConfirmation(password, confirmPassword),
    });
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length || !resetToken) return;

    setSubmitting(true);
    try {
      const { message } = await authApi.resetPassword(resetToken, password, confirmPassword);
      navigate(LOGIN_PATH, { replace: true, state: { message } });
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        // Reset session expired or already used: go back to requesting a new code.
        setStep("verify");
        setResetToken(null);
        setOtp("");
        setInfo(null);
      }
      setFormError(error instanceof ApiError ? error.message : "Unable to reset your password. Please try again.");
      if (error instanceof ApiError) setErrors(error.fieldErrors);
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title={step === "verify" ? "Enter verification code" : "Set a new password"}
      subtitle={
        step === "verify"
          ? "Check your email for the 6-digit code. It expires in a few minutes and can be used once."
          : undefined
      }
      footer={<Link to="/login">Back to sign in</Link>}
    >
      {info && !formError && <Alert variant="info">{info}</Alert>}
      {formError && <Alert variant="error">{formError}</Alert>}

      {step === "verify" ? (
        <form onSubmit={handleVerify} noValidate>
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
          />
          <TextField
            label="Verification code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
            error={errors.otp}
            autoFocus
          />
          <Button type="submit" loading={submitting} loadingText="Verifying…">
            Verify code
          </Button>
          <Button type="button" variant="link" onClick={handleResend} disabled={cooldown > 0}>
            {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
          </Button>
        </form>
      ) : (
        <form onSubmit={handleReset} noValidate>
          <TextField
            label="New password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            hint="At least 8 characters, including a letter and a number."
            autoFocus
          />
          <TextField
            label="Confirm new password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            error={errors.confirm_password}
          />
          <Button type="submit" loading={submitting} loadingText="Saving…">
            Reset password
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}

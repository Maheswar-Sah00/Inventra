import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AuthLayout } from "../components/layout/AuthLayout";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { SelectField, TextField } from "../components/ui/FormField";
import { DEFAULT_AUTHENTICATED_PATH, ROLE_LABELS, useAuth, type UserRole } from "../modules/auth";
import {
  collectErrors,
  validateEmail,
  validateName,
  validatePassword,
  validatePasswordConfirmation,
  type FieldErrors,
} from "../modules/auth/validation";
import { ApiError } from "../services/apiClient";

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    role: "WAREHOUSE_STAFF" as UserRole,
    password: "",
    confirm_password: "",
  });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (field: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = collectErrors({
      name: validateName(form.name),
      email: validateEmail(form.email),
      password: validatePassword(form.password),
      confirm_password: validatePasswordConfirmation(form.password, form.confirm_password),
    });
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;

    setSubmitting(true);
    try {
      await signup({ ...form, name: form.name.trim(), email: form.email.trim() });
      navigate(DEFAULT_AUTHENTICATED_PATH, { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message);
        setErrors(error.fieldErrors);
      } else {
        setFormError("Unable to create your account. Please try again.");
      }
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Get started with StockSense."
      footer={
        <>
          Already have an account? <Link to="/login">Sign in</Link>
        </>
      }
    >
      {formError && <Alert variant="error">{formError}</Alert>}
      <form onSubmit={handleSubmit} noValidate>
        <TextField label="Full name" autoComplete="name" value={form.name} onChange={update("name")} error={errors.name} autoFocus />
        <TextField label="Email" type="email" autoComplete="email" value={form.email} onChange={update("email")} error={errors.email} />
        <SelectField label="Role" value={form.role} onChange={update("role")} error={errors.role}>
          {(Object.keys(ROLE_LABELS) as UserRole[]).map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          value={form.password}
          onChange={update("password")}
          error={errors.password}
          hint="At least 8 characters, including a letter and a number."
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          value={form.confirm_password}
          onChange={update("confirm_password")}
          error={errors.confirm_password}
        />
        <Button type="submit" loading={submitting} loadingText="Creating account…">
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}

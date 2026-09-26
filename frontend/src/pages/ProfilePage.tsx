import { useState, type FormEvent } from "react";

import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/FormField";
import { ROLE_LABELS, useAuth } from "../modules/auth";
import { authApi } from "../modules/auth/authApi";
import { validateName } from "../modules/auth/validation";
import { ApiError } from "../services/apiClient";

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

export function ProfilePage() {
  const { user, setUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user?.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (!user) return null;

  function startEditing() {
    setName(user!.name);
    setError(null);
    setFormError(null);
    setSuccess(null);
    setEditing(true);
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    const nameError = validateName(name);
    setError(nameError);
    setFormError(null);
    if (nameError) return;

    setSaving(true);
    try {
      const updated = await authApi.updateProfile({ name: name.trim() });
      setUser(updated);
      setEditing(false);
      setSuccess("Profile updated.");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to save your profile.");
      if (err instanceof ApiError && err.fieldErrors.name) setError(err.fieldErrors.name);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page">
      <h1>My Profile</h1>
      {success && <Alert variant="success">{success}</Alert>}
      {formError && <Alert variant="error">{formError}</Alert>}

      <div className="card profile-card">
        {editing ? (
          <form onSubmit={handleSave} noValidate>
            <TextField label="Full name" value={name} onChange={(e) => setName(e.target.value)} error={error} autoFocus />
            <div className="button-row">
              <Button type="submit" loading={saving} loadingText="Saving…">
                Save changes
              </Button>
              <Button type="button" variant="secondary" onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <dl className="details">
            <dt>Name</dt>
            <dd>{user.name}</dd>
            <dt>Email</dt>
            <dd>{user.email}</dd>
            <dt>Role</dt>
            <dd>{ROLE_LABELS[user.role]}</dd>
            <dt>Account status</dt>
            <dd>
              <span className={`badge ${user.is_active ? "badge-success" : "badge-muted"}`}>
                {user.is_active ? "Active" : "Inactive"}
              </span>
            </dd>
            <dt>Member since</dt>
            <dd>{formatDate(user.created_at)}</dd>
          </dl>
        )}
        {!editing && (
          <div className="button-row">
            <Button type="button" variant="secondary" onClick={startEditing}>
              Edit name
            </Button>
          </div>
        )}
      </div>
      <p className="muted small">Your email and role are managed by your organisation and can't be changed here.</p>
    </section>
  );
}

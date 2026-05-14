import { useState, type FormEvent } from 'react';
import Button from './ui/Button';
import Input from './ui/Input';
import { login } from '../lib/auth';
import './LoginForm.css';

export default function LoginForm() {
  const [token, setToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const result = await login(token);
    setSubmitting(false);
    if (result.ok) {
      window.location.assign('/');
    } else {
      setError(result.error ?? 'Login failed.');
    }
  }

  return (
    <form className="login-form" onSubmit={onSubmit} noValidate>
      <Input
        label="Access token"
        name="token"
        type="password"
        autoComplete="current-password"
        value={token}
        onChange={(e) => setToken(e.currentTarget.value)}
        error={error ?? undefined}
        required
      />
      <Button type="submit" variant="primary" size="md" loading={submitting} disabled={!token}>
        Sign in
      </Button>
    </form>
  );
}

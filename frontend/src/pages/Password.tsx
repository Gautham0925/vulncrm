import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { post } from "../lib/api";
import { ErrorBox, Field } from "../components/ui";
import { AuthShell } from "./Login";

export function Forgot() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e: FormEvent) => { e.preventDefault(); setError(""); try { await post("/api/auth/forgot-password", { email }); setSent(true); } catch (err: any) { setError(err.message); } };
  return (
    <AuthShell title="Reset your password" subtitle="We will email you a link to choose a new password.">
      {sent ? <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">If an account exists for that address, a reset link has been sent. <Link to="/login" className="font-medium underline">Back to sign in</Link></div> : (
        <form onSubmit={submit} className="space-y-4">
          {error && <ErrorBox error={{ message: error }} />}
          <Field label="Email"><input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email" /></Field>
          <button className="btn-primary w-full">Send reset link</button>
          <Link to="/login" className="block text-center text-sm text-brand-600 hover:underline">Back to sign in</Link>
        </form>
      )}
    </AuthShell>
  );
}

export function Reset() {
  const [sp] = useSearchParams();
  const [token, setToken] = useState(sp.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e: FormEvent) => { e.preventDefault(); setError(""); try { await post("/api/auth/reset-password", { token, password }); setDone(true); } catch (err: any) { setError(err.message); } };
  return (
    <AuthShell title="Choose a new password">
      {done ? <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">Your password has been updated. <Link to="/login" className="font-medium underline">Sign in</Link></div> : (
        <form onSubmit={submit} className="space-y-4">
          {error && <ErrorBox error={{ message: error }} />}
          <Field label="Reset token"><input className="input" required value={token} onChange={(e) => setToken(e.target.value)} aria-label="Reset token" /></Field>
          <Field label="New password" hint="At least 12 characters"><input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} aria-label="New password" /></Field>
          <button className="btn-primary w-full">Update password</button>
        </form>
      )}
    </AuthShell>
  );
}

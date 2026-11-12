import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { get, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorBox, Field } from "../components/ui";

export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  const { meta } = useAuth();
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-ink-900 p-12 text-white lg:flex">
        <div className="flex items-center gap-2.5"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600"><ShieldCheck className="h-5 w-5" /></span><span className="text-xl font-bold tracking-tight">VULNCRM</span></div>
        <div><h2 className="max-w-md text-3xl font-semibold leading-snug text-white">{meta?.tagline ?? "Manage Relationships. Secure Every Interaction."}</h2><p className="mt-4 max-w-md text-ink-300">Customers, pipeline, support and integrations in one workspace, with the access controls an enterprise expects.</p></div>
        <p className="text-xs text-ink-400">© VULNCRM</p>
      </div>
      <div className="flex items-center justify-center bg-white p-8">
        <div className="w-full max-w-sm">
          {meta?.training_environment && meta.mode === "vulnerable" && <p role="note" className="mb-6 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900 ring-1 ring-amber-200">{meta.banner}</p>}
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  );
}

export default function Login() {
  const { meta, refresh, me } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [challenge, setChallenge] = useState<{ id: string } | null>(null);
  const [code, setCode] = useState("");
  const [org, setOrg] = useState("northwind");

  useEffect(() => { get("/api/auth/session-init").catch(() => {}); }, []);
  useEffect(() => { if (me) nav("/", { replace: true }); }, [me, nav]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const r = await post("/api/auth/login", { email, password });
      if (r.mfa_required) setChallenge({ id: r.challenge_id });
      else { await refresh(); nav("/"); }
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };
  const verify = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { await post("/api/auth/verify-otp", { challenge_id: challenge!.id, code }); await refresh(); nav("/"); }
    catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };

  if (challenge) return (
    <AuthShell title="Verify your identity" subtitle="Enter the 6-digit code sent to your email.">
      <form onSubmit={verify} className="space-y-4">
        {error && <ErrorBox error={{ message: error }} />}
        <Field label="Verification code"><input className="input tracking-widest" inputMode="numeric" autoFocus value={code} onChange={(e) => setCode(e.target.value)} placeholder="123456" aria-label="Verification code" /></Field>
        <button className="btn-primary w-full" disabled={busy}>Verify and continue</button>
        <p className="text-xs text-ink-500">Codes are delivered to the <Link className="text-brand-600 hover:underline" to="/dev/mailbox" target="_blank">development mailbox</Link> in this environment.</p>
      </form>
    </AuthShell>
  );

  return (
    <AuthShell title="Sign in to your workspace" subtitle="Use your work email to continue.">
      <form onSubmit={submit} className="space-y-4">
        {sp.get("error") && <ErrorBox error={{ message: sp.get("error") }} />}
        {error && <ErrorBox error={{ message: error }} />}
        <Field label="Email"><input className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" aria-label="Email" /></Field>
        <Field label="Password"><input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} aria-label="Password" /></Field>
        <div className="flex justify-end"><Link to="/forgot-password" className="text-xs font-medium text-brand-600 hover:underline">Forgot password?</Link></div>
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      {(meta?.sso.saml || meta?.sso.oidc) && (
        <div className="mt-6 border-t border-ink-100 pt-5">
          <p className="label">Single sign-on</p>
          <div className="flex gap-2">
            <input className="input" value={org} onChange={(e) => setOrg(e.target.value)} aria-label="Organization identifier" placeholder="organization" />
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {meta.sso.saml && <a className="btn-secondary" href={`/saml/${org}/login`}>SAML</a>}
            {meta.sso.oidc && <a className="btn-secondary" href={`/api/auth/oidc/${org}/login`}>OpenID Connect</a>}
          </div>
        </div>
      )}
    </AuthShell>
  );
}

import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, SESSION_KEYS, type LoginResponse } from "@/lib/api";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Officer Login - Ikshana" },
      { name: "description", content: "Booth officer authentication for the Ikshana electoral system." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const [officerId, setOfficerId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<LoginResponse | null>(null);

  const login = useMutation({
    mutationFn: () => api.boothLogin(officerId.trim(), password),
    onSuccess: (data) => {
      if (data.status !== "success" || !data.session_token) {
        setSuccess(null);
        setError(data.message || "Invalid credentials");
        return;
      }
      setError(null);
      localStorage.setItem(SESSION_KEYS.token, data.session_token);
      localStorage.setItem(SESSION_KEYS.booth, data.assigned_booth);
      localStorage.setItem(SESSION_KEYS.officer, data.officer_name);
      setSuccess(data);
      window.setTimeout(() => {
        void navigate({ to: "/booth", search: { booth: data.assigned_booth } });
      }, 1200);
    },
    onError: (e: Error) => {
      setSuccess(null);
      setError(`Login failed: ${e.message}`);
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!officerId.trim() || !password) {
      setError("Officer ID and password are required");
      return;
    }
    login.mutate();
  };

  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-md border border-primary/40 bg-primary/10">
            <img
  src="/ikshana-logo.png"
  alt="Ikshana"
  className="h-10 w-10 object-contain"
/>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Ikshana</h1>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Fake Vote Invigilator
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-lg border border-border bg-card p-6 shadow-lg"
        >
          <h2 className="text-sm font-semibold">Booth Officer Login</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Authenticate to access your assigned booth terminal.
          </p>

          <div className="mt-5 space-y-4">
            <div>
              <label htmlFor="officer-id" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Officer ID
              </label>
              <Input
                id="officer-id"
                value={officerId}
                onChange={(e) => setOfficerId(e.target.value.toUpperCase())}
                placeholder="e.g. ECI-BLR-001"
                className="mt-1.5 h-11 font-mono tracking-wider"
                autoComplete="username"
                autoFocus
                disabled={login.isPending || !!success}
              />
            </div>
            <div>
              <label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="********"
                className="mt-1.5 h-11"
                autoComplete="current-password"
                disabled={login.isPending || !!success}
              />
            </div>
          </div>

          {error && (
            <p className="mt-4 text-sm font-medium text-destructive">{error}</p>
          )}

          {success && (
            <div className="mt-4 rounded-md border border-green-500/40 bg-green-500/10 p-3 text-sm">
              <div className="font-medium text-green-400">
                Welcome {success.officer_name}
              </div>
              <div className="mt-0.5 font-mono text-xs text-muted-foreground">
                <Link
                  to="/booth"
                  search={{ booth: success.assigned_booth }}
                  className="text-green-400 underline-offset-4 hover:underline"
                >
                  Booth {success.assigned_booth}
                </Link>{" "}
                is now active. Redirecting...
              </div>
            </div>
          )}

          <Button
            type="submit"
            disabled={login.isPending || !!success}
            className="mt-5 h-11 w-full gap-2"
          >
            <LogIn className="h-4 w-4" />
            {login.isPending ? "Authenticating..." : success ? "Authenticated" : "Login"}
          </Button>
        </form>

        <p className="mt-4 text-center text-[10px] uppercase tracking-wider text-muted-foreground">
          Authorized personnel only - Election Commission
        </p>
      </div>
    </main>
  );
}

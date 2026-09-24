import { useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { LogIn, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { api } from "@/lib/api";

export const Route = createFileRoute("/admin-login")({
  head: () => ({
    meta: [
      { title: "Admin Login — Ikshana" },
      { name: "description", content: "Regional admin authentication for Ikshana." },
    ],
  }),
  component: AdminLoginPage,
});

function AdminLoginPage() {
  const navigate = useNavigate();
  const [officerId, setOfficerId] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<"login" | "otp">("login");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const login = useMutation({
    mutationFn: () => api.adminLogin(officerId.trim(), password),
    onSuccess: (data) => {
      if (data.status !== "otp_sent") {
        setSuccess(null);
        setError(data.message || "Unable to continue with login.");
        return;
      }

      setError(null);
      setSuccess(data.message);
      setStep("otp");
      setOtp("");
    },
    onError: (e: Error) => {
      setSuccess(null);
      setError(`Login failed: ${e.message}`);
    },
  });

  const verifyOtp = useMutation({
    mutationFn: () => api.adminVerifyOtp(officerId.trim(), otp),
    onSuccess: (data) => {
      if (data.status !== "ok") {
        setSuccess(null);
        setError(data.message || "Unable to verify the OTP.");
        return;
      }

      setError(null);
      setSuccess(`${data.officer_name ?? "Officer"} authenticated as ${data.role ?? "admin"}.`);
      window.setTimeout(() => {
        void navigate({ to: data.role === "CEO" ? "/admin-ceo" : "/admin-ro" });
      }, 800);
    },
    onError: (e: Error) => {
      setSuccess(null);
      setError(`Verification failed: ${e.message}`);
    },
  });

  const otpLabel = useMemo(
    () => (step === "otp" ? "Enter the 6-digit verification code" : "Officer ID and password"),
    [step],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (step === "login") {
      if (!officerId.trim() || !password) {
        setError("Officer ID and password are required");
        return;
      }
      login.mutate();
      return;
    }

    if (otp.length !== 6) {
      setError("Enter the full 6-digit OTP code.");
      return;
    }

    verifyOtp.mutate();
  };

  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-md border border-primary/40 bg-primary/10">
            <img src="/ikshana-logo.png" alt="Ikshana" className="h-10 w-10 object-contain" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Ikshana</h1>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Election admin access</p>
        </div>

        <form onSubmit={onSubmit} className="rounded-lg border border-border bg-card p-6 shadow-lg">
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">{step === "login" ? "Administrative Login" : "Verify One-Time Password"}</h2>
          </div>

          <p className="text-xs text-muted-foreground">{otpLabel}</p>

          {step === "login" ? (
            <div className="mt-5 space-y-4">
              <div>
                <label htmlFor="officer-id" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Officer ID
                </label>
                <Input
                  id="officer-id"
                  value={officerId}
                  onChange={(e) => setOfficerId(e.target.value.toUpperCase())}
                  placeholder="e.g. RO-DEL-001"
                  className="mt-1.5 h-11 font-mono tracking-wider"
                  autoComplete="username"
                  autoFocus
                  disabled={login.isPending}
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
                  disabled={login.isPending}
                />
              </div>
            </div>
          ) : (
            <div className="mt-5">
              <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Verification Code
              </label>
              <div className="mt-3 flex justify-center">
                <InputOTP maxLength={6} value={otp} onChange={setOtp} disabled={verifyOtp.isPending}>
                  <InputOTPGroup>
                    {Array.from({ length: 6 }).map((_, index) => (
                      <InputOTPSlot key={index} index={index} className="h-12 w-10 text-base" />
                    ))}
                  </InputOTPGroup>
                </InputOTP>
              </div>
            </div>
          )}

          {error && <p className="mt-4 text-sm font-medium text-destructive">{error}</p>}

          {success && (
            <div className="mt-4 rounded-md border border-green-500/40 bg-green-500/10 p-3 text-sm">
              <div className="font-medium text-green-400">Login request sent</div>
              <div className="mt-0.5 text-muted-foreground">{success}</div>
            </div>
          )}

          <Button type="submit" disabled={login.isPending || verifyOtp.isPending} className="mt-5 h-11 w-full gap-2">
            <LogIn className="h-4 w-4" />
            {step === "login"
              ? login.isPending
                ? "Authenticating..."
                : "Continue"
              : verifyOtp.isPending
                ? "Verifying..."
                : "Verify OTP"}
          </Button>

          {step === "otp" && (
            <button
              type="button"
              onClick={() => {
                setStep("login");
                setError(null);
                setSuccess(null);
                setOtp("");
              }}
              className="mt-3 w-full text-center text-xs font-medium text-muted-foreground underline-offset-4 hover:underline"
            >
              Use a different officer ID
            </button>
          )}
        </form>

        <p className="mt-4 text-center text-[10px] uppercase tracking-wider text-muted-foreground">
          Authorized personnel only - Election Commission
        </p>
      </div>
    </main>
  );
}

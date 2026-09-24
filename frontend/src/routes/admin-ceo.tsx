import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { toast } from "sonner";
import { AlertTriangle, Play, Radio, ShieldCheck, Square, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FraudConfidencePanel } from "@/components/FraudConfidencePanel";
import { FraudEvidenceDialog } from "@/components/FraudEvidenceDialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { api, type FraudType } from "@/lib/api";

export const Route = createFileRoute("/admin-ceo")({
  head: () => ({
    meta: [
      { title: "CEO Dashboard — Ikshana" },
      { name: "description", content: "Chief election officer dashboard with district-wide monitoring and officer registration." },
    ],
  }),
  component: AdminCEOPage,
});

function AdminCEOPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const electionStatus = useQuery({
    queryKey: ["election-status"],
    queryFn: api.electionStatus,
    retry: false,
    refetchInterval: 5000,
  });
  const [startDialogOpen, setStartDialogOpen] = useState(false);
  const [startStep, setStartStep] = useState<"details" | "otp">("details");
  const [startPassword, setStartPassword] = useState("");
  const [startReason, setStartReason] = useState("");
  const [startOtpCode, setStartOtpCode] = useState("");
  const [startError, setStartError] = useState<string | null>(null);
  const [endDialogOpen, setEndDialogOpen] = useState(false);
  const [endStep, setEndStep] = useState<"details" | "otp">("details");
  const [endPassword, setEndPassword] = useState("");
  const [endReason, setEndReason] = useState("");
  const [confirmationText, setConfirmationText] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [confirmationError, setConfirmationError] = useState<string | null>(null);
  const [endError, setEndError] = useState<string | null>(null);

  const overview = useQuery({
    queryKey: ["admin-ceo-overview"],
    queryFn: api.adminCeoOverview,
    retry: false,
    refetchInterval: 15000,
  });
  const fraudLog = useQuery({
    queryKey: ["admin-ceo-fraud-log"],
    queryFn: api.adminCeoFraudLog,
    retry: false,
    refetchInterval: 15000,
  });
  const booths = useQuery({
    queryKey: ["admin-ceo-booths"],
    queryFn: api.adminCeoBooths,
    retry: false,
    refetchInterval: 15000,
  });
  const officers = useQuery({
    queryKey: ["admin-ceo-officers"],
    queryFn: api.adminCeoOfficers,
    retry: false,
    refetchInterval: 15000,
  });
  const accuracy = useQuery({
    queryKey: ["admin-accuracy"],
    queryFn: api.adminAccuracy,
    retry: false,
  });
  const reviewFraud = useMutation({
    mutationFn: ({ id, status, note }: { id: number; status: "confirmed" | "false_positive"; note?: string }) =>
      api.adminReviewFraudLog(id, status, note),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-ceo-fraud-log"] });
      void qc.invalidateQueries({ queryKey: ["admin-accuracy"] });
    },
  });

  useEffect(() => {
    const failed = [overview.error, fraudLog.error, booths.error, officers.error].some((error) => isUnauthorized(error));
    if (failed) {
      void navigate({ to: "/admin-login" });
    }
  }, [booths.error, fraudLog.error, navigate, officers.error, overview.error]);

  const startEl = useMutation({
    mutationFn: (otp?: string) => api.startElection({
      password: startPassword,
      reason: startReason,
      ...(otp ? { otp_code: otp } : {}),
    }),
    onSuccess: (response) => {
      if (response.status === "otp_required") {
        setStartStep("otp");
        setStartError(null);
        return;
      }
      if (response.status !== "ok") {
        setStartError(response.message);
        return;
      }
      toast.success("Election started");
      qc.invalidateQueries();
      setStartDialogOpen(false);
    },
    onError: (e: Error) => setStartError(e.message),
  });

  const endEl = useMutation({
    mutationFn: (otp?: string) => api.endElection({
      password: endPassword,
      reason: endReason,
      confirmation_text: confirmationText,
      ...(otp ? { otp_code: otp } : {}),
    }),
    onSuccess: (response) => {
      if (response.status === "otp_required") {
        setEndStep("otp");
        setEndError(null);
        return;
      }
      if (response.status === "invalid_confirmation") {
        setConfirmationError(response.message);
        setEndStep("details");
        return;
      }
      if (response.status !== "ok") {
        setEndError(response.message);
        return;
      }
      toast.success("Election ended — database truncated");
      qc.invalidateQueries();
      setEndDialogOpen(false);
    },
    onError: (e: Error) => setEndError(e.message),
  });

  const electionName = electionStatus.data?.name ?? "";
  const resetStartDialog = (open: boolean) => {
    setStartDialogOpen(open);
    if (open) return;
    setStartStep("details");
    setStartPassword("");
    setStartReason("");
    setStartOtpCode("");
    setStartError(null);
    startEl.reset();
  };

  const submitStartElection = () => {
    setStartError(null);
    if (startStep === "details") {
      if (!startPassword || !startReason.trim()) {
        setStartError("Password and reason are required.");
        return;
      }
      startEl.mutate(undefined);
      return;
    }
    if (!startOtpCode.trim()) {
      setStartError("Enter the confirmation code.");
      return;
    }
    startEl.mutate(startOtpCode.trim());
  };

  const resetEndDialog = (open: boolean) => {
    setEndDialogOpen(open);
    if (open) return;
    setEndStep("details");
    setEndPassword("");
    setEndReason("");
    setConfirmationText("");
    setOtpCode("");
    setConfirmationError(null);
    setEndError(null);
    endEl.reset();
  };

  const submitEndElection = () => {
    setConfirmationError(null);
    setEndError(null);
    if (endStep === "details") {
      if (confirmationText !== electionName) {
        setConfirmationError("Type the election name exactly to continue.");
        return;
      }
      if (!endPassword || !endReason.trim()) {
        setEndError("Password and reason are required.");
        return;
      }
      endEl.mutate(undefined);
      return;
    }
    if (!otpCode.trim()) {
      setEndError("Enter the confirmation code.");
      return;
    }
    endEl.mutate(otpCode.trim());
  };

  const logout = async () => {
    try {
      await api.adminLogout();
    } catch {
      // Ignore logout issues; redirect to the login page.
    }
    void navigate({ to: "/admin-login" });
  };

  const entries = fraudLog.data ?? [];
  const boothRows = booths.data ?? [];
  const officerRows = officers.data ?? [];

  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">CEO Dashboard</h1>
          <p className="text-sm text-muted-foreground">National election monitoring and officer administration.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <AlertDialog open={startDialogOpen} onOpenChange={resetStartDialog}>
            <AlertDialogTrigger asChild>
              <Button disabled={startEl.isPending} className="gap-2 bg-[oklch(0.55_0.17_145)] text-white hover:bg-[oklch(0.6_0.17_145)]">
                <Play className="h-4 w-4" /> Start Election
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {startStep === "details" ? "Start election?" : "Enter confirmation code"}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {startStep === "details"
                    ? "Verify your password and provide the reason for starting the election. We will send a confirmation code to your email."
                    : "A confirmation code was sent to your registered email address."}
                </AlertDialogDescription>
                {startStep === "details" ? (
                  <div className="space-y-3">
                    <div>
                      <label htmlFor="start-password" className="text-xs font-medium">Password</label>
                      <Input id="start-password" type="password" value={startPassword} onChange={(event) => setStartPassword(event.target.value)} className="mt-1" />
                    </div>
                    <div>
                      <label htmlFor="start-reason" className="text-xs font-medium">Reason</label>
                      <Input id="start-reason" value={startReason} onChange={(event) => setStartReason(event.target.value)} placeholder="Reason for starting the election" className="mt-1" />
                    </div>
                  </div>
                ) : (
                  <div>
                    <label htmlFor="start-otp" className="text-xs font-medium">Confirmation code</label>
                    <Input id="start-otp" inputMode="numeric" value={startOtpCode} onChange={(event) => setStartOtpCode(event.target.value)} className="mt-1 font-mono" />
                  </div>
                )}
                {startError ? <p className="text-sm text-destructive">{startError}</p> : null}
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={(event) => {
                    event.preventDefault();
                    submitStartElection();
                  }}
                  disabled={startEl.isPending}
                >
                  {startEl.isPending ? "Processing..." : startStep === "details" ? "Send confirmation code" : "Start election"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <AlertDialog open={endDialogOpen} onOpenChange={resetEndDialog}>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" className="gap-2">
                <Square className="h-4 w-4" /> End Election
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {endStep === "details" ? "End election & truncate database?" : "Enter confirmation code"}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {endStep === "details"
                    ? "This will mark the election as ended and clear all voter authentication records from the database. This action cannot be undone."
                    : "A confirmation code was sent to your registered email address."}
                </AlertDialogDescription>
                {endStep === "details" ? (
                  <div className="space-y-3">
                    <div>
                      <label htmlFor="end-confirmation" className="text-xs font-medium">
                        Type <span className="font-mono text-primary">{electionName || "the election name"}</span> to confirm
                      </label>
                      <Input
                        id="end-confirmation"
                        value={confirmationText}
                        onChange={(event) => {
                          setConfirmationText(event.target.value);
                          setConfirmationError(null);
                        }}
                        placeholder={electionName}
                        aria-invalid={Boolean(confirmationError)}
                        className={`mt-1 font-mono ${confirmationError ? "border-destructive" : ""}`}
                      />
                      {confirmationError ? <p className="mt-1 text-xs text-destructive">{confirmationError}</p> : null}
                    </div>
                    <div>
                      <label htmlFor="end-password" className="text-xs font-medium">Password</label>
                      <Input id="end-password" type="password" value={endPassword} onChange={(event) => setEndPassword(event.target.value)} className="mt-1" />
                    </div>
                    <div>
                      <label htmlFor="end-reason" className="text-xs font-medium">Reason</label>
                      <Input id="end-reason" value={endReason} onChange={(event) => setEndReason(event.target.value)} placeholder="Reason for ending the election" className="mt-1" />
                    </div>
                  </div>
                ) : (
                  <div>
                    <label htmlFor="end-otp" className="text-xs font-medium">Confirmation code</label>
                    <Input id="end-otp" inputMode="numeric" value={otpCode} onChange={(event) => setOtpCode(event.target.value)} className="mt-1 font-mono" />
                  </div>
                )}
                {endError ? <p className="text-sm text-destructive">{endError}</p> : null}
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={(event) => {
                      event.preventDefault();
                      submitEndElection();
                    }}
                    disabled={endEl.isPending || (endStep === "details" && (!electionName || confirmationText !== electionName))}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {endEl.isPending ? "Processing..." : endStep === "details" ? "Send confirmation code" : "Yes, end election"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button variant="outline" onClick={() => void logout()} className="gap-2">
            <ShieldCheck className="h-4 w-4" /> Log out
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        <StatCard icon={<Users className="h-5 w-5 text-primary" />} label="Total Voters" value={overview.data?.total_voters ?? 0} />
        <StatCard icon={<ShieldCheck className="h-5 w-5 text-[oklch(0.78_0.17_145)]" />} label="Authenticated" value={overview.data?.voters_authenticated ?? 0} />
        <StatCard icon={<Radio className="h-5 w-5 text-[oklch(0.72_0.12_210)]" />} label="Active Booths" value={overview.data?.active_booths ?? 0} />
        <StatCard icon={<AlertTriangle className="h-5 w-5 text-destructive" />} label="Total Booths" value={overview.data?.total_booths ?? 0} accent="destructive" />
      </div>

      <div className="mt-6">
        <FraudConfidencePanel data={accuracy.data} isLoading={accuracy.isLoading} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="space-y-6">
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Booth Status</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Booth</th>
                    <th className="px-4 py-2 text-left font-medium">Constituency</th>
                    <th className="px-4 py-2 text-left font-medium">Status</th>
                    <th className="px-4 py-2 text-left font-medium">Officer</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-xs">
                  {boothRows.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                        {booths.isLoading ? "Loading booths..." : "No booths available."}
                      </td>
                    </tr>
                  )}
                  {boothRows.map((booth) => (
                    <tr key={booth.booth_id}>
                      <td className="px-4 py-2 font-mono">{booth.booth_id}</td>
                      <td className="px-4 py-2 text-muted-foreground">{booth.constituency ?? "—"}</td>
                      <td className="px-4 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${booth.status === "active" ? "bg-green-500/15 text-green-400" : "bg-muted text-muted-foreground"}`}>
                          {booth.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{booth.officer_name ?? "Unassigned"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Fraud Log</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Timestamp</th>
                    <th className="px-4 py-2 text-left font-medium">Voter ID</th>
                    <th className="px-4 py-2 text-left font-medium">Booth</th>
                    <th className="px-4 py-2 text-left font-medium">Type</th>
                    <th className="px-4 py-2 text-left font-medium">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-xs">
                  {entries.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                        {fraudLog.isLoading ? "Loading fraud log..." : "No fraud incidents recorded."}
                      </td>
                    </tr>
                  )}
                  {entries.map((entry) => (
                    <tr key={`${entry.timestamp}-${entry.voter_id}-${entry.booth_id}`} className="align-top">
                      <td className="px-4 py-2 font-mono">{safeTime(entry.timestamp)}</td>
                      <td className="px-4 py-2 font-mono">{maskVoterId(entry.voter_id)}</td>
                      <td className="px-4 py-2 font-mono">{entry.booth_id}</td>
                      <td className="px-4 py-2">{entry.fraud_type ? <FraudBadge type={entry.fraud_type} /> : "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground">
                        <div className="space-y-2">
                          <div>{entry.details ?? "—"}</div>
                          {entry.match_metric && entry.match_score != null ? (
                            <div className="text-[11px] text-foreground">
                              <span className="font-medium">{entry.match_metric}:</span> {entry.match_score}
                            </div>
                          ) : null}
                          {entry.original_vote ? (
                            <div className="font-medium text-amber-400">
                              Originally voted at Booth {entry.original_vote.booth_id}, {safeTime(entry.original_vote.timestamp)}
                            </div>
                          ) : null}
                          <div className="flex flex-wrap items-center gap-2">
                            <ReviewStatusBadge status={entry.review_status ?? null} />
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void reviewFraud.mutate({ id: entry.id, status: "confirmed" })}
                              disabled={reviewFraud.isPending || entry.review_status === "confirmed"}
                            >
                              Confirm
                            </Button>
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => void reviewFraud.mutate({ id: entry.id, status: "false_positive" })}
                              disabled={reviewFraud.isPending || entry.review_status === "false_positive"}
                            >
                              False positive
                            </Button>
                          </div>
                          {entry.evidence_photo_url ? (
                            <FraudEvidenceDialog
                              entry={entry}
                              formattedTimestamp={safeTime(entry.timestamp)}
                              formattedOriginalVoteTimestamp={entry.original_vote ? safeTime(entry.original_vote.timestamp) : undefined}
                            />
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <aside className="space-y-6">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Register Officer</h2>
            </div>
            <RegisterOfficerForm onRegistered={() => qc.invalidateQueries({ queryKey: ["admin-ceo-officers"] })} />
          </div>

          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold">Officers</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium">Officer</th>
                    <th className="px-4 py-2 text-left font-medium">Booth</th>
                    <th className="px-4 py-2 text-left font-medium">Constituency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-xs">
                  {officerRows.length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">
                        {officers.isLoading ? "Loading officers..." : "No officers registered."}
                      </td>
                    </tr>
                  )}
                  {officerRows.map((officer) => (
                    <tr key={officer.officer_id}>
                      <td className="px-4 py-2">
                        <div className="font-medium">{officer.name}</div>
                        <div className="font-mono text-[10px] text-muted-foreground">{officer.officer_id}</div>
                      </td>
                      <td className="px-4 py-2 font-mono">{officer.assigned_booth ?? "—"}</td>
                      <td className="px-4 py-2">{officer.constituency ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

function RegisterOfficerForm({ onRegistered }: { onRegistered: () => void }) {
  const [officerId, setOfficerId] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [assignedBooth, setAssignedBooth] = useState("");
  const [constituency, setConstituency] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const register = useMutation({
    mutationFn: () =>
      api.ceoRegisterOfficer({
        officer_id: officerId.trim(),
        name: name.trim(),
        password,
        assigned_booth: assignedBooth.trim(),
        constituency: constituency.trim() || undefined,
      }),
    onSuccess: (data) => {
      const valid = data.status === "ok";
      setSuccess(valid);
      setMessage(data.message);
      if (valid) {
        setOfficerId("");
        setName("");
        setPassword("");
        setAssignedBooth("");
        setConstituency("");
        onRegistered();
      }
    },
    onError: (e: Error) => {
      setSuccess(false);
      setMessage(`Registration failed: ${e.message}`);
    },
  });

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!officerId.trim() || !name.trim() || !password || !assignedBooth.trim()) {
      setSuccess(false);
      setMessage("Officer ID, name, password, and assigned booth are required.");
      return;
    }
    setMessage(null);
    register.mutate();
  };

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div>
        <label htmlFor="officer-id" className="text-[10px] uppercase tracking-wider text-muted-foreground">Officer ID</label>
        <Input id="officer-id" value={officerId} onChange={(e) => setOfficerId(e.target.value.toUpperCase())} placeholder="e.g. BLO-BLR-001" className="mt-1 h-10 font-mono" />
      </div>
      <div>
        <label htmlFor="officer-name" className="text-[10px] uppercase tracking-wider text-muted-foreground">Name</label>
        <Input id="officer-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" className="mt-1 h-10" />
      </div>
      <div>
        <label htmlFor="officer-password" className="text-[10px] uppercase tracking-wider text-muted-foreground">Password</label>
        <Input id="officer-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="********" className="mt-1 h-10" />
      </div>
      <div>
        <label htmlFor="officer-booth" className="text-[10px] uppercase tracking-wider text-muted-foreground">Assigned Booth</label>
        <Input id="officer-booth" value={assignedBooth} onChange={(e) => setAssignedBooth(e.target.value.toUpperCase())} placeholder="e.g. BC-B01" className="mt-1 h-10 font-mono" />
      </div>
      <div>
        <label htmlFor="officer-constituency" className="text-[10px] uppercase tracking-wider text-muted-foreground">Constituency (optional)</label>
        <Input id="officer-constituency" value={constituency} onChange={(e) => setConstituency(e.target.value)} placeholder="e.g. Bangalore Central" className="mt-1 h-10" />
      </div>

      {message && (
        <p className={`text-sm font-medium ${success ? "text-green-400" : "text-destructive"}`}>
          {message}
        </p>
      )}

      <Button type="submit" disabled={register.isPending} className="w-full h-10">
        {register.isPending ? "Registering..." : "Register officer"}
      </Button>
    </form>
  );
}

function StatCard({ icon, label, value, accent }: { icon: React.ReactNode; label: string; value: number | string; accent?: "destructive" }) {
  return (
    <div className={`rounded-lg border border-border bg-card p-4 ${accent === "destructive" ? "border-destructive/40" : ""}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
        {icon}
      </div>
      <div className="mt-2 font-mono text-3xl font-bold tracking-tight">{value}</div>
    </div>
  );
}

function ReviewStatusBadge({ status }: { status: string | null }) {
  if (status === "confirmed") return <span className="rounded-full bg-green-500/15 px-2 py-0.5 text-[10px] font-semibold text-green-400">confirmed</span>;
  if (status === "false_positive") return <span className="rounded-full bg-yellow-500/15 px-2 py-0.5 text-[10px] font-semibold text-yellow-300">false_positive</span>;
  return <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">unreviewed</span>;
}

function FraudBadge({ type }: { type: FraudType }) {
  const normalized = String(type).toLowerCase().replace(/[_\s-]+/g, " ");
  const color = normalized.includes("duplicate")
    ? "bg-destructive/15 text-destructive"
    : normalized.includes("identity")
      ? "bg-orange-500/15 text-orange-400"
      : "bg-purple-500/15 text-purple-300";
  return <span className={`rounded-full px-2 py-0.5 font-sans text-[10px] font-semibold ${color}`}>{labelForFraud(type)}</span>;
}

function labelForFraud(t: FraudType) {
  return String(t).replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function maskVoterId(id: string) {
  return id.length <= 6 ? id : `${id.slice(0, 3)}••••${id.slice(-3)}`;
}

function safeTime(ts?: string) {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return format(d, "dd/MM/yyyy HH:mm:ss");
}

function isUnauthorized(error: unknown) {
  return Boolean(error) && (error instanceof Error ? /401/.test(error.message) : false);
}

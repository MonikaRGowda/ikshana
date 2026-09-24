import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { AlertTriangle, Building2, ShieldCheck, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FraudConfidencePanel } from "@/components/FraudConfidencePanel";
import { FraudEvidenceDialog } from "@/components/FraudEvidenceDialog";
import { api, type FraudType } from "@/lib/api";

export const Route = createFileRoute("/admin-ro")({
  head: () => ({
    meta: [
      { title: "RO Dashboard — Ikshana" },
      { name: "description", content: "Regional officer monitoring for constituency activity and fraud alerts." },
    ],
  }),
  component: AdminROPage,
});

function AdminROPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const overview = useQuery({
    queryKey: ["admin-ro-overview"],
    queryFn: api.adminRoOverview,
    retry: false,
    refetchInterval: 15000,
  });
  const fraudLog = useQuery({
    queryKey: ["admin-ro-fraud-log"],
    queryFn: api.adminRoFraudLog,
    retry: false,
    refetchInterval: 15000,
  });
  const booths = useQuery({
    queryKey: ["admin-ro-booths"],
    queryFn: api.adminRoBooths,
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
      void qc.invalidateQueries({ queryKey: ["admin-ro-fraud-log"] });
      void qc.invalidateQueries({ queryKey: ["admin-accuracy"] });
    },
  });

  useEffect(() => {
    const failed = [overview.error, fraudLog.error, booths.error].some((error) => isUnauthorized(error));
    if (failed) {
      void navigate({ to: "/admin-login" });
    }
  }, [booths.error, fraudLog.error, navigate, overview.error]);

  const logout = async () => {
    try {
      await api.adminLogout();
    } catch {
      // Ignore logout issues; redirect to the admin login screen.
    }
    void navigate({ to: "/admin-login" });
  };

  const entries = fraudLog.data ?? [];
  const boothRows = booths.data ?? [];

  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Returning Officer Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {overview.data ? `Constituency: ${overview.data.constituency}` : "Monitoring constituency activity."}
          </p>
        </div>
        <Button variant="outline" onClick={() => void logout()} className="gap-2">
          <ShieldCheck className="h-4 w-4" />
          Log out
        </Button>
      </div>

      {overview.isError ? (
        <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          Unable to load your overview. Please sign in again.
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-4">
        <StatCard icon={<Users className="h-5 w-5 text-primary" />} label="Voters" value={overview.data?.total_voters ?? 0} />
        <StatCard icon={<ShieldCheck className="h-5 w-5 text-[oklch(0.78_0.17_145)]" />} label="Authenticated" value={overview.data?.voters_authenticated ?? 0} />
        <StatCard icon={<Building2 className="h-5 w-5 text-[oklch(0.7_0.12_210)]" />} label="Active Booths" value={overview.data?.active_booths ?? 0} />
        <StatCard icon={<AlertTriangle className="h-5 w-5 text-destructive" />} label="Total Booths" value={overview.data?.total_booths ?? 0} accent="destructive" />
      </div>

      <div className="mt-6">
        <FraudConfidencePanel data={accuracy.data} isLoading={accuracy.isLoading} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Booth Status</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Booth</th>
                  <th className="px-4 py-2 text-left font-medium">Status</th>
                  <th className="px-4 py-2 text-left font-medium">Officer</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-xs">
                {boothRows.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">
                      {booths.isLoading ? "Loading booth list..." : "No booths assigned to this constituency."}
                    </td>
                  </tr>
                )}
                {boothRows.map((booth) => (
                  <tr key={booth.booth_id}>
                    <td className="px-4 py-2 font-mono">{booth.booth_id}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          booth.status === "active"
                            ? "bg-green-500/15 text-green-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {booth.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">{booth.officer_name ?? "Unassigned"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Fraud Summary</h2>
          </div>
          <div className="p-4">
            <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Active alerts</div>
              <div className="mt-2 font-mono text-3xl font-bold text-destructive">{entries.length}</div>
            </div>
          </div>
        </aside>
      </div>

      <section className="mt-6 rounded-lg border border-border bg-card">
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
                  <td className="px-4 py-2">
                    {entry.fraud_type ? <FraudBadge type={entry.fraud_type} /> : "—"}
                  </td>
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
      </section>
    </main>
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

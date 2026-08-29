import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { toast } from "sonner";
import { AlertTriangle, Play, Square, ShieldCheck, Users, Radio } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { api, type AuditEntry, type FraudType } from "@/lib/api";
import { useSocketEvent } from "@/lib/socket";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Admin Dashboard — Ikshana" },
      { name: "description", content: "Election monitoring, fraud alerts, and audit log." },
    ],
  }),
  component: AdminPage,
});

interface FraudAlert {
  id: string;
  fraud_type: FraudType;
  voter_id: string;
  booth_id: string;
  timestamp: string;
  message?: string;
  details?: string;
}

function AdminPage() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["election-status"], queryFn: api.electionStatus, retry: false, refetchInterval: 5000 });
  const audit = useQuery({ queryKey: ["audit-log"], queryFn: api.auditLog, retry: false, refetchInterval: 5000 });
  const [alerts, setAlerts] = useState<FraudAlert[]>([]);
  const [flash, setFlash] = useState(false);
  const [authenticatedCount, setAuthenticatedCount] = useState(0);
  const [fraudAttemptCount, setFraudAttemptCount] = useState(0);

  useEffect(() => { setAuthenticatedCount(status.data?.total_votes ?? 0); }, [status.data?.total_votes]);
  useEffect(() => { setFraudAttemptCount((audit.data ?? []).filter((entry) => entry.fraud_type).length); }, [audit.data]);
  useEffect(() => {
    setAlerts((audit.data ?? [])
      .filter((entry) => entry.fraud_type)
      .map((entry) => ({
        id: `${entry.timestamp}:${entry.voter_id}:${entry.booth_id}`,
        fraud_type: entry.fraud_type ?? "fraud_detected",
        voter_id: entry.voter_id,
        booth_id: entry.booth_id,
        timestamp: entry.timestamp,
        message: entry.details,
      }))
      .slice(0, 100));
  }, [audit.data]);

  useSocketEvent<FraudAlert>("fraud_detected", (alert) => {
    setAlerts((a) => [{ ...alert, id: alert.id ?? crypto.randomUUID() }, ...a].slice(0, 100));
    setFraudAttemptCount((count) => count + 1);
    qc.setQueryData<AuditEntry[]>(["audit-log"], (current = []) => [{
      timestamp: alert.timestamp,
      voter_id: alert.voter_id,
      booth_id: alert.booth_id,
      status: "fraud_detected",
      fraud_type: alert.fraud_type,
      details: alert.message ?? alert.details,
    }, ...current]);
    setFlash(true);
    qc.invalidateQueries({ queryKey: ["audit-log"] });
    toast.error(`Fraud detected: ${labelForFraud(alert.fraud_type)}`);
  });
  useSocketEvent("voter_authenticated", () => {
    setAuthenticatedCount((count) => count + 1);
  });
  useSocketEvent("election_reset", () => {
    setAlerts([]);
    qc.invalidateQueries();
    toast.info("Election reset");
  });

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(false), 600);
    return () => clearTimeout(t);
  }, [flash]);

  const startEl = useMutation({
    mutationFn: api.startElection,
    onSuccess: () => { toast.success("Election started"); qc.invalidateQueries(); },
    onError: (e: Error) => toast.error(`Failed: ${e.message}`),
  });
  const endEl = useMutation({
    mutationFn: api.endElection,
    onSuccess: () => { toast.success("Election ended — database truncated"); qc.invalidateQueries(); },
    onError: (e: Error) => toast.error(`Failed: ${e.message}`),
  });

  const entries = audit.data ?? [];
  const fraudCount = fraudAttemptCount;
  const authCount = authenticatedCount;
  const boothCount = status.data?.active_booths ?? 0;

  return (
    <main
      className={`mx-auto max-w-7xl px-4 py-6 transition-colors duration-300 ${flash ? "bg-destructive/10" : ""}`}
    >
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin Dashboard</h1>
          <p className="text-sm text-muted-foreground">Live monitoring across all polling booths.</p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => startEl.mutate()}
            disabled={startEl.isPending || status.data?.status === "active"}
            className="gap-2 bg-[oklch(0.55_0.17_145)] text-white hover:bg-[oklch(0.6_0.17_145)]"
          >
            <Play className="h-4 w-4" /> Start Election
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" className="gap-2">
                <Square className="h-4 w-4" /> End Election
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>End election & truncate database?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will mark the election as ended and clear all voter authentication
                  records from the database. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => endEl.mutate()}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Yes, end election
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={<ShieldCheck className="h-5 w-5 text-[oklch(0.78_0.17_145)]" />} label="Total Authenticated" value={authCount} />
        <StatCard icon={<AlertTriangle className="h-5 w-5 text-destructive" />} label="Fraud Attempts" value={fraudCount} accent="destructive" />
        <StatCard icon={<Users className="h-5 w-5 text-primary" />} label="Booths Active" value={boothCount} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Audit Log</h2>
            <p className="text-xs text-muted-foreground">All authentication attempts across booths.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Timestamp</th>
                  <th className="px-4 py-2 text-left font-medium">Voter ID</th>
                  <th className="px-4 py-2 text-left font-medium">Booth</th>
                  <th className="px-4 py-2 text-left font-medium">Fraud Type</th>
                  <th className="px-4 py-2 text-left font-medium">Details / Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono text-xs">
                {entries.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                      {audit.isError ? "Backend offline — audit log unavailable." : "No entries yet."}
                    </td>
                  </tr>
                )}
                {entries.map((row, i) => (
                  <tr key={i} className={row.fraud_type ? "bg-destructive/5" : ""}>
                    <td className="px-4 py-2">{safeTime(row.timestamp)}</td>
                    <td className="px-4 py-2">{maskTableVoterId(row.voter_id)}</td>
                    <td className="px-4 py-2">{row.booth_id}</td>
                    <td className="px-4 py-2">
                      {row.fraud_type ? <FraudBadge type={row.fraud_type} /> : "—"}
                    </td>
                    <td className="px-4 py-2 font-sans text-muted-foreground">{row.details ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-destructive" />
              <h2 className="text-sm font-semibold">Fraud Alerts</h2>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {alerts.length}
            </span>
          </div>
          <ul className="max-h-[600px] overflow-y-auto divide-y divide-border">
            {alerts.length === 0 && (
              <li className="px-4 py-6 text-center text-xs text-muted-foreground">
                No fraud alerts. System monitoring…
              </li>
            )}
            {alerts.map((a) => (
              <li key={a.id} className="border-l-2 border-l-destructive px-4 py-3 animate-in slide-in-from-right">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-destructive">
                      {labelForFraud(a.fraud_type)}
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                      {a.voter_id} · {a.booth_id}
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {safeTime(a.timestamp)}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </main>
  );
}

function StatCard({
  icon, label, value, accent,
}: { icon: React.ReactNode; label: string; value: number | string; accent?: "destructive" }) {
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

function labelForFraud(t: FraudType) {
  return String(t).replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function FraudBadge({ type }: { type: FraudType }) {
  const normalized = String(type).toLowerCase().replace(/[_\s-]+/g, " ");
  const color = normalized.includes("duplicate") ? "bg-destructive/15 text-destructive" : normalized.includes("identity") ? "bg-orange-500/15 text-orange-400" : "bg-purple-500/15 text-purple-300";
  return <span className={`rounded-full px-2 py-0.5 font-sans text-[10px] font-semibold ${color}`}>{labelForFraud(type)}</span>;
}

function maskTableVoterId(id: string) {
  return id.length <= 6 ? id : `${id.slice(0, 3)}${"\u2022".repeat(4)}${id.slice(-3)}`;
}

function maskVoterId(id: string) {
  return id.length <= 6 ? id : `${id.slice(0, 3)}••••${id.slice(-3)}`;
}

function safeTime(ts?: string) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return format(d, "dd/MM/yyyy HH:mm:ss");
}

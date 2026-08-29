import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api, type ElectionStatus } from "@/lib/api";
import { useSocketEvent } from "@/lib/socket";
import { useQueryClient } from "@tanstack/react-query";
import { Shield } from "lucide-react";

type ElectionStatsUpdate = Pick<ElectionStatus, "total_votes" | "active_booths">;

export function ElectionStatusBar() {
  const qc = useQueryClient();
  const { data, isError } = useQuery<ElectionStatus>({
    queryKey: ["election-status"],
    queryFn: api.electionStatus,
    refetchInterval: 5000,
    retry: false,
  });

  useSocketEvent("voter_authenticated", () =>
    qc.invalidateQueries({ queryKey: ["election-status"] }),
  );
  useSocketEvent("election_reset", () =>
    qc.invalidateQueries({ queryKey: ["election-status"] }),
  );
  useSocketEvent<ElectionStatsUpdate>("election_stats_updated", (stats) => {
    qc.setQueryData<ElectionStatus>(["election-status"], (current) =>
      current ? { ...current, ...stats } : current,
    );
  });

  const status = data?.status ?? (isError ? "offline" : "loading");
  const isActive = status === "active";

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <img
  src="/ikshana-logo.png"
  alt="Ikshana"
  className="h-10 w-10 object-contain"
/>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold tracking-tight text-primary">
                IKSHANA
              </span>
              <span className="text-xs text-muted-foreground">
                Fake Vote Invigilator
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              {data?.name ?? "Election Control System"}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs sm:text-sm">
          <StatusPill state={status} />
          <Stat label="Votes Cast" value={data?.total_votes ?? "—"} />
          <Stat label="Active Booths" value={data?.active_booths ?? "—"} />

          <nav className="ml-2 flex items-center gap-1 rounded-md border border-border bg-background/50 p-1">
            <NavLink to="/booth" label="Booth" />
            <NavLink to="/admin" label="Admin" />
          </nav>
        </div>
      </div>
    </header>
  );
}

function NavLink({ to, label }: { to: "/booth" | "/admin"; label: string }) {
  return (
    <Link
      to={to}
      className="rounded px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground data-[status=active]:bg-primary data-[status=active]:text-primary-foreground"
      activeProps={{ "data-status": "active" } as never}
    >
      {label}
    </Link>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-sm font-semibold text-foreground">
        {value}
      </span>
    </div>
  );
}

function StatusPill({ state }: { state: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active: {
      label: "ACTIVE",
      cls: "bg-[oklch(0.68_0.17_145/0.15)] text-[oklch(0.78_0.17_145)] border-[oklch(0.68_0.17_145/0.4)]",
    },
    ended: {
      label: "ENDED",
      cls: "bg-destructive/15 text-destructive border-destructive/40",
    },
    loading: {
      label: "CONNECTING",
      cls: "bg-muted text-muted-foreground border-border",
    },
    offline: {
      label: "OFFLINE",
      cls: "bg-destructive/15 text-destructive border-destructive/40",
    },
  };
  const c = map[state] ?? map.loading;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold tracking-wider ${c.cls}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {c.label}
    </span>
  );
}

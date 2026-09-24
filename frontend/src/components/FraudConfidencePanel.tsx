import type { AccuracySummaryResponse } from "@/lib/api";

interface FraudConfidencePanelProps {
  data?: AccuracySummaryResponse;
  isLoading: boolean;
}

export function FraudConfidencePanel({ data, isLoading }: FraudConfidencePanelProps) {
  return (
    <section className="rounded-lg border border-border bg-card p-4" aria-labelledby="fraud-confidence-title">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 id="fraud-confidence-title" className="text-sm font-semibold">Fraud confidence rate</h2>
          <p className="text-xs text-muted-foreground">
            {data?.scope === "global" ? "Global reporting" : "Constituency reporting"}
          </p>
        </div>
        {isLoading ? <span className="text-xs text-muted-foreground">Loading...</span> : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Total flagged" value={data?.total_flagged ?? "—"} />
        <MetricTile label="Total authenticated" value={data?.total_authenticated ?? "—"} />
        <MetricTile label="Detection rate" value={formatPercent(data?.detection_rate)} />
        <MetricTile
          label="Confidence rate (precision)"
          value={data?.reviewed_count ? formatPercent(data.precision) : "Not enough reviewed data yet"}
          compact={Boolean(data && data.reviewed_count > 0)}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
        <span><strong className="font-semibold text-foreground">{data?.confirmed_count ?? "—"}</strong> confirmed</span>
        <span><strong className="font-semibold text-foreground">{data?.false_positive_count ?? "—"}</strong> false positives</span>
        <span><strong className="font-semibold text-foreground">{data?.unreviewed_count ?? "—"}</strong> unreviewed</span>
        <span><strong className="font-semibold text-foreground">{data?.reviewed_count ?? "—"}</strong> reviewed</span>
      </div>

      <div className="mt-3 grid gap-3 border-t border-border pt-3 sm:grid-cols-2">
        <MetricTile
          label="Avg. fingerprint match score (higher = more similar)"
          value={formatMetric(data?.avg_fingerprint_score)}
        />
        <MetricTile
          label="Avg. face match distance (lower = more similar)"
          value={formatMetric(data?.avg_face_distance)}
        />
      </div>
    </section>
  );
}

function MetricTile({ label, value, compact = false }: { label: string; value: number | string; compact?: boolean }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`mt-2 font-mono font-bold tracking-tight ${compact ? "text-2xl" : "text-xl"}`}>{value}</div>
    </div>
  );
}

function formatPercent(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatMetric(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(3);
}
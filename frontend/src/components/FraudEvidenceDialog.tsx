import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_BASE, type AdminROFraudEntry } from "@/lib/api";

type FraudEvidenceEntry = Pick<
  AdminROFraudEntry,
  "timestamp" | "voter_id" | "booth_id" | "fraud_type" | "original_vote" | "evidence_photo_url" | "match_score" | "match_metric"
>;

type ImageState = "idle" | "loading" | "ready" | "not-found" | "unauthorized" | "error";

export function FraudEvidenceDialog({
  entry,
  formattedTimestamp,
  formattedOriginalVoteTimestamp,
}: {
  entry: FraudEvidenceEntry;
  formattedTimestamp: string;
  formattedOriginalVoteTimestamp?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageState, setImageState] = useState<ImageState>("idle");

  useEffect(() => {
    if (!isOpen || !entry.evidence_photo_url) return;

    const controller = new AbortController();
    let objectUrl: string | null = null;
    setImageUrl(null);
    setImageState("loading");

    fetch(`${API_BASE}${entry.evidence_photo_url}`, {
      credentials: "include",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          setImageState(response.status === 404 ? "not-found" : response.status === 401 ? "unauthorized" : "error");
          return;
        }
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        setImageUrl(objectUrl);
        setImageState("ready");
      })
      .catch((error: unknown) => {
        if ((error as { name?: string }).name !== "AbortError") setImageState("error");
      });

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [entry.evidence_photo_url, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen]);

  if (!entry.evidence_photo_url) return null;

  return (
    <>
      <Button type="button" variant="link" size="sm" className="h-auto p-0" onClick={() => setIsOpen(true)}>
        View Evidence
      </Button>
      {isOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          role="presentation"
          onClick={() => setIsOpen(false)}
        >
          <div
            className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-lg border border-border bg-card p-5 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="evidence-dialog-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 id="evidence-dialog-title" className="text-base font-semibold">Fraud Evidence</h2>
                <div className="mt-2 grid gap-x-6 gap-y-1 text-xs text-muted-foreground sm:grid-cols-2">
                  <div><span className="font-medium text-foreground">Voter:</span> {entry.voter_id}</div>
                  <div><span className="font-medium text-foreground">Booth:</span> {entry.booth_id}</div>
                  <div><span className="font-medium text-foreground">Type:</span> {entry.fraud_type ?? "—"}</div>
                  <div><span className="font-medium text-foreground">Timestamp:</span> {formattedTimestamp}</div>
                  {entry.match_metric && entry.match_score != null ? (
                    <div className="sm:col-span-2">
                      <span className="font-medium text-foreground">Match metric:</span> {entry.match_metric} = {entry.match_score}
                    </div>
                  ) : null}
                  {entry.original_vote ? (
                    <div className="sm:col-span-2">
                      <span className="font-medium text-foreground">Original vote:</span>{" "}
                      Booth {entry.original_vote.booth_id}, {formattedOriginalVoteTimestamp ?? entry.original_vote.timestamp}
                    </div>
                  ) : null}
                </div>
              </div>
              <Button type="button" variant="ghost" size="icon" aria-label="Close evidence" onClick={() => setIsOpen(false)}>
                <X />
              </Button>
            </div>

            <div className="flex min-h-48 items-center justify-center rounded-md border border-border bg-muted/20 p-3">
              {imageState === "loading" ? <p className="text-sm text-muted-foreground">Loading evidence photo...</p> : null}
              {imageState === "ready" && imageUrl ? (
                <img src={imageUrl} alt={`Fraud evidence for voter ${entry.voter_id}`} className="max-h-[60vh] max-w-full object-contain" />
              ) : null}
              {imageState === "not-found" ? <p className="text-sm text-muted-foreground">Photo not found.</p> : null}
              {imageState === "unauthorized" ? <p className="text-sm text-destructive">Your session has expired. Please sign in again.</p> : null}
              {imageState === "error" ? <p className="text-sm text-destructive">Unable to load the evidence photo.</p> : null}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
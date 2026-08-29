import { useCallback, useEffect, useRef, useState, type FormEvent, type RefObject } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { Fingerprint, ScanFace, Search, CheckCircle2, XCircle, AlertTriangle, Radio } from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, SESSION_KEYS, type BiometricResponse, type FingerprintResponse, type VerifyResponse } from "@/lib/api";
import { useSocketEvent } from "@/lib/socket";

const searchSchema = z.object({ booth: z.string().optional() });

export const Route = createFileRoute("/booth")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "Booth Terminal — Ikshana" },
      { name: "description", content: "Voter authentication terminal for polling booth officers." },
    ],
  }),
  component: BoothPage,
});

interface FeedItem {
  voter_id: string;
  booth_id: string;
  status: string;
  timestamp: string;
  fraud_type?: string | null;
  message?: string;
}

function BoothPage() {
  const { booth } = Route.useSearch();
  const navigate = useNavigate();
  const storedBooth = typeof window !== "undefined" ? localStorage.getItem(SESSION_KEYS.booth) : null;
  const boothId = booth ?? storedBooth ?? "BC-B01";
  const [voterId, setVoterId] = useState("");
  const [verifiedVoterId, setVerifiedVoterId] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [fingerprintResult, setFingerprintResult] = useState<FingerprintResponse | null>(null);
  const [biometricResult, setBiometricResult] = useState<BiometricResponse | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem(SESSION_KEYS.token);
    if (!token) {
      navigate({ to: "/login" });
    }
  }, [navigate]);

  useEffect(() => stopCamera, [stopCamera]);

  useEffect(() => {
    if (cameraActive && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [cameraActive]);

  const verify = useMutation({
    mutationFn: (id: string) => {
      const token = localStorage.getItem(SESSION_KEYS.token) ?? "";
      return api.verifyVoter(id, boothId, token);
    },
    onSuccess: (data, id) => {
      setResult(data);
      setVerifiedVoterId(data.status === "verified" ? id : null);
      setFingerprintResult(null);
      setBiometricResult(null);
      stopCamera();
    },
    onError: (e: Error) =>
      setResult({ status: "not_found", message: `Backend unreachable: ${e.message}` }),
  });

  const biometric = useMutation({
    mutationFn: (faceImage: string) => {
      const token = localStorage.getItem(SESSION_KEYS.token) ?? "";
      return api.verifyBiometric(verifiedVoterId ?? voterId, boothId, token, faceImage);
    },
    onSuccess: (data) => setBiometricResult(data),
    onError: (e: Error) =>
      setBiometricResult({ status: "failed", message: `Biometric service unreachable: ${e.message}` }),
  });

  const fingerprint = useMutation({
    mutationFn: () => {
      const token = localStorage.getItem(SESSION_KEYS.token) ?? "";
      return api.scanFingerprint(verifiedVoterId ?? voterId, boothId, token);
    },
    onMutate: () => {
      setFingerprintResult({ status: "failed", message: "Place voter's finger on the scanner..." });
      setBiometricResult(null);
      stopCamera();
    },
    onSuccess: (data) => {
      setFingerprintResult(data);
      if (data.status !== "ready") {
        setBiometricResult(null);
        stopCamera();
      }
    },
    onError: (e: Error) =>
      setFingerprintResult({ status: "failed", message: `Fingerprint service unreachable: ${e.message}` }),
  });

  useSocketEvent<FeedItem>("voter_authenticated", (item) => {
    setFeed((f) => [{ ...item, status: "authenticated" }, ...f].slice(0, 50));
  });
  useSocketEvent("election_reset", () => {
    setFeed([]);
    setResult(null);
    setVerifiedVoterId(null);
    setFingerprintResult(null);
    setBiometricResult(null);
    setVoterId("");
    stopCamera();
    toast.info("Election reset — booth cleared");
  });
  useSocketEvent<FeedItem>("fraud_detected", (item) => {
    setFeed((f) => [{ ...item, status: "fraud_detected" }, ...f].slice(0, 50));
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const parsed = z.string().trim().min(4).max(24).regex(/^[A-Za-z0-9-]+$/).safeParse(voterId);
    if (!parsed.success) {
      toast.error("Enter a valid Voter ID (4–24 alphanumeric chars)");
      return;
    }
    setResult(null);
    setVerifiedVoterId(null);
    setFingerprintResult(null);
    setBiometricResult(null);
    stopCamera();
    setVoterId(parsed.data);
    verify.mutate(parsed.data);
  };

  const onVoterIdChange = (value: string) => {
    setVoterId(value.toUpperCase());
    setResult(null);
    setVerifiedVoterId(null);
    setFingerprintResult(null);
    setBiometricResult(null);
    stopCamera();
  };

  const startCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setBiometricResult({ status: "failed", message: "Camera access is not supported in this browser." });
      return;
    }

    try {
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      setCameraActive(true);
      setBiometricResult(null);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unable to access camera.";
      setBiometricResult({ status: "failed", message });
    }
  };

  const captureFace = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0 || video.videoHeight === 0) {
      setBiometricResult({ status: "failed", message: "Camera preview is not ready. Please try again." });
      return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      setBiometricResult({ status: "failed", message: "Unable to capture camera frame." });
      return;
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const faceImage = canvas.toDataURL("image/jpeg", 0.8);
    stopCamera();
    biometric.mutate(faceImage);
  };

  const voterVerified = result?.status === "verified" && Boolean(verifiedVoterId);
  const fingerprintReady = fingerprintResult?.status === "ready";

  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Booth Terminal</h1>
          <p className="text-sm text-muted-foreground">Authenticate voters before biometric capture.</p>
        </div>
        <div className="rounded-md border border-primary/40 bg-primary/10 px-3 py-1.5">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Booth ID</div>
          <div className="font-mono text-lg font-bold text-primary">{boothId}</div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="space-y-4">
          <form
            onSubmit={onSubmit}
            className="rounded-lg border border-border bg-card p-5"
          >
            <label htmlFor="voter-id" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Voter ID
            </label>
            <div className="mt-2 flex gap-2">
              <Input
                id="voter-id"
                value={voterId}
                onChange={(e) => onVoterIdChange(e.target.value)}
                placeholder="e.g. ABC1234567"
                className="h-12 font-mono text-base tracking-wider"
                autoComplete="off"
                autoFocus
              />
              <Button type="submit" disabled={verify.isPending} className="h-12 gap-2 px-6">
                <Search className="h-4 w-4" />
                {verify.isPending ? "Verifying…" : "Verify"}
              </Button>
            </div>
          </form>

          <ResultCard result={result} boothId={boothId} />

          <FingerprintScanPanel
            enabled={voterVerified}
            pending={fingerprint.isPending}
            result={fingerprintResult}
            onScan={() => fingerprint.mutate()}
          />

          <FaceScanPanel
            enabled={voterVerified && fingerprintReady}
            active={cameraActive}
            pending={biometric.isPending}
            result={biometricResult}
            videoRef={videoRef}
            canvasRef={canvasRef}
            onStart={startCamera}
            onCapture={captureFace}
            onCancel={stopCamera}
          />
        </section>

        <aside className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">Live Activity</h2>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {feed.length} events
            </span>
          </div>
          <ul className="max-h-150 overflow-y-auto divide-y divide-border">
            {feed.length === 0 && (
              <li className="px-4 py-6 text-center text-xs text-muted-foreground">
                Awaiting authentication events…
              </li>
            )}
            {feed.map((item, i) => (
              <li key={i} className="px-4 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs">{maskFeedVoterId(item.voter_id)}</span>
                  <StatusChip status={item.status} />
                </div>
                {item.fraud_type && <div className="mt-1 text-xs font-medium text-destructive">{item.fraud_type}</div>}
                <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                  {item.booth_id} · {safeTime(item.timestamp)}
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </main>
  );
}

function FingerprintScanPanel({
  enabled,
  pending,
  result,
  onScan,
}: {
  enabled: boolean;
  pending: boolean;
  result: FingerprintResponse | null;
  onScan: () => void;
}) {
  const statusStyles = {
    ready: "border-l-[oklch(0.68_0.17_145)] bg-[oklch(0.68_0.17_145/0.08)] text-[oklch(0.85_0.17_145)]",
    fraud_detected: "border-l-destructive bg-destructive/10 text-destructive",
    failed: "border-l-[oklch(0.78_0.16_85)] bg-[oklch(0.78_0.16_85/0.12)] text-[oklch(0.9_0.13_85)]",
  } satisfies Record<FingerprintResponse["status"], string>;

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
            <Fingerprint className="h-5 w-5" />
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-primary">Step 1</div>
            <h2 className="text-sm font-semibold">Fingerprint Scan</h2>
          </div>
        </div>
        <Button type="button" disabled={!enabled || pending} onClick={onScan} className="gap-2">
          <Fingerprint className="h-4 w-4" />
          {pending ? "Scanning..." : result?.status === "failed" ? "Retry Fingerprint" : "Scan Fingerprint"}
        </Button>
      </div>

      {!enabled && (
        <p className="mt-3 text-xs text-muted-foreground">
          Verify a voter ID before scanning fingerprint.
        </p>
      )}

      {pending && (
        <div className="mt-4 rounded-lg border border-border border-l-4 border-l-primary bg-primary/10 p-4 text-primary">
          <div className="flex items-start gap-3">
            <Fingerprint className="mt-0.5 h-5 w-5" />
            <div>
              <div className="font-semibold">Scanner Waiting</div>
              <p className="mt-1 text-xs text-muted-foreground">Place voter's finger on the scanner...</p>
            </div>
          </div>
        </div>
      )}

      {!pending && result && (
        <div className={`mt-4 rounded-lg border border-border border-l-4 p-4 ${statusStyles[result.status]}`}>
          <div className="flex items-start gap-3">
            {result.status === "ready" ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5" />
            ) : result.status === "fraud_detected" ? (
              <AlertTriangle className="mt-0.5 h-5 w-5" />
            ) : (
              <XCircle className="mt-0.5 h-5 w-5" />
            )}
            <div>
              <div className="font-semibold">
                {result.status === "ready"
                  ? "Fingerprint Captured"
                  : result.status === "fraud_detected"
                    ? "Fraud Detected"
                    : "Fingerprint Scan Failed"}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{result.message}</p>
              {result.fraud_type && (
                <p className="mt-2 font-mono text-[10px] uppercase tracking-wider">
                  {result.fraud_type}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function FaceScanPanel({
  enabled,
  active,
  pending,
  result,
  videoRef,
  canvasRef,
  onStart,
  onCapture,
  onCancel,
}: {
  enabled: boolean;
  active: boolean;
  pending: boolean;
  result: BiometricResponse | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  onStart: () => void;
  onCapture: () => void;
  onCancel: () => void;
}) {
  const statusStyles = {
    authenticated: "border-l-[oklch(0.68_0.17_145)] bg-[oklch(0.68_0.17_145/0.08)] text-[oklch(0.85_0.17_145)]",
    fraud_detected: "border-l-destructive bg-destructive/10 text-destructive",
    failed: "border-l-[oklch(0.78_0.16_85)] bg-[oklch(0.78_0.16_85/0.12)] text-[oklch(0.9_0.13_85)]",
  } satisfies Record<BiometricResponse["status"], string>;

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
            <ScanFace className="h-5 w-5" />
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-primary">Step 2</div>
            <h2 className="text-sm font-semibold">Face Scan</h2>
          </div>
        </div>
        {!active ? (
          <Button type="button" disabled={!enabled || pending} onClick={onStart} className="gap-2">
            <ScanFace className="h-4 w-4" />
            {pending ? "Processing..." : "Open Camera"}
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="button" onClick={onCapture}>
              Capture
            </Button>
          </div>
        )}
      </div>

      {active && (
        <div className="mt-4 overflow-hidden rounded-md border border-border bg-black">
          <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />
        </div>
      )}
      <canvas ref={canvasRef} className="hidden" />

      {!enabled && (
        <p className="mt-3 text-xs text-muted-foreground">
          Complete fingerprint scan before opening the camera.
        </p>
      )}

      {result && (
        <div className={`mt-4 rounded-lg border border-border border-l-4 p-4 ${statusStyles[result.status]}`}>
          <div className="flex items-start gap-3">
            {result.status === "authenticated" ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5" />
            ) : result.status === "fraud_detected" ? (
              <AlertTriangle className="mt-0.5 h-5 w-5" />
            ) : (
              <XCircle className="mt-0.5 h-5 w-5" />
            )}
            <div>
              <div className="font-semibold">
                {result.status === "authenticated"
                  ? "Face Authenticated"
                  : result.status === "fraud_detected"
                    ? "Fraud Detected"
                    : "Face Scan Failed"}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{result.message}</p>
              {result.fraud_type && (
                <p className="mt-2 font-mono text-[10px] uppercase tracking-wider">
                  {result.fraud_type}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ResultCard({ result, boothId }: { result: VerifyResponse | null; boothId: string }) {
  if (!result) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card/50 px-5 py-10 text-center text-sm text-muted-foreground">
        Enter a Voter ID and press Verify to begin.
      </div>
    );
  }
  if (result.status === "verified") {
    return (
      <div className="rounded-lg border-l-4 border-l-[oklch(0.68_0.17_145)] border border-border bg-[oklch(0.68_0.17_145/0.08)] p-5">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-6 w-6 text-[oklch(0.78_0.17_145)]" />
          <div className="flex-1">
            <div className="font-semibold text-[oklch(0.85_0.17_145)]">Voter Verified — Proceed to Biometric Scan</div>
            <dl className="mt-3 grid grid-cols-3 gap-3 text-xs">
              <Field label="Name" value={result.voter_name ?? "—"} />
              <Field label="Constituency" value={result.constituency ?? "—"} />
              <Field label="Booth" value={boothId} mono />
            </dl>
          </div>
        </div>
      </div>
    );
  }
  if (result.status === "duplicate") {
    return (
      <div className="rounded-lg border-l-4 border-l-destructive border border-border bg-destructive/10 p-5 animate-in fade-in">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-6 w-6 text-destructive" />
          <div className="flex-1">
            <div className="font-semibold text-destructive">Already Voted — Duplicate Attempt Blocked</div>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
              <Field label="Name" value={result.voter_name ?? "—"} />
              <Field label="Previous Vote" value={safeTime(result.timestamp) ?? "—"} mono />
            </dl>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="rounded-lg border-l-4 border-l-destructive border border-border bg-destructive/10 p-5 animate-in fade-in">
      <div className="flex items-start gap-3">
        <XCircle className="mt-0.5 h-6 w-6 text-destructive" />
        <div>
          <div className="font-semibold text-destructive">Voter ID Not Found — Not in Registry</div>
          <p className="mt-1 text-xs text-muted-foreground">{result.message}</p>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className={`mt-0.5 font-medium ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const s = status.toLowerCase();
  const cls = s === "authenticated" || s.includes("verif") || s === "ok"
    ? "bg-[oklch(0.68_0.17_145/0.15)] text-[oklch(0.82_0.17_145)]"
    : "bg-destructive/15 text-destructive";
  return (
    <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${cls}`}>
      {status}
    </span>
  );
}

function maskFeedVoterId(id: string) {
  return id.length <= 6 ? id : `${id.slice(0, 3)}••••${id.slice(-3)}`;
}

function maskVoterId(id: string) {
  if (id.length <= 4) return id;
  return `${id.slice(0, 3)}••••${id.slice(-3)}`;
}

function safeTime(ts?: string) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return format(d, "HH:mm:ss");
}

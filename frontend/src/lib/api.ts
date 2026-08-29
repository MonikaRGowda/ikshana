const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export type VerifyStatus = "verified" | "duplicate" | "not_found";

export interface VerifyResponse {
  status: VerifyStatus;
  message: string;
  voter_name?: string;
  constituency?: string;
  timestamp?: string;
}

export type BiometricStatus = "authenticated" | "fraud_detected" | "failed";
export type FingerprintStatus = "ready" | "fraud_detected" | "failed";

export interface FingerprintResponse {
  status: FingerprintStatus;
  message: string;
  voter_name?: string;
  fraud_type?: string;
}

export interface BiometricResponse {
  status: BiometricStatus;
  message: string;
  voter_name?: string;
  fraud_type?: string;
}

export interface ElectionStatus {
  name: string;
  status: "active" | "ended";
  total_votes: number;
  active_booths: number;
}

export type FraudType = "duplicate_voting" | "identity_fraud" | "voter_id_forgery" | string;

export interface AuditEntry {
  timestamp: string;
  voter_id: string;
  booth_id: string;
  status: string;
  fraud_type?: FraudType | null;
  details?: string;
}

export const api = {
  verifyVoter: (voter_id: string, booth_id: string, session_token: string) =>
    req<VerifyResponse>("/api/verify-voter", {
      method: "POST",
      headers: { Authorization: `Bearer ${session_token}` },
      body: JSON.stringify({ voter_id, booth_id, session_token }),
    }),
  verifyBiometric: (voter_id: string, booth_id: string, session_token: string, face_image: string) =>
    req<BiometricResponse>("/api/biometric/verify", {
      method: "POST",
      headers: { Authorization: `Bearer ${session_token}` },
      body: JSON.stringify({ voter_id, booth_id, session_token, face_image }),
    }),
  scanFingerprint: (voter_id: string, booth_id: string, session_token: string) =>
    req<FingerprintResponse>("/api/biometric/fingerprint", {
      method: "POST",
      headers: { Authorization: `Bearer ${session_token}` },
      body: JSON.stringify({ voter_id, booth_id, session_token }),
    }),
  electionStatus: () => req<ElectionStatus>("/api/election/status"),
  auditLog: () => req<AuditEntry[]>("/api/audit-log"),
  startElection: () => req<{ ok: boolean }>("/api/election/start", { method: "POST" }),
  endElection: () => req<{ ok: boolean }>("/api/election/end", { method: "POST" }),
  boothLogin: (officer_id: string, password: string) =>
    req<LoginResponse>("/api/booth/login", {
      method: "POST",
      body: JSON.stringify({ officer_id, password }),
    }),
};

export interface LoginResponse {
  status: string;
  message: string;
  officer_name: string;
  designation: string;
  assigned_booth: string;
  session_token: string;
}

export const SESSION_KEYS = {
  token: "ikshana.session_token",
  booth: "ikshana.assigned_booth",
  officer: "ikshana.officer_name",
} as const;

export const API_BASE = BASE;

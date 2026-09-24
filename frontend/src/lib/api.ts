const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
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

export type ElectionActionStatus =
  | "ok"
  | "otp_required"
  | "invalid_confirmation"
  | "invalid_password"
  | "invalid_otp"
  | "not_active"
  | "error";

export interface ElectionActionResponse {
  status: ElectionActionStatus;
  message: string;
}

export interface StartElectionRequest {
  password?: string;
  reason?: string;
  otp_code?: string;
}

export interface EndElectionRequest {
  password: string;
  reason: string;
  confirmation_text: string;
  otp_code?: string;
}

export type FraudType = "duplicate_voting" | "identity_fraud" | "voter_id_forgery" | string;

export type AdminLoginStatus =
  | "otp_sent"
  | "invalid_credentials"
  | "locked"
  | "account_disabled"
  | "no_email";

export interface AdminLoginResponse {
  status: AdminLoginStatus;
  message: string;
}

export type AdminVerifyOtpStatus = "ok" | "invalid" | "expired";

export interface AdminVerifyOtpResponse {
  status: AdminVerifyOtpStatus;
  message?: string;
  officer_name?: string;
  role?: "RO" | "CEO";
  constituency?: string | null;
}

export interface LoginResponse {
  status: string;
  message: string;
  officer_name: string;
  designation: string;
  assigned_booth: string;
  session_token: string;
}

export interface AdminROOverviewResponse {
  constituency: string;
  total_voters: number;
  voters_authenticated: number;
  active_booths: number;
  total_booths: number;
}

export interface AdminROFraudEntry {
  id: number;
  timestamp: string;
  voter_id: string;
  booth_id: string;
  fraud_type?: FraudType | null;
  details?: string | null;
  evidence_photo_url?: string | null;
  original_vote?: {
    booth_id: string;
    timestamp: string;
  } | null;
  match_score?: number | null;
  match_metric?: "fingerprint_score" | "face_distance" | null;
  review_status?: "confirmed" | "false_positive" | null;
}

export interface AdminROBoothInfo {
  booth_id: string;
  status: "active" | "inactive";
  officer_name?: string | null;
}

export interface AdminCEOOverviewResponse {
  total_voters: number;
  voters_authenticated: number;
  active_booths: number;
  total_booths: number;
}

export interface AccuracySummaryResponse {
  scope: "constituency" | "global";
  total_flagged: number;
  total_authenticated: number;
  detection_rate: number | null;
  reviewed_count: number;
  confirmed_count: number;
  false_positive_count: number;
  unreviewed_count: number;
  precision: number | null;
  avg_fingerprint_score: number | null;
  avg_face_distance: number | null;
}

export interface AdminCEOFraudEntry extends AdminROFraudEntry {}

export interface AdminCEOBoothInfo extends AdminROBoothInfo {
  constituency?: string | null;
}

export interface AdminCEOOfficer {
  officer_id: string;
  name: string;
  role: string;
  assigned_booth?: string | null;
  constituency?: string | null;
}

export interface RegisterOfficerRequest {
  officer_id: string;
  name: string;
  password: string;
  assigned_booth: string;
  constituency?: string;
}

export interface RegisterOfficerResponse {
  status: "ok" | "duplicate" | "error";
  message: string;
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
  startElection: (payload: StartElectionRequest) =>
    req<ElectionActionResponse>("/api/election/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  endElection: (payload: EndElectionRequest) =>
    req<ElectionActionResponse>("/api/election/end", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  boothLogin: (officer_id: string, password: string) =>
    req<LoginResponse>("/api/booth/login", {
      method: "POST",
      body: JSON.stringify({ officer_id, password }),
    }),
  adminLogin: (officer_id: string, password: string) =>
    req<AdminLoginResponse>("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ officer_id, password }),
    }),
  adminVerifyOtp: (officer_id: string, code: string) =>
    req<AdminVerifyOtpResponse>("/api/admin/verify-otp", {
      method: "POST",
      body: JSON.stringify({ officer_id, code }),
    }),
  adminLogout: () =>
    req<{ status: string }>("/api/admin/logout", { method: "POST" }),
  adminRoOverview: () => req<AdminROOverviewResponse>("/api/admin/ro/overview"),
  adminRoFraudLog: () => req<AdminROFraudEntry[]>("/api/admin/ro/fraud-log"),
  adminRoBooths: () => req<AdminROBoothInfo[]>("/api/admin/ro/booths"),
  adminReviewFraudLog: (id: number, status: "confirmed" | "false_positive", note?: string) =>
    req<{ status: string; message: string }>(`/api/admin/fraud-log/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    }),
  adminAccuracy: () => req<AccuracySummaryResponse>("/api/admin/accuracy"),
  adminCeoOverview: () => req<AdminCEOOverviewResponse>("/api/admin/ceo/overview"),
  adminCeoFraudLog: () => req<AdminCEOFraudEntry[]>("/api/admin/ceo/fraud-log"),
  adminCeoBooths: () => req<AdminCEOBoothInfo[]>("/api/admin/ceo/booths"),
  adminCeoOfficers: () => req<AdminCEOOfficer[]>("/api/admin/ceo/officers"),
  ceoRegisterOfficer: (payload: RegisterOfficerRequest) =>
    req<RegisterOfficerResponse>("/api/admin/ceo/officers/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const SESSION_KEYS = {
  token: "ikshana.session_token",
  booth: "ikshana.assigned_booth",
  officer: "ikshana.officer_name",
} as const;

export const API_BASE = BASE;
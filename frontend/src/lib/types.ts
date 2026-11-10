export type Confidence =
  | "verified"
  | "corroborated"
  | "weak"
  | "conflicting"
  | "unverified"
  | "leaver_attested"
  | "reviewer_asserted"
  | "unknown";

export interface Person {
  id: string;
  name: string;
  handle: string | null;
}

export interface Me {
  account: { id: string; kind: string };
  user: Person | null;
  people: Person[];
  projects: { id: string; name: string; is_demo: boolean; role: string }[];
}

export interface Member {
  user_id: string;
  name: string;
  handle: string | null;
  role: string;
  access_level: string;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  stage: string;
  warnings: string[];
  error: string | null;
  stats: Record<string, number>;
  created_at: string;
  finished_at: string | null;
}

export interface Overview {
  project: { id: string; name: string; description: string; is_demo: boolean; departing: string | null; incoming: string | null };
  me: { user_id: string; name: string; role: string; access_level: string };
  members: Member[];
  counts: Record<string, number>;
  steps: { key: string; label: string; done: boolean }[];
  latest_job: Job | null;
  handover: { versions: number; approved_version: number | null };
  ai: { configured: boolean; chain: string[] };
}

export interface Source {
  id: string;
  kind: string;
  filename: string;
  uri: string | null;
  access_label: string;
  status: string;
  error: string | null;
  unit_count: number;
  redactions: number;
  coverage: { skipped?: string[]; skipped_count?: number; storage_error?: string };
  created_at: string;
}

export interface Evidence {
  id: string;
  code: string;
  kind: string;
  source_id: string;
  source: string | null;
  author: string | null;
  date: string | null;
  location: Record<string, string | number>;
  access_label: string;
  source_type?: string | null;
  text: string;
}

export interface Citation {
  cited_code: string;
  quote: string;
  match: "exact" | "fuzzy" | "none" | "missing_evidence";
  match_score: number;
  start: number | null;
  end: number | null;
  evidence: Evidence | null;
  hidden: boolean;
  source?: string | null;
}

export interface Claim {
  id: string;
  code: string;
  type: string;
  subject: string;
  statement: string;
  original_statement: string;
  status: string | null;
  owner: string | null;
  owner_reassigned: boolean;
  rationale: string | null;
  confidence: Confidence;
  support: string | null;
  support_reason: string | null;
  review_state: "pending" | "approved" | "corrected" | "rejected" | "superseded";
  reviewer_note: string | null;
  leaver_note: string | null;
  access_label: string;
  extractor: string;
  gate1: "pass" | "fail";
  citation_count: number;
  citations: Citation[];
  reviews?: { action: string; reason: string | null; at: string }[];
  conflicts?: { id: string; status: string; explanation: string }[];
}

export interface Gap {
  id: string;
  kind: string;
  question: string;
  status: "open" | "answered" | "dismissed";
  answer: string | null;
  claim_id: string | null;
  conflict_id: string | null;
  answer_evidence_id: string | null;
  access_label: string;
}

export interface Conflict {
  id: string;
  kind: string;
  explanation: string;
  status: "open" | "resolved" | "kept";
  winner_claim_id: string | null;
  resolution_note: string | null;
  newer_side: "a" | "b" | null;
  side_a: Claim[];
  side_b: Claim[];
  claim_a: Claim | null;
  claim_b: Claim | null;
}

export interface HandoverEvidence {
  evidence_id: string;
  code: string;
  source: string;
  kind: string;
  author: string | null;
  date: string | null;
  location: Record<string, string | number>;
  quote: string;
  source_type?: string;
  match?: string;
  start?: number | null;
  end?: number | null;
  url?: string | null;
}

export interface HandoverItem {
  claim_id: string | null;
  code: string | null;
  type: string;
  text: string;
  status?: string | null;
  owner?: string | null;
  owner_reassigned?: boolean;
  rationale?: string | null;
  confidence: Confidence;
  leaver_note?: string | null;
  reviewer_note?: string | null;
  access_label?: string;
  open_gap?: string;
  action?: string;
  review_state?: string;
  evidence: HandoverEvidence[];
}

export interface Handover {
  id: string;
  version: number;
  status: "draft" | "approved" | "superseded";
  approved_at: string | null;
  approved_by: string | null;
  content: {
    project: string;
    departing: string | null;
    incoming: string | null;
    hidden_count: number;
    sections: { key: string; title: string; note?: string | null; items: HandoverItem[]; hidden_count: number }[];
  };
  viewer: { name: string; role: string; access_level: number };
  acknowledged: string[];
}

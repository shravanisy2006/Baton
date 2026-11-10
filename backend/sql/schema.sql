-- Baton database schema for Supabase Postgres.
-- The API also creates these tables automatically on first start (SQLAlchemy create_all).
-- Run this file in the Supabase SQL editor if you prefer to create them yourself.
--
-- Security model: the browser never talks to the database. All reads and writes go through the
-- Baton API, which checks project membership, role and access label (Team/Leads/Restricted) in every
-- query. Row-Level Security is switched ON for every table with NO policies, so Supabase's public
-- REST API (anon / authenticated keys) can read nothing. Only the API's database user can.

CREATE TABLE IF NOT EXISTS accounts (
	id VARCHAR(24) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	email VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS llm_cache (
	key VARCHAR(64) NOT NULL, 
	task VARCHAR(32) NOT NULL, 
	model VARCHAR(80) NOT NULL, 
	response JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
);

CREATE TABLE IF NOT EXISTS users (
	id VARCHAR(24) NOT NULL, 
	account_id VARCHAR(24) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	handle VARCHAR(120), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(account_id) REFERENCES accounts (id)
);
CREATE INDEX IF NOT EXISTS ix_users_account_id ON users (account_id);

CREATE TABLE IF NOT EXISTS projects (
	id VARCHAR(24) NOT NULL, 
	account_id VARCHAR(24) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	description TEXT NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	departing_user_id VARCHAR(24), 
	incoming_user_id VARCHAR(24), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(account_id) REFERENCES accounts (id), 
	FOREIGN KEY(departing_user_id) REFERENCES users (id), 
	FOREIGN KEY(incoming_user_id) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_projects_account_id ON projects (account_id);

CREATE TABLE IF NOT EXISTS audit_events (
	id SERIAL NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	actor_id VARCHAR(24), 
	actor_name VARCHAR(120) NOT NULL, 
	action VARCHAR(60) NOT NULL, 
	target_type VARCHAR(32), 
	target_id VARCHAR(24), 
	detail JSON NOT NULL, 
	at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_audit_events_project_id ON audit_events (project_id);

CREATE TABLE IF NOT EXISTS claims (
	id VARCHAR(24) NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	code VARCHAR(16) NOT NULL, 
	type VARCHAR(24) NOT NULL, 
	subject VARCHAR(200) NOT NULL, 
	statement TEXT NOT NULL, 
	original_statement TEXT NOT NULL, 
	status VARCHAR(24), 
	owner VARCHAR(160), 
	owner_reassigned BOOLEAN NOT NULL, 
	rationale TEXT, 
	confidence VARCHAR(24) NOT NULL, 
	support VARCHAR(16), 
	support_reason TEXT, 
	review_state VARCHAR(16) NOT NULL, 
	reviewer_note TEXT, 
	leaver_note TEXT, 
	leaver_evidence_id VARCHAR(24), 
	access_label INTEGER NOT NULL, 
	extractor VARCHAR(80) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_claims_project_id ON claims (project_id);

CREATE TABLE IF NOT EXISTS handover_versions (
	id VARCHAR(24) NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	version INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	snapshot JSON NOT NULL, 
	created_by VARCHAR(24), 
	approved_by VARCHAR(24), 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_handover_versions_project_id ON handover_versions (project_id);

CREATE TABLE IF NOT EXISTS jobs (
	id VARCHAR(24) NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	kind VARCHAR(24) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	stage VARCHAR(40) NOT NULL, 
	warnings JSON NOT NULL, 
	error TEXT, 
	stats JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_jobs_project_id ON jobs (project_id);

CREATE TABLE IF NOT EXISTS memberships (
	id SERIAL NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	user_id VARCHAR(24) NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	access_level INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (project_id, user_id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_memberships_project_id ON memberships (project_id);
CREATE INDEX IF NOT EXISTS ix_memberships_user_id ON memberships (user_id);

CREATE TABLE IF NOT EXISTS sources (
	id VARCHAR(24) NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	uri VARCHAR(500), 
	access_label INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	error TEXT, 
	unit_count INTEGER NOT NULL, 
	redactions INTEGER NOT NULL, 
	coverage JSON NOT NULL, 
	storage_path VARCHAR(500), 
	authorised_by VARCHAR(24), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(authorised_by) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_sources_project_id ON sources (project_id);

CREATE TABLE IF NOT EXISTS acknowledgements (
	id SERIAL NOT NULL, 
	version_id VARCHAR(24) NOT NULL, 
	user_id VARCHAR(24) NOT NULL, 
	section VARCHAR(40) NOT NULL, 
	at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (version_id, user_id, section), 
	FOREIGN KEY(version_id) REFERENCES handover_versions (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conflicts (
	id VARCHAR(24) NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	kind VARCHAR(24) NOT NULL, 
	claim_a_id VARCHAR(24) NOT NULL, 
	claim_b_id VARCHAR(24) NOT NULL, 
	explanation TEXT NOT NULL, 
	side_a JSON NOT NULL, 
	side_b JSON NOT NULL, 
	newer_side VARCHAR(1), 
	status VARCHAR(16) NOT NULL, 
	winner_claim_id VARCHAR(24), 
	resolution_note TEXT, 
	access_label INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(claim_a_id) REFERENCES claims (id) ON DELETE CASCADE, 
	FOREIGN KEY(claim_b_id) REFERENCES claims (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_conflicts_project_id ON conflicts (project_id);

CREATE TABLE IF NOT EXISTS evidence_units (
	id VARCHAR(24) NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	source_id VARCHAR(24) NOT NULL, 
	code VARCHAR(16) NOT NULL, 
	seq INTEGER NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	text TEXT NOT NULL, 
	text_hash VARCHAR(64) NOT NULL, 
	author VARCHAR(160), 
	occurred_at VARCHAR(40), 
	location JSON NOT NULL, 
	access_label INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_evidence_units_project_id ON evidence_units (project_id);
CREATE INDEX IF NOT EXISTS ix_evidence_units_source_id ON evidence_units (source_id);

CREATE TABLE IF NOT EXISTS gaps (
	id VARCHAR(24) NOT NULL, 
	project_id VARCHAR(24) NOT NULL, 
	claim_id VARCHAR(24), 
	conflict_id VARCHAR(24), 
	source_id VARCHAR(24), 
	kind VARCHAR(32) NOT NULL, 
	question TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	answer TEXT, 
	answer_evidence_id VARCHAR(24), 
	access_label INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(claim_id) REFERENCES claims (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_gaps_project_id ON gaps (project_id);

CREATE TABLE IF NOT EXISTS reviews (
	id SERIAL NOT NULL, 
	claim_id VARCHAR(24) NOT NULL, 
	reviewer_id VARCHAR(24) NOT NULL, 
	action VARCHAR(16) NOT NULL, 
	before JSON NOT NULL, 
	after JSON NOT NULL, 
	reason TEXT, 
	at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(claim_id) REFERENCES claims (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_reviews_claim_id ON reviews (claim_id);

CREATE TABLE IF NOT EXISTS claim_evidence (
	id SERIAL NOT NULL, 
	claim_id VARCHAR(24) NOT NULL, 
	evidence_id VARCHAR(24), 
	cited_code VARCHAR(16) NOT NULL, 
	quote TEXT NOT NULL, 
	start INTEGER, 
	"end" INTEGER, 
	match VARCHAR(16) NOT NULL, 
	match_score FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(claim_id) REFERENCES claims (id) ON DELETE CASCADE, 
	FOREIGN KEY(evidence_id) REFERENCES evidence_units (id)
);
CREATE INDEX IF NOT EXISTS ix_claim_evidence_claim_id ON claim_evidence (claim_id);

-- Row-Level Security: deny everything to the public Supabase roles.
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE handover_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE acknowledgements ENABLE ROW LEVEL SECURITY;
ALTER TABLE conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE gaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_evidence ENABLE ROW LEVEL SECURITY;

-- The audit log is append-only: nobody (except a superuser) may change or delete history.
REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC, anon, authenticated;

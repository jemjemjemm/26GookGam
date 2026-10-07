-- 운영 PostgreSQL용 기준 구조. 로컬 DB를 그대로 변환하는 migration이 아니라 목표 DDL이다.
-- 배포 관리자가 역할을 생성하고 접속 계정별로 GRANT한다. 실제 SSO/RLS 배포 검증은 별도.
CREATE SCHEMA IF NOT EXISTS radar;
CREATE TABLE radar.issues (
 id text PRIMARY KEY, name text NOT NULL, timezone text NOT NULL DEFAULT 'Asia/Seoul'
);
CREATE TABLE radar.sources (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, channel text NOT NULL,
 name text NOT NULL, access_mode text NOT NULL, rights_note text NOT NULL, expected_seconds integer NOT NULL,
 status text NOT NULL, last_success timestamptz, cursor jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE radar.documents (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, source_id text NOT NULL REFERENCES radar.sources,
 external_id text NOT NULL, canonical_url text, title text NOT NULL, published_at timestamptz,
 provided_at timestamptz, collected_at timestamptz NOT NULL, parent_id text REFERENCES radar.documents,
 content_scope text NOT NULL CHECK(content_scope IN ('full','snippet','title','transcript','comment')),
 is_demo boolean NOT NULL DEFAULT false, sample_method text NOT NULL,
 UNIQUE(source_id, external_id)
);
CREATE TABLE radar.document_versions (
 id text PRIMARY KEY, document_id text NOT NULL REFERENCES radar.documents, revision integer NOT NULL,
 content_hash text NOT NULL, body_object_uri text NOT NULL, observed_at timestamptz NOT NULL,
 redaction_version text NOT NULL, UNIQUE(document_id,revision)
);
CREATE TABLE radar.story_clusters (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, representative_version_id text NOT NULL REFERENCES radar.document_versions,
 method text NOT NULL, version text NOT NULL, approved_by text, created_at timestamptz NOT NULL
);
CREATE TABLE radar.cluster_members (
 cluster_id text NOT NULL REFERENCES radar.story_clusters, document_version_id text NOT NULL REFERENCES radar.document_versions,
 PRIMARY KEY(cluster_id,document_version_id)
);
CREATE TABLE radar.fact_registry (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, fact_version integer NOT NULL,
 statement text NOT NULL, procedural_status text NOT NULL, attribution text NOT NULL,
 source_uri text NOT NULL, source_hash text NOT NULL, locator text NOT NULL, evidence_quote text NOT NULL,
 verification text NOT NULL CHECK(verification IN ('pending','verified','superseded')),
 approved_by text, approved_at timestamptz, valid_from timestamptz NOT NULL, valid_to timestamptz,
 CHECK(verification!='verified' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL AND length(evidence_quote)>0))
);
CREATE TABLE radar.analysis_runs (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, document_version_id text NOT NULL REFERENCES radar.document_versions,
 model text NOT NULL, model_version text NOT NULL, prompt_version text NOT NULL, dictionary_version text NOT NULL,
 fact_version integer NOT NULL, output jsonb NOT NULL, confidence real NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 status text NOT NULL CHECK(status IN ('pending','approved','rejected')), reviewed_by text, reviewed_at timestamptz,
 created_at timestamptz NOT NULL,
 UNIQUE(document_version_id,model_version,prompt_version,dictionary_version,fact_version)
);
CREATE TABLE radar.frame_tags (
 analysis_id text NOT NULL REFERENCES radar.analysis_runs, code text NOT NULL, is_primary boolean NOT NULL,
 strength real NOT NULL CHECK(strength BETWEEN 0 AND 1), evidence jsonb NOT NULL, PRIMARY KEY(analysis_id,code)
);
CREATE UNIQUE INDEX one_primary_frame ON radar.frame_tags(analysis_id) WHERE is_primary;
CREATE TABLE radar.entity_mentions (
 analysis_id text NOT NULL REFERENCES radar.analysis_runs, entity_key text NOT NULL, entity_type text NOT NULL,
 flags jsonb NOT NULL, attribution text, evidence jsonb NOT NULL, PRIMARY KEY(analysis_id,entity_key)
);
CREATE TABLE radar.narratives (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, label text NOT NULL,
 argument_code text NOT NULL, target_type text NOT NULL, is_candidate boolean NOT NULL, version text NOT NULL
);
CREATE TABLE radar.narrative_members (
 narrative_id text NOT NULL REFERENCES radar.narratives, analysis_id text NOT NULL REFERENCES radar.analysis_runs,
 is_primary boolean NOT NULL, PRIMARY KEY(narrative_id,analysis_id)
);
CREATE TABLE radar.broadcast_segments (
 id text PRIMARY KEY, document_version_id text NOT NULL REFERENCES radar.document_versions,
 speaker_type text NOT NULL, start_ms integer, end_ms integer, transcription_method text NOT NULL,
 asr_confidence real, output jsonb NOT NULL, CHECK(end_ms IS NULL OR start_ms<=end_ms)
);
CREATE TABLE radar.amplifications (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, document_id text NOT NULL REFERENCES radar.documents,
 kind text NOT NULL, observed_at timestamptz NOT NULL, ended_at timestamptz,
 evidence_uri text NOT NULL, verified_by text, context jsonb NOT NULL, duration_basis text NOT NULL
);
CREATE TABLE radar.jobs (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, idempotency_key text NOT NULL UNIQUE,
 kind text NOT NULL, payload jsonb NOT NULL, state text NOT NULL, attempts integer NOT NULL DEFAULT 0,
 available_at timestamptz NOT NULL, lease_until timestamptz, error_code text
);
CREATE TABLE radar.metric_snapshots (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, cutoff_at timestamptz NOT NULL,
 window_seconds integer NOT NULL, formula_version text NOT NULL, payload jsonb NOT NULL,
 filters jsonb NOT NULL, data_quality jsonb NOT NULL, created_at timestamptz NOT NULL
);
CREATE TABLE radar.alerts (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, dedupe_key text NOT NULL UNIQUE,
 rule_version text NOT NULL, severity text NOT NULL, state text NOT NULL, snapshot_id text REFERENCES radar.metric_snapshots,
 payload jsonb NOT NULL, assignee text, acknowledged_by text, acknowledged_at timestamptz, resolved_at timestamptz
);
CREATE TABLE radar.reports (
 id text PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues, scheduled_at timestamptz NOT NULL,
 revision integer NOT NULL DEFAULT 1, snapshot_id text NOT NULL REFERENCES radar.metric_snapshots,
 status text NOT NULL CHECK(status IN ('draft','approved','sent','corrected')), body text NOT NULL,
 approved_by text, approved_at timestamptz, sent_at timestamptz, UNIQUE(issue_id,scheduled_at,revision)
);
CREATE TABLE radar.collection_runs (
 id text PRIMARY KEY, source_id text NOT NULL REFERENCES radar.sources, started_at timestamptz NOT NULL,
 finished_at timestamptz, status text NOT NULL, counts jsonb NOT NULL, cursor jsonb, error_code text
);
CREATE TABLE radar.audit_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, issue_id text NOT NULL REFERENCES radar.issues,
 actor text NOT NULL, action text NOT NULL, object_id text NOT NULL, before_after jsonb NOT NULL, created_at timestamptz NOT NULL
);
CREATE INDEX documents_issue_time ON radar.documents(issue_id,published_at DESC);
CREATE INDEX versions_doc_time ON radar.document_versions(document_id,observed_at DESC);
CREATE INDEX jobs_ready ON radar.jobs(state,available_at);
CREATE INDEX analysis_doc_time ON radar.analysis_runs(document_version_id,created_at DESC);
CREATE INDEX amplification_time ON radar.amplifications(issue_id,observed_at DESC);
CREATE INDEX output_search ON radar.analysis_runs USING gin(output);

-- 관리자가 실행하는 권한 템플릿. role 생성 권한이 필요하다.
CREATE ROLE radar_reader NOLOGIN;
CREATE ROLE radar_collector NOLOGIN;
CREATE ROLE radar_analyzer NOLOGIN;
CREATE ROLE radar_fact_approver NOLOGIN;
CREATE ROLE radar_reporter NOLOGIN;
GRANT USAGE ON SCHEMA radar TO radar_reader,radar_collector,radar_analyzer,radar_fact_approver,radar_reporter;
GRANT SELECT ON ALL TABLES IN SCHEMA radar TO radar_reader;
GRANT SELECT ON radar.documents,radar.document_versions,radar.sources TO radar_collector;
GRANT INSERT ON radar.documents,radar.document_versions,radar.collection_runs TO radar_collector;
GRANT UPDATE ON radar.sources TO radar_collector;
GRANT SELECT ON radar.documents,radar.document_versions,radar.fact_registry TO radar_analyzer;
GRANT INSERT ON radar.analysis_runs,radar.frame_tags,radar.entity_mentions,radar.broadcast_segments TO radar_analyzer;
REVOKE INSERT,UPDATE,DELETE ON radar.fact_registry FROM radar_analyzer,radar_collector,radar_reporter,radar_reader;
GRANT SELECT,INSERT,UPDATE ON radar.fact_registry TO radar_fact_approver;
GRANT SELECT ON ALL TABLES IN SCHEMA radar TO radar_reporter;
GRANT INSERT ON radar.metric_snapshots,radar.alerts,radar.reports TO radar_reporter;
-- 운영 RLS: API 인증 이후 SET LOCAL app.issue_id를 서버가 설정한다. 클라이언트 직접 지정 금지.
ALTER TABLE radar.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE radar.documents FORCE ROW LEVEL SECURITY;
CREATE POLICY issue_documents ON radar.documents USING (issue_id=current_setting('app.issue_id',true));
ALTER TABLE radar.fact_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE radar.fact_registry FORCE ROW LEVEL SECURITY;
CREATE POLICY issue_facts ON radar.fact_registry USING (issue_id=current_setting('app.issue_id',true));
-- 나머지 issue 테이블과 child join 기반 RLS도 운영 배포 전에 적용해야 한다.
-- 현 파일은 전체 RLS/SSO 완성본이 아니며 계정 관리·migration·backup 검증 후 사용한다.

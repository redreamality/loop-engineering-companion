CREATE TABLE maturity_evidence (
    evidence_id     text PRIMARY KEY,
    loop_id         text NOT NULL,
    review_id       text NOT NULL,
    dimension       text NOT NULL CHECK (dimension IN ('A','B','C','D','E','F','G','H')),
    claimed_level   smallint NOT NULL CHECK (claimed_level BETWEEN 0 AND 4),
    evidence_type   text NOT NULL CHECK (
        evidence_type IN ('declaration','config','test','production')
    ),
    evidence_uri    text NOT NULL,
    observed_at     timestamptz NOT NULL,
    valid_until     timestamptz,
    system_version  text NOT NULL,
    reviewer        text NOT NULL,
    status          text NOT NULL CHECK (status IN ('pending','accepted','rejected'))
);

CREATE INDEX maturity_evidence_review
    ON maturity_evidence (loop_id, review_id, system_version, dimension);

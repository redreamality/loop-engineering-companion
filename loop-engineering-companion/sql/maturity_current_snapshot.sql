WITH target (loop_id, review_id, system_version) AS (
    VALUES (%s::text, %s::text, %s::text)
)
SELECT
    evidence.loop_id,
    evidence.review_id,
    evidence.system_version,
    evidence.dimension,
    MAX(evidence.claimed_level) FILTER (
        WHERE evidence.status = 'accepted'
          AND (evidence.valid_until IS NULL
               OR evidence.valid_until >= CURRENT_TIMESTAMP)
    ) AS highest_live_claim,
    COUNT(*) FILTER (
        WHERE evidence.status = 'accepted'
          AND (evidence.valid_until IS NULL
               OR evidence.valid_until >= CURRENT_TIMESTAMP)
    ) AS live_evidence_count,
    COUNT(*) FILTER (
        WHERE evidence.status = 'accepted'
          AND evidence.valid_until < CURRENT_TIMESTAMP
    ) AS expired_evidence_count,
    MIN(evidence.valid_until) FILTER (
        WHERE evidence.status = 'accepted'
          AND evidence.valid_until >= CURRENT_TIMESTAMP
    ) AS next_expiry
FROM maturity_evidence AS evidence
JOIN target
  ON evidence.loop_id = target.loop_id
 AND evidence.review_id = target.review_id
 AND evidence.system_version = target.system_version
GROUP BY
    evidence.loop_id,
    evidence.review_id,
    evidence.system_version,
    evidence.dimension
ORDER BY evidence.dimension;

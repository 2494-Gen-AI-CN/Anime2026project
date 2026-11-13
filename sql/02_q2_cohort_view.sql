-- 02_q2_cohort_view.sql
-- Analysis cohort for Question 2: finished, rated, multi-episode TV series.
--
-- The dataset has no per-episode viewing data, so "abandonment before the finale" is proxied:
--   completion_proxy  = scored_by / members   (share of the audience that stuck around to rate)
--   abandonment_proxy = 1 - completion_proxy
-- Audience volume  = members          Viewer satisfaction = score

CREATE OR REPLACE VIEW `{project}.{dataset}.vw_q2_cohort` AS
WITH base AS (
  SELECT
    a.anime_id, a.name, a.episodes, a.score, a.members, a.scored_by,
    1 - SAFE_DIVIDE(a.scored_by, a.members) AS abandonment_proxy
  FROM `{project}.{dataset}.dim_anime` AS a
  WHERE a.type = 'TV'
    AND a.status = 'Finished Airing'          -- a finale actually exists
    AND a.episodes >= 8                        -- exclude shorts / one-offs
    AND a.score IS NOT NULL
    AND a.scored_by >= 1000                    -- enough raters for a stable score
    AND a.members > 0
    -- dim_genre joins on title, so drop the few names that are not unique
    AND a.name IN (SELECT name FROM `{project}.{dataset}.dim_anime` GROUP BY name HAVING COUNT(*) = 1)
)
SELECT
  *,
  NTILE(5)      OVER (ORDER BY members)           AS audience_tier,   -- 1 = smallest, 5 = largest
  PERCENT_RANK() OVER (ORDER BY members)           AS pr_members,
  PERCENT_RANK() OVER (ORDER BY score)             AS pr_score,
  PERCENT_RANK() OVER (ORDER BY abandonment_proxy) AS pr_abandon
FROM base;

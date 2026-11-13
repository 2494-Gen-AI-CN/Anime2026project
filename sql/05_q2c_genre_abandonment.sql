-- Part B: which genres lose the most viewers before the finale?
-- size_adj_abandonment = title abandonment minus the average for its audience-size tier,
-- so niche genres are not penalised/rewarded just for having smaller audiences.
-- hype_gap = percentile of audience size minus percentile of score (positive = more hype than praise).
WITH tier_avg AS (
  SELECT audience_tier, AVG(abandonment_proxy) AS tier_abandonment
  FROM `{project}.{dataset}.vw_q2_cohort`
  GROUP BY audience_tier
),
genre_titles AS (
  SELECT
    g.genre_name,
    c.anime_id, c.score, c.abandonment_proxy,
    c.abandonment_proxy - t.tier_abandonment AS size_adj_abandonment,
    c.pr_members - c.pr_score                AS hype_gap
  FROM `{project}.{dataset}.vw_q2_cohort` AS c
  JOIN `{project}.{dataset}.dim_genre`    AS g ON g.title = c.name       -- star-schema join
  JOIN tier_avg                           AS t USING (audience_tier)
)
SELECT
  genre_name,
  COUNT(DISTINCT anime_id)                                   AS n_titles,
  ROUND(AVG(score), 2)                                       AS avg_score,
  ROUND(APPROX_QUANTILES(abandonment_proxy, 100)[OFFSET(50)], 3) AS median_abandonment,
  ROUND(AVG(size_adj_abandonment), 3)                        AS size_adj_abandonment,
  ROUND(AVG(hype_gap), 3)                                    AS hype_gap
FROM genre_titles
GROUP BY genre_name
HAVING COUNT(DISTINCT anime_id) >= 30
ORDER BY median_abandonment DESC;

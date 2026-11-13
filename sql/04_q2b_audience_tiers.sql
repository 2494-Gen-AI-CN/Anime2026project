-- Part A (detail): satisfaction and abandonment by audience-size quintile
SELECT
  audience_tier,
  COUNT(*)                                           AS n_titles,
  MIN(members)                                       AS min_members,
  APPROX_QUANTILES(members, 2)[OFFSET(1)]            AS median_members,
  ROUND(AVG(score), 2)                               AS avg_score,
  ROUND(AVG(abandonment_proxy), 3)                   AS avg_abandonment
FROM `{project}.{dataset}.vw_q2_cohort`
GROUP BY audience_tier
ORDER BY audience_tier;

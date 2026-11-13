-- Part A: how strongly does audience volume correlate with satisfaction?
-- CORR on percent-ranks approximates Spearman (robust to the heavy skew in members).
SELECT
  COUNT(*)                                          AS n_titles,
  ROUND(CORR(LOG10(members), score), 3)             AS pearson_log_members_vs_score,
  ROUND(CORR(pr_members, pr_score), 3)              AS spearman_members_vs_score,
  ROUND(CORR(pr_members, pr_abandon), 3)            AS spearman_members_vs_abandonment,
  ROUND(CORR(pr_score,   pr_abandon), 3)            AS spearman_score_vs_abandonment
FROM `{project}.{dataset}.vw_q2_cohort`;

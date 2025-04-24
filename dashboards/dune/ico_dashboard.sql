-- SolanaGuard: Token ICO Analysis Dashboard
-- This query provides analytics for token launches and ICOs on Solana

-- Identify recent token launches (past 90 days)
WITH recent_token_launches AS (
  SELECT
    tk.mint,
    tk.symbol,
    tk.name,
    tk.decimals,
    MIN(tx.block_time) AS launch_time,
    mc.creator AS creator_address
  FROM solana.tokens tk
  JOIN solana.token_metadata mc ON tk.mint = mc.mint
  JOIN solana.transactions tx ON tx.tx_id = mc.tx_id
  WHERE tx.block_time >= NOW() - INTERVAL '90 days'
    AND tk.symbol IS NOT NULL
    AND tk.name IS NOT NULL
  GROUP BY tk.mint, tk.symbol, tk.name, tk.decimals, mc.creator
),

-- Initial transfers after token creation (first 24 hours)
initial_transfers AS (
  SELECT
    rtl.mint,
    rtl.symbol,
    COUNT(DISTINCT tr.tx_id) AS transfer_count,
    COUNT(DISTINCT tr.to_account) AS recipient_count,
    SUM(tr.amount / POWER(10, rtl.decimals)) AS total_tokens_transferred,
    MAX(tr.amount / POWER(10, rtl.decimals)) AS largest_transfer,
    MIN(tr.block_time) AS first_transfer_time,
    MAX(tr.block_time) AS last_transfer_time
  FROM recent_token_launches rtl
  JOIN solana.transfers tr ON rtl.mint = tr.mint
  WHERE tr.block_time BETWEEN rtl.launch_time AND rtl.launch_time + INTERVAL '24 hours'
  GROUP BY rtl.mint, rtl.symbol
),

-- Token distribution metrics
token_distribution AS (
  WITH holder_balances AS (
    SELECT
      ta.mint,
      ta.owner,
      ta.amount,
      tk.decimals
    FROM solana.token_accounts ta
    JOIN solana.tokens tk ON ta.mint = tk.mint
    WHERE ta.mint IN (SELECT mint FROM recent_token_launches)
      AND ta.amount > 0
  )
  
  SELECT
    mint,
    COUNT(DISTINCT owner) AS holder_count,
    SUM(amount / POWER(10, decimals)) AS total_supply,
    MAX(amount / POWER(10, decimals)) AS largest_holder_balance,
    MIN(amount / POWER(10, decimals)) AS smallest_holder_balance,
    AVG(amount / POWER(10, decimals)) AS average_balance,
    -- Concentration metrics
    MAX(amount / POWER(10, decimals)) / NULLIF(SUM(amount / POWER(10, decimals)), 0) * 100 AS top_holder_percentage,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY amount / POWER(10, decimals) DESC) AS top_10pct_threshold
  FROM holder_balances
  GROUP BY mint
),

-- Liquidity pair creation events
liquidity_pairs AS (
  -- This is a simplified approximation - would be enhanced with actual DEX data
  SELECT
    tr.mint AS token_mint,
    tr.tx_id,
    tr.from_account,
    tr.to_account,
    tr.block_time,
    CASE
      WHEN i.account_keys[i.program_index] = 'dexV4KQtEzJgJBLWJy5vLnGQ9Z1DJhuPbXsNKJek5wC' THEN 'Serum'
      WHEN i.account_keys[i.program_index] = 'RaydiumPoolMake1111111111111111111111111' THEN 'Raydium'
      WHEN i.account_keys[i.program_index] = 'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc' THEN 'Orca'
      ELSE 'Other DEX'
    END AS dex_platform,
    tr.amount / POWER(10, tk.decimals) AS token_amount
  FROM solana.transfers tr
  JOIN recent_token_launches rtl ON tr.mint = rtl.mint
  JOIN solana.tokens tk ON tr.mint = tk.mint
  JOIN solana.instructions i ON tr.tx_id = i.tx_id
  WHERE tr.block_time BETWEEN rtl.launch_time AND rtl.launch_time + INTERVAL '7 days'
    AND (
      i.account_keys[i.program_index] = 'dexV4KQtEzJgJBLWJy5vLnGQ9Z1DJhuPbXsNKJek5wC' OR -- Serum
      i.account_keys[i.program_index] = 'RaydiumPoolMake1111111111111111111111111' OR -- Raydium
      i.account_keys[i.program_index] = 'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc' -- Orca
    )
),

-- Price history (simplified approximation)
token_price_history AS (
  WITH price_events AS (
    -- Serum trades as price indicators
    SELECT
      tx.block_time,
      tr.mint,
      tr.amount / POWER(10, tk.decimals) AS token_amount,
      -- This is a simplification, actual price would be derived from paired asset
      tx.fee / (tr.amount / POWER(10, tk.decimals)) AS estimated_price,
      'trade' AS event_type
    FROM solana.transfers tr
    JOIN solana.transactions tx ON tr.tx_id = tx.tx_id
    JOIN solana.tokens tk ON tr.mint = tk.mint
    JOIN solana.instructions i ON tr.tx_id = i.tx_id
    WHERE 
      tr.mint IN (SELECT mint FROM recent_token_launches)
      AND i.account_keys[i.program_index] = 'dexV4KQtEzJgJBLWJy5vLnGQ9Z1DJhuPbXsNKJek5wC' -- Serum DEX
  )
  
  SELECT
    mint,
    DATE_TRUNC('day', block_time) AS day,
    AVG(estimated_price) AS avg_price,
    MIN(estimated_price) AS low_price,
    MAX(estimated_price) AS high_price,
    FIRST_VALUE(estimated_price) OVER (PARTITION BY mint, DATE_TRUNC('day', block_time) ORDER BY block_time) AS open_price,
    LAST_VALUE(estimated_price) OVER (PARTITION BY mint, DATE_TRUNC('day', block_time) ORDER BY block_time ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close_price,
    SUM(token_amount) AS volume
  FROM price_events
  GROUP BY mint, DATE_TRUNC('day', block_time)
),

-- Creator wallet activity
creator_activity AS (
  SELECT
    rtl.creator_address,
    COUNT(DISTINCT tx.tx_id) AS transaction_count,
    COUNT(DISTINCT tk.mint) AS tokens_created,
    MIN(tx.block_time) AS first_activity,
    MAX(tx.block_time) AS last_activity
  FROM recent_token_launches rtl
  JOIN solana.transactions tx ON tx.signer = rtl.creator_address
  LEFT JOIN solana.token_metadata mc ON tx.tx_id = mc.tx_id
  LEFT JOIN solana.tokens tk ON mc.mint = tk.mint
  GROUP BY rtl.creator_address
),

-- Detect insider trading patterns
insider_patterns AS (
  -- Large buys just before significant price increases
  WITH price_jumps AS (
    SELECT
      t1.mint,
      t1.day AS before_day,
      t2.day AS jump_day,
      t1.close_price AS before_price,
      t2.close_price AS after_price,
      (t2.close_price - t1.close_price) / NULLIF(t1.close_price, 0) * 100 AS price_change_pct
    FROM token_price_history t1
    JOIN token_price_history t2 ON 
      t1.mint = t2.mint AND
      t2.day = t1.day + INTERVAL '1 day'
    WHERE (t2.close_price - t1.close_price) / NULLIF(t1.close_price, 0) * 100 > 30 -- 30% price jump
  )
  
  SELECT
    pj.mint,
    tk.symbol,
    tr.from_account,
    tr.to_account,
    tr.amount / POWER(10, tk.decimals) AS token_amount,
    tr.block_time,
    pj.before_day,
    pj.jump_day,
    pj.before_price,
    pj.after_price,
    pj.price_change_pct
  FROM price_jumps pj
  JOIN solana.transfers tr ON pj.mint = tr.mint
  JOIN solana.tokens tk ON tr.mint = tk.mint
  WHERE tr.block_time BETWEEN pj.before_day - INTERVAL '12 hours' AND pj.before_day + INTERVAL '12 hours'
  ORDER BY tr.amount DESC
  LIMIT 100
),

-- Token launch success metrics
launch_success_metrics AS (
  SELECT
    rtl.mint,
    rtl.symbol,
    rtl.name,
    rtl.launch_time,
    td.holder_count,
    td.total_supply,
    td.top_holder_percentage,
    COALESCE(it.transfer_count, 0) AS first_day_transfers,
    COALESCE(it.recipient_count, 0) AS first_day_recipients,
    -- Success score based on multiple factors
    (
      CASE WHEN td.holder_count > 100 THEN 30 ELSE td.holder_count * 0.3 END +
      CASE WHEN td.top_holder_percentage < 50 THEN 30 ELSE (100 - td.top_holder_percentage) * 0.6 END +
      CASE WHEN it.recipient_count > 50 THEN 20 ELSE it.recipient_count * 0.4 END +
      CASE WHEN EXISTS (SELECT 1 FROM liquidity_pairs lp WHERE lp.token_mint = rtl.mint) THEN 20 ELSE 0 END
    ) AS success_score,
    -- Liquidity stats
    EXISTS(SELECT 1 FROM liquidity_pairs lp WHERE lp.token_mint = rtl.mint) AS has_liquidity,
    (SELECT COUNT(DISTINCT dex_platform) FROM liquidity_pairs lp WHERE lp.token_mint = rtl.mint) AS dex_count
  FROM recent_token_launches rtl
  LEFT JOIN token_distribution td ON rtl.mint = td.mint
  LEFT JOIN initial_transfers it ON rtl.mint = it.mint
)

-- Main query outputs
-- 1. Overall token launch metrics
SELECT
  symbol,
  name,
  mint,
  DATE_TRUNC('day', launch_time) AS launch_date,
  holder_count,
  total_supply,
  top_holder_percentage AS top_holder_pct,
  first_day_transfers,
  first_day_recipients,
  has_liquidity,
  dex_count,
  success_score,
  CASE
    WHEN success_score >= 80 THEN 'Excellent'
    WHEN success_score >= 60 THEN 'Good'
    WHEN success_score >= 40 THEN 'Average'
    WHEN success_score >= 20 THEN 'Poor'
    ELSE 'Very Poor'
  END AS launch_quality
FROM launch_success_metrics
ORDER BY launch_time DESC;

-- 2. Daily token launch count
SELECT
  DATE_TRUNC('day', launch_time) AS day,
  COUNT(*) AS token_launches,
  AVG(holder_count) AS avg_holders,
  AVG(top_holder_percentage) AS avg_concentration,
  AVG(success_score) AS avg_success_score
FROM launch_success_metrics
GROUP BY 1
ORDER BY 1 DESC;

-- 3. Top token creators
SELECT
  ca.creator_address,
  ca.tokens_created,
  AVG(lsm.success_score) AS avg_success_score,
  MAX(lsm.success_score) AS best_launch_score,
  MIN(lsm.success_score) AS worst_launch_score,
  ARRAY_AGG(lsm.symbol) AS token_symbols
FROM creator_activity ca
JOIN recent_token_launches rtl ON ca.creator_address = rtl.creator_address
JOIN launch_success_metrics lsm ON rtl.mint = lsm.mint
WHERE ca.tokens_created > 1
GROUP BY 1, 2
ORDER BY ca.tokens_created DESC, avg_success_score DESC;

-- 4. Potential insider trading activity
SELECT
  mint,
  symbol,
  from_account,
  to_account,
  token_amount,
  block_time,
  before_price,
  after_price,
  price_change_pct
FROM insider_patterns
ORDER BY price_change_pct DESC, token_amount DESC;

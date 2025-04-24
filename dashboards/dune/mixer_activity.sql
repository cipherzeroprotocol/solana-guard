-- SolanaGuard: Mixer Activity Detection and Analysis
-- This query identifies potential mixer services and their usage patterns on Solana

-- Known mixer programs and addresses
WITH known_mixers AS (
  SELECT address, name, risk_level
  FROM (VALUES
    ('tor1xzb2Zyy1cUxXmyJfR8aNXuWnwHG8AwgaG7UGD4K', 'TornadoClone', 'very_high'),
    ('mixerEfg3yXGYZJbhG43RJ2KdMUXbf6s9YGBXnJE9Qj2T', 'SolMixer', 'high'),
    ('cyc1e3PYPBv4FfCqVj8PGD99C9tUBr8K7GHMpNM5hKE', 'CycleProtocol', 'high'),
    ('shuf7F4LADDnUVSgHQpVbdAP7zQX6NdXQ6VTwSD7j4nK', 'SolShuffler', 'high')
  ) AS t(address, name, risk_level)
),

-- Identify transactions with known mixers
known_mixer_txs AS (
  SELECT
    tx.tx_id,
    tx.block_time,
    tx.signer,
    km.address AS mixer_address,
    km.name AS mixer_name,
    km.risk_level,
    tx.fee,
    tx.success
  FROM solana.transactions tx
  JOIN lateral (
    SELECT unnest(account_keys) AS address
  ) AS addresses ON true
  JOIN known_mixers km ON addresses.address = km.address
  WHERE tx.block_time >= NOW() - INTERVAL '90 days'
    AND tx.success = true
),

-- Identify potential mixers through pattern analysis
potential_mixers AS (
  -- Find contracts with anonymity-enhancing patterns
  WITH tx_patterns AS (
    SELECT 
      i.account_keys[i.program_index] AS program_id,
      COUNT(DISTINCT tx.signer) AS unique_users,
      COUNT(*) AS transaction_count,
      -- Distribution of transaction amounts
      percentile_disc(0.5) WITHIN GROUP (ORDER BY tx.fee) AS median_fee,
      COUNT(DISTINCT extract(hour from tx.block_time)) AS active_hours,
      -- Time between similar transactions
      AVG(extract(epoch from tx.block_time - LAG(tx.block_time) OVER (PARTITION BY i.account_keys[i.program_index] ORDER BY tx.block_time))) AS avg_seconds_between_txs
    FROM solana.instructions i
    JOIN solana.transactions tx ON i.tx_id = tx.tx_id
    WHERE tx.block_time >= NOW() - INTERVAL '90 days'
      AND tx.success = true
    GROUP BY i.account_keys[i.program_index]
    HAVING COUNT(*) > 50 -- Only consider programs with significant usage
  )
  
  SELECT
    program_id,
    unique_users,
    transaction_count,
    median_fee,
    active_hours,
    avg_seconds_between_txs,
    -- Risk scoring based on mixer patterns
    CASE
      -- High number of users, consistent transaction sizes, 24h activity
      WHEN unique_users >= 100 AND active_hours >= 20 THEN 'very_high'
      -- Many users with somewhat consistent pattern
      WHEN unique_users >= 50 AND active_hours >= 15 THEN 'high'
      -- Moderate indicators
      WHEN unique_users >= 25 THEN 'medium'
      ELSE 'low'
    END AS risk_level,
    'potential' AS mixer_type
  FROM tx_patterns
  WHERE 
    -- Consistent spacing between transactions
    avg_seconds_between_txs < 3600 AND
    -- High ratio of unique users to transactions
    unique_users * 1.0 / transaction_count > 0.3 AND
    -- Round the clock activity (indicates automated service)
    active_hours >= 12
  ORDER BY unique_users * active_hours DESC
),

-- Combine known and potential mixers
all_mixers AS (
  SELECT address AS mixer_id, name AS mixer_name, risk_level, 'known' AS mixer_type
  FROM known_mixers
  
  UNION ALL
  
  SELECT program_id AS mixer_id, 'Unlabeled-' || LEFT(program_id, 8) AS mixer_name, risk_level, mixer_type
  FROM potential_mixers
),

-- User activity with mixers
user_mixer_activity AS (
  -- Interactions with known mixers
  SELECT
    tx.signer AS user_address,
    km.address AS mixer_address,
    km.name AS mixer_name,
    km.risk_level,
    COUNT(*) AS transaction_count,
    SUM(tx.fee) AS total_fees,
    MIN(tx.block_time) AS first_seen,
    MAX(tx.block_time) AS last_seen
  FROM solana.transactions tx
  JOIN lateral (
    SELECT unnest(account_keys) AS address
  ) AS addresses ON true
  JOIN known_mixers km ON addresses.address = km.address
  WHERE tx.block_time >= NOW() - INTERVAL '90 days'
    AND tx.success = true
  GROUP BY tx.signer, km.address, km.name, km.risk_level
  
  UNION ALL
  
  -- Interactions with potential mixers
  SELECT
    tx.signer AS user_address,
    i.account_keys[i.program_index] AS mixer_address,
    'Unlabeled-' || LEFT(i.account_keys[i.program_index], 8) AS mixer_name,
    pm.risk_level,
    COUNT(*) AS transaction_count,
    SUM(tx.fee) AS total_fees,
    MIN(tx.block_time) AS first_seen,
    MAX(tx.block_time) AS last_seen
  FROM solana.instructions i
  JOIN solana.transactions tx ON i.tx_id = tx.tx_id
  JOIN potential_mixers pm ON i.account_keys[i.program_index] = pm.program_id
  WHERE tx.block_time >= NOW() - INTERVAL '90 days'
    AND tx.success = true
  GROUP BY tx.signer, i.account_keys[i.program_index], pm.risk_level
),

-- Mixer usage time patterns
mixer_time_patterns AS (
  SELECT
    DATE_TRUNC('day', kmtx.block_time) AS day,
    kmtx.mixer_name,
    COUNT(*) AS daily_transactions,
    COUNT(DISTINCT kmtx.signer) AS daily_users
  FROM known_mixer_txs kmtx
  GROUP BY 1, 2
  
  UNION ALL
  
  SELECT
    DATE_TRUNC('day', tx.block_time) AS day,
    'Unlabeled-' || LEFT(i.account_keys[i.program_index], 8) AS mixer_name,
    COUNT(*) AS daily_transactions,
    COUNT(DISTINCT tx.signer) AS daily_users
  FROM solana.instructions i
  JOIN solana.transactions tx ON i.tx_id = tx.tx_id
  JOIN potential_mixers pm ON i.account_keys[i.program_index] = pm.program_id
  WHERE tx.success = true
  GROUP BY 1, 2
),

-- Transactions before and after mixer usage
mixer_adjacency AS (
  -- Find transactions shortly before mixer usage
  WITH mixer_users AS (
    SELECT DISTINCT user_address, mixer_address, first_seen
    FROM user_mixer_activity
  )
  
  SELECT
    mu.user_address,
    mu.mixer_address,
    tx.tx_id AS adjacent_tx_id,
    tx.block_time,
    tx.signer,
    CASE
      WHEN tx.block_time < mu.first_seen THEN 'before'
      ELSE 'after'
    END AS timing,
    ABS(EXTRACT(EPOCH FROM (tx.block_time - mu.first_seen)) / 3600) AS hours_difference,
    tx.fee
  FROM mixer_users mu
  JOIN solana.transactions tx ON 
    tx.signer = mu.user_address AND
    tx.block_time BETWEEN mu.first_seen - INTERVAL '24 hours' AND mu.first_seen + INTERVAL '24 hours'
  WHERE tx.success = true
),

-- High-value transfers before mixing
high_value_premix AS (
  SELECT
    ma.user_address,
    ma.mixer_address,
    ma.mixer_name,
    tr.tx_id,
    tr.from_account,
    tr.to_account,
    tr.amount / POWER(10, COALESCE(tk.decimals, 9)) AS amount,
    tk.symbol,
    tr.block_time,
    ma.first_seen AS first_mixer_usage
  FROM user_mixer_activity ma
  JOIN solana.transfers tr ON 
    tr.from_account = ma.user_address OR tr.to_account = ma.user_address
  LEFT JOIN solana.tokens tk ON tr.mint = tk.mint
  WHERE tr.block_time BETWEEN ma.first_seen - INTERVAL '24 hours' AND ma.first_seen
  ORDER BY tr.amount DESC
  LIMIT 1000
)

-- Main query outputs
-- 1. Top mixers by usage
SELECT
  mixer_id,
  mixer_name,
  risk_level,
  mixer_type,
  COUNT(DISTINCT uma.user_address) AS unique_users,
  SUM(uma.transaction_count) AS total_transactions,
  AVG(uma.transaction_count) AS avg_transactions_per_user,
  MIN(uma.first_seen) AS first_activity,
  MAX(uma.last_seen) AS last_activity
FROM all_mixers am
LEFT JOIN user_mixer_activity uma ON am.mixer_id = uma.mixer_address
GROUP BY 1, 2, 3, 4
ORDER BY unique_users DESC, total_transactions DESC;

-- 2. Daily mixer activity
SELECT
  day,
  mixer_name,
  daily_transactions,
  daily_users,
  daily_transactions * 1.0 / daily_users AS avg_tx_per_user
FROM mixer_time_patterns
ORDER BY day DESC, daily_transactions DESC;

-- 3. Top mixer users
SELECT
  user_address,
  COUNT(DISTINCT mixer_address) AS unique_mixers_used,
  SUM(transaction_count) AS total_transactions,
  MAX(risk_level) AS highest_risk_level,
  MIN(first_seen) AS first_mixer_usage,
  MAX(last_seen) AS last_mixer_usage,
  EXTRACT(DAY FROM MAX(last_seen) - MIN(first_seen)) AS days_active
FROM user_mixer_activity
GROUP BY 1
ORDER BY unique_mixers_used DESC, total_transactions DESC
LIMIT 100;

-- 4. High-value pre-mixing transfers
SELECT
  user_address,
  mixer_name,
  from_account,
  to_account,
  amount,
  symbol,
  block_time,
  first_mixer_usage,
  EXTRACT(MINUTES FROM (first_mixer_usage - block_time)) AS minutes_before_mixing
FROM high_value_premix
WHERE amount > 100 -- Only significant transfers
ORDER BY amount DESC
LIMIT 50;

-- SolanaGuard: Money Laundering Route Analysis
-- This query identifies potential money laundering patterns and routes on Solana

-- Known high-risk entities and addresses
WITH high_risk_entities AS (
  SELECT address, entity_type, risk_level
  FROM (VALUES
    -- These would be addresses identified from external sources or previous analysis
    ('tor1xzb2Zyy1cUxXmyJfR8aNXuWnwHG8AwgaG7UGD4K', 'mixer', 'very_high'),
    ('mixerEfg3yXGYZJbhG43RJ2KdMUXbf6s9YGBXnJE9Qj2T', 'mixer', 'high'),
    ('worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth', 'bridge', 'medium'),
    ('3u8hJUVTA4jH1wYAyUur7FFZVQ8H635K3tSHHF4ssjQ5', 'bridge', 'medium')
  ) AS t(address, entity_type, risk_level)
),

-- High-risk programs
high_risk_programs AS (
  SELECT program_id, program_type, risk_level
  FROM (VALUES
    ('worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth', 'bridge', 'medium'),
    ('wormDTUJ6AWPNvk59vGQbDvGJmqbDTdgWgAqcLBCgUb', 'bridge', 'medium'),
    ('3u8hJUVTA4jH1wYAyUur7FFZVQ8H635K3tSHHF4ssjQ5', 'bridge', 'medium'),
    ('tornadoXzb2Zyy1cUxXmyJfR8aNXuWnwHG8AwgaG7UGD4K', 'mixer', 'very_high')
  ) AS t(program_id, program_type, risk_level)
),

-- Identify transactions with high-risk addresses
high_risk_transactions AS (
  SELECT
    tx.tx_id,
    tx.block_time,
    tx.signer,
    tx.fee,
    hre.address AS high_risk_address,
    hre.entity_type,
    hre.risk_level
  FROM solana.transactions tx
  JOIN lateral (
    SELECT unnest(account_keys) AS address
  ) AS addresses ON true
  JOIN high_risk_entities hre ON addresses.address = hre.address
  WHERE tx.block_time >= NOW() - INTERVAL '30 days'
),

-- Transactions using high-risk programs
high_risk_program_usage AS (
  SELECT
    tx.tx_id,
    tx.block_time,
    tx.signer,
    i.account_keys[i.program_index] AS program_id,
    hrp.program_type,
    hrp.risk_level
  FROM solana.instructions i
  JOIN solana.transactions tx ON i.tx_id = tx.tx_id
  JOIN high_risk_programs hrp ON i.account_keys[i.program_index] = hrp.program_id
  WHERE tx.block_time >= NOW() - INTERVAL '30 days'
),

-- Identify layering patterns (multiple hops in short time)
layering_patterns AS (
  WITH transaction_graph AS (
    -- Create a graph of transactions by connecting signers and receivers
    SELECT 
      tx.tx_id,
      tx.block_time,
      tx.signer AS source,
      tr.to_account AS destination,
      tr.amount / POWER(10, COALESCE(tk.decimals, 9)) AS amount,
      tk.symbol
    FROM solana.transactions tx
    JOIN solana.transfers tr ON tx.tx_id = tr.tx_id
    LEFT JOIN solana.tokens tk ON tr.mint = tk.mint
    WHERE tx.block_time >= NOW() - INTERVAL '30 days'
  ),
  
  multi_hop_paths AS (
    -- Find paths where funds move through multiple wallets in a short time
    SELECT
      t1.source AS origin_address,
      t1.destination AS hop1,
      t2.destination AS hop2,
      t3.destination AS final_destination,
      t1.amount AS initial_amount,
      t1.symbol AS token,
      t1.block_time AS hop1_time,
      t2.block_time AS hop2_time,
      t3.block_time AS final_time,
      EXTRACT(EPOCH FROM (t3.block_time - t1.block_time)) / 60 AS minutes_elapsed
    FROM transaction_graph t1
    JOIN transaction_graph t2 ON 
      t1.destination = t2.source AND
      t2.block_time > t1.block_time AND
      t2.block_time < t1.block_time + INTERVAL '30 minutes'
    JOIN transaction_graph t3 ON 
      t2.destination = t3.source AND
      t3.block_time > t2.block_time AND
      t3.block_time < t2.block_time + INTERVAL '30 minutes'
    WHERE
      -- Ensure this is a chain of different addresses
      t1.source != t1.destination AND
      t1.destination != t2.destination AND
      t2.destination != t3.destination AND
      t1.source != t3.destination AND
      -- Fast movement is suspicious
      EXTRACT(EPOCH FROM (t3.block_time - t1.block_time)) / 60 < 60 -- Less than 60 minutes for full path
  )
  
  SELECT 
    origin_address,
    final_destination,
    COUNT(DISTINCT hop1) AS unique_intermediaries,
    COUNT(*) AS path_count,
    MIN(minutes_elapsed) AS min_minutes_elapsed,
    MAX(minutes_elapsed) AS max_minutes_elapsed,
    array_agg(DISTINCT token) AS tokens
  FROM multi_hop_paths
  GROUP BY 1, 2
  HAVING COUNT(*) > 2 -- Multiple paths between the same origin and destination
  ORDER BY COUNT(*) DESC
  LIMIT 100
),

-- Detect splitting and combining patterns
split_combine_patterns AS (
  WITH outgoing_transactions AS (
    -- Find addresses that split funds into multiple destinations in a short time
    SELECT
      tx.signer AS source_address,
      COUNT(DISTINCT tr.to_account) AS destination_count,
      MIN(tx.block_time) AS start_time,
      MAX(tx.block_time) AS end_time,
      SUM(tr.amount / POWER(10, COALESCE(tk.decimals, 9))) AS total_amount,
      tk.symbol
    FROM solana.transactions tx
    JOIN solana.transfers tr ON tx.tx_id = tr.tx_id
    LEFT JOIN solana.tokens tk ON tr.mint = tk.mint
    WHERE 
      tx.block_time >= NOW() - INTERVAL '30 days'
    GROUP BY tx.signer, tk.symbol, tk.decimals
    HAVING 
      COUNT(DISTINCT tr.to_account) > 5 AND -- Split into many addresses
      EXTRACT(EPOCH FROM (MAX(tx.block_time) - MIN(tx.block_time))) / 60 < 120 -- Within 2 hours
  ),
  
  incoming_transactions AS (
    -- Find addresses that receive funds from multiple sources in a short time
    SELECT
      tr.to_account AS destination_address,
      COUNT(DISTINCT tx.signer) AS source_count,
      MIN(tx.block_time) AS start_time,
      MAX(tx.block_time) AS end_time,
      SUM(tr.amount / POWER(10, COALESCE(tk.decimals, 9))) AS total_amount,
      tk.symbol
    FROM solana.transactions tx
    JOIN solana.transfers tr ON tx.tx_id = tr.tx_id
    LEFT JOIN solana.tokens tk ON tr.mint = tk.mint
    WHERE 
      tx.block_time >= NOW() - INTERVAL '30 days'
    GROUP BY tr.to_account, tk.symbol, tk.decimals
    HAVING 
      COUNT(DISTINCT tx.signer) > 5 AND -- Combined from many addresses
      EXTRACT(EPOCH FROM (MAX(tx.block_time) - MIN(tx.block_time))) / 60 < 120 -- Within 2 hours
  )
  
  -- Find addresses involved in both splitting and combining
  SELECT 
    COALESCE(o.source_address, i.destination_address) AS address,
    o.destination_count,
    i.source_count,
    CASE
      WHEN o.source_address IS NOT NULL AND i.destination_address IS NOT NULL THEN 'both'
      WHEN o.source_address IS NOT NULL THEN 'splitting'
      ELSE 'combining'
    END AS pattern_type,
    COALESCE(o.total_amount, 0) AS outgoing_amount,
    COALESCE(i.total_amount, 0) AS incoming_amount,
    COALESCE(o.symbol, i.symbol) AS token
  FROM outgoing_transactions o
  FULL OUTER JOIN incoming_transactions i ON o.source_address = i.destination_address
  WHERE 
    o.source_address IS NOT NULL OR i.destination_address IS NOT NULL
  ORDER BY 
    CASE
      WHEN o.source_address IS NOT NULL AND i.destination_address IS NOT NULL THEN 3
      WHEN o.destination_count > i.source_count THEN 2
      ELSE 1
    END DESC,
    COALESCE(o.destination_count, 0) + COALESCE(i.source_count, 0) DESC
  LIMIT 100
),

-- Cross-chain bridge activity
bridge_activity AS (
  SELECT
    tx.signer AS address,
    hrp.program_id,
    hrp.program_type,
    COUNT(*) AS bridge_tx_count,
    MIN(tx.block_time) AS first_bridge_tx,
    MAX(tx.block_time) AS last_bridge_tx
  FROM high_risk_program_usage hrp
  JOIN solana.transactions tx ON hrp.tx_id = tx.tx_id
  WHERE hrp.program_type = 'bridge'
  GROUP BY 1, 2, 3
  ORDER BY 4 DESC
  LIMIT 100
),

-- Mixer usage
mixer_activity AS (
  SELECT
    tx.signer AS address,
    hrp.program_id,
    hrp.program_type,
    COUNT(*) AS mixer_tx_count,
    MIN(tx.block_time) AS first_mixer_tx,
    MAX(tx.block_time) AS last_mixer_tx
  FROM high_risk_program_usage hrp
  JOIN solana.transactions tx ON hrp.tx_id = tx.tx_id
  WHERE hrp.program_type = 'mixer'
  GROUP BY 1, 2, 3
  ORDER BY 4 DESC
  LIMIT 100
),

-- High velocity transactions (potential structuring)
high_velocity_structuring AS (
  WITH tx_groups AS (
    SELECT
      signer,
      block_time,
      tx_id,
      LAG(block_time) OVER (PARTITION BY signer ORDER BY block_time) AS prev_time
    FROM solana.transactions
    WHERE block_time >= NOW() - INTERVAL '7 days'
  )
  
  SELECT
    signer AS address,
    COUNT(*) AS transaction_count,
    MIN(block_time) AS first_transaction,
    MAX(block_time) AS last_transaction,
    AVG(EXTRACT(EPOCH FROM (block_time - prev_time))) AS avg_seconds_between_txs,
    STDDEV(EXTRACT(EPOCH FROM (block_time - prev_time))) AS stddev_seconds_between_txs,
    COUNT(*) / EXTRACT(EPOCH FROM (MAX(block_time) - MIN(block_time))) * 3600 AS tx_per_hour
  FROM tx_groups
  WHERE prev_time IS NOT NULL
  GROUP BY 1
  HAVING 
    COUNT(*) > 50 AND -- Significant number of transactions
    AVG(EXTRACT(EPOCH FROM (block_time - prev_time))) < 300 AND -- Less than 5 minutes between transactions on average
    STDDEV(EXTRACT(EPOCH FROM (block_time - prev_time))) < 100 AND -- Very consistent timing (potential automation)
    COUNT(*) / EXTRACT(EPOCH FROM (MAX(block_time) - MIN(block_time))) * 3600 > 5 -- More than 5 transactions per hour
  ORDER BY tx_per_hour DESC
  LIMIT 100
),

-- Combined money laundering risk scoring
risk_scoring AS (
  SELECT
    address,
    SUM(CASE 
      WHEN risk_factor = 'high_risk_interactions' THEN high_risk_score * 0.3
      WHEN risk_factor = 'layering' THEN layering_score * 0.25
      WHEN risk_factor = 'split_combine' THEN split_combine_score * 0.15
      WHEN risk_factor = 'bridge_usage' THEN bridge_score * 0.15
      WHEN risk_factor = 'mixer_usage' THEN mixer_score * 0.25
      WHEN risk_factor = 'high_velocity' THEN velocity_score * 0.1
      ELSE 0
    END) AS combined_risk_score,
    MAX(high_risk_score) AS high_risk_score,
    MAX(layering_score) AS layering_score,
    MAX(split_combine_score) AS split_combine_score,
    MAX(bridge_score) AS bridge_score,
    MAX(mixer_score) AS mixer_score,
    MAX(velocity_score) AS velocity_score,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT risk_factor), NULL) AS risk_factors,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT entity_type), NULL) AS entity_types
  FROM (
    -- High-risk entity interactions
    SELECT
      hrt.signer AS address,
      'high_risk_interactions' AS risk_factor,
      hre.entity_type,
      CASE 
        WHEN hre.risk_level = 'very_high' THEN 100
        WHEN hre.risk_level = 'high' THEN 80
        WHEN hre.risk_level = 'medium' THEN 60
        ELSE 40
      END AS high_risk_score,
      NULL AS layering_score,
      NULL AS split_combine_score,
      NULL AS bridge_score,
      NULL AS mixer_score,
      NULL AS velocity_score
    FROM high_risk_transactions hrt
    JOIN high_risk_entities hre ON hrt.high_risk_address = hre.address
    
    UNION ALL
    
    -- Layering patterns
    SELECT
      lp.origin_address AS address,
      'layering' AS risk_factor,
      NULL AS entity_type,
      NULL AS high_risk_score,
      CASE
        WHEN lp.unique_intermediaries >= 5 AND lp.path_count >= 10 THEN 100
        WHEN lp.unique_intermediaries >= 3 AND lp.path_count >= 5 THEN 80
        WHEN lp.unique_intermediaries >= 2 AND lp.path_count >= 3 THEN 60
        ELSE 40
      END AS layering_score,
      NULL AS split_combine_score,
      NULL AS bridge_score,
      NULL AS mixer_score,
      NULL AS velocity_score
    FROM layering_patterns lp
    
    UNION ALL
    
    -- Split-combine patterns
    SELECT
      sc.address,
      'split_combine' AS risk_factor,
      NULL AS entity_type,
      NULL AS high_risk_score,
      NULL AS layering_score,
      CASE
        WHEN sc.pattern_type = 'both' AND sc.destination_count > 10 AND sc.source_count > 10 THEN 100
        WHEN sc.pattern_type = 'both' AND (sc.destination_count > 5 OR sc.source_count > 5) THEN 80
        WHEN sc.pattern_type = 'splitting' AND sc.destination_count > 10 THEN 70
        WHEN sc.pattern_type = 'combining' AND sc.source_count > 10 THEN 70
        ELSE 50
      END AS split_combine_score,
      NULL AS bridge_score,
      NULL AS mixer_score,
      NULL AS velocity_score
    FROM split_combine_patterns sc
    
    UNION ALL
    
    -- Bridge usage
    SELECT
      ba.address,
      'bridge_usage' AS risk_factor,
      'bridge' AS entity_type,
      NULL AS high_risk_score,
      NULL AS layering_score,
      NULL AS split_combine_score,
      CASE
        WHEN ba.bridge_tx_count > 10 THEN 90
        WHEN ba.bridge_tx_count > 5 THEN 70
        ELSE 50
      END AS bridge_score,
      NULL AS mixer_score,
      NULL AS velocity_score
    FROM bridge_activity ba
    
    UNION ALL
    
    -- Mixer usage
    SELECT
      ma.address,
      'mixer_usage' AS risk_factor,
      'mixer' AS entity_type,
      NULL AS high_risk_score,
      NULL AS layering_score,
      NULL AS split_combine_score,
      NULL AS bridge_score,
      CASE
        WHEN ma.mixer_tx_count > 5 THEN 100
        WHEN ma.mixer_tx_count > 2 THEN 90
        ELSE 80
      END AS mixer_score,
      NULL AS velocity_score
    FROM mixer_activity ma
    
    UNION ALL
    
    -- High velocity structuring
    SELECT
      hvs.address,
      'high_velocity' AS risk_factor,
      NULL AS entity_type,
      NULL AS high_risk_score,
      NULL AS layering_score,
      NULL AS split_combine_score,
      NULL AS bridge_score,
      NULL AS mixer_score,
      CASE
        WHEN hvs.tx_per_hour > 20 AND hvs.stddev_seconds_between_txs < 50 THEN 90
        WHEN hvs.tx_per_hour > 10 THEN 70
        ELSE 50
      END AS velocity_score
    FROM high_velocity_structuring hvs
  ) combined_data
  GROUP BY address
)

-- Final output
SELECT
  address,
  combined_risk_score,
  CASE 
    WHEN combined_risk_score >= 80 THEN 'Very High'
    WHEN combined_risk_score >= 60 THEN 'High'
    WHEN combined_risk_score >= 40 THEN 'Medium'
    WHEN combined_risk_score >= 20 THEN 'Low'
    ELSE 'Very Low'
  END AS risk_level,
  risk_factors,
  entity_types,
  high_risk_score,
  layering_score,
  split_combine_score,
  bridge_score,
  mixer_score,
  velocity_score,
  -- Include a reference to source data for primary risk factors
  CASE
    WHEN mixer_score IS NOT NULL AND mixer_score > 0 THEN 
      (SELECT json_build_object(
        'program_id', program_id,
        'tx_count', mixer_tx_count
      ) FROM mixer_activity ma WHERE ma.address = risk_scoring.address LIMIT 1)
    WHEN bridge_score IS NOT NULL AND bridge_score > 0 THEN 
      (SELECT json_build_object(
        'program_id', program_id,
        'tx_count', bridge_tx_count
      ) FROM bridge_activity ba WHERE ba.address = risk_scoring.address LIMIT 1)
    WHEN layering_score IS NOT NULL AND layering_score > 0 THEN 
      (SELECT json_build_object(
        'unique_intermediaries', unique_intermediaries,
        'path_count', path_count,
        'final_destination', final_destination
      ) FROM layering_patterns lp WHERE lp.origin_address = risk_scoring.address LIMIT 1)
    ELSE NULL
  END AS primary_evidence
FROM risk_scoring
WHERE combined_risk_score >= 40 -- Focus on medium to high risk
ORDER BY combined_risk_score DESC
LIMIT 100;
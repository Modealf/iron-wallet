#!/usr/bin/env bash
set -euo pipefail

# 1) create a wallet by inserting directly (no wallet controller in POC)
WALLET_ID=$(docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "
  INSERT INTO wallets (id, user_id, balance_minor, currency) VALUES (gen_random_uuid(), gen_random_uuid(), 0, 'SAR')
  RETURNING id;
" --format csv | tail -n 1)

# 2) POST via gateway
IDEM=$(uuidgen)
curl -s -X POST http://localhost:8081/top-ups \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEM" \
  -d "{\"wallet_id\":\"$WALLET_ID\",\"amount_minor\":10000,\"currency\":\"SAR\"}" | jq
sleep 3
# 3) Check balance after settlement
docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "SELECT balance_minor FROM wallets WHERE id='$WALLET_ID';"

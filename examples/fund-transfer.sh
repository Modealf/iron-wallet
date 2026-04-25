#!/usr/bin/env bash
set -euo pipefail
WALLET_ID=$(docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "
  INSERT INTO wallets (id, user_id, balance_minor, currency) VALUES (gen_random_uuid(), gen_random_uuid(), 0, 'SAR')
  RETURNING id;
" --format csv | tail -n 1)
REF="bk-$(uuidgen)"
curl -s -X POST http://localhost:8081/bank-transfers \
  -H "Content-Type: application/json" \
  -d "{\"virtual_iban\":\"SA000000001\",\"amount_minor\":5000,\"currency\":\"SAR\",\"bank_reference\":\"$REF\",\"wallet_id\":\"$WALLET_ID\"}" | jq
sleep 2
docker exec database /cockroach/cockroach sql --insecure -d investment_wallet -e "SELECT balance_minor FROM wallets WHERE id='$WALLET_ID';"

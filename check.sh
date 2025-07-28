#!/bin/bash

# Input JSON file
JSON_FILE="../BehavioralBiometricSA/company_data/company_clients.json"
TASK_ID=101
ID=1

# Extract URLs, strip http:// or https:// prefix, and deduplicate
URLS=$(jq -r '.[] | .[]' "$JSON_FILE" | sed 's|^https\?://||' | sort -fu)

# Loop through each URL
echo "$URLS" | while read -r url; do
  [[ -z "$url" ]] && continue

  # Reconstruct full URL by prepending https:// if needed for actual request
  full_url="https://$url"

  # Extract domain
  scan_domain=$(echo "$url" | awk -F/ '{print $1}')

  # Create JSON payload
  read -r -d '' JSON_DATA <<EOF
{
  "task_id": $TASK_ID,
  "candidates": [
    {
      "id": $ID,
      "url": "$full_url",
      "actions": null,
      "scan_domain": "$scan_domain"
    }
  ]
}
EOF

  echo "[$ID] Sending to $full_url"
  curl -s -X POST "http://127.0.0.1:4050/api/login_candidates" \
       -H "Content-Type: application/json" \
       -d "$JSON_DATA"

  ID=$((ID + 1))
done

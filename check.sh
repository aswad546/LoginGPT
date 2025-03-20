#!/bin/bash
# Bash script to POST candidate data using curl

# Define JSON payload using a here-document
read -r -d '' JSON_DATA <<'EOF'
{
    "task_id": "8068d502-eb45-4657-81a6-ee17475f7c76",
    "candidates": [
    {
      "id": 1,
      "url": "https://www.pnc.com/en/personal-banking.html",
      "actions": [
        {
          "selectOptions": "None"
        },
        {
          "step": 1,
          "clickPosition": {
            "x": 1169,
            "y": 110
          },
          "elementHTML": "<span class=\" cmp-button__text\">\n    <span class=\"cmp-button__icon cmp-button__icon--login fa-solid fa-user\" aria-hidden=\"true\"></span>\n SIGN ON</span>",
          "screenshot": "/app/modules/loginpagedetection/screenshot_flows/www_pnc_com/flow_0/page_1.png",
          "url": "https://www.pnc.com/en/personal-banking.html"
        }
      ],
      "scan_domain": "www.pnc.com"
    },
    {
      "id": 2,
      "url": "https://www.pnc.com/login",
      "actions": null,
      "scan_domain": "www.pnc.com"
    },
    {
      "id": 3,
      "url": "https://www.pnc.com/en/personal-banking/banking/online-and-mobile-banking/online-banking.html",
      "actions": null,
      "scan_domain": "www.pnc.com"
    },
    {
      "id": 4,
      "url": "https://www.pnc.com/en/personal-banking/banking/online-and-mobile-banking.html",
      "actions": null,
      "scan_domain": "www.pnc.com"
    }
  ]
}

EOF

# Execute the curl POST request
curl -X POST "http://127.0.0.1:4050/api/login_candidates" \
     -H "Content-Type: application/json" \
     -d "${JSON_DATA}"

# curl -X POST "http://host.docker.internal:8889/api/login_candidates" \
#      -H "Content-Type: application/json" \
#      -d "${}"

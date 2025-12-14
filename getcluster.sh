#!/usr/bin/env bash

set -e

for project in $(gcloud projects list --format="value(projectId)"); do
  echo "==> Project: $project"
  gcloud config set project "$project" >/dev/null

  gcloud container clusters list --format="value(name,location)" 2>/dev/null | \
  while read name location; do
    if [[ -n "$name" ]]; then
      echo "  -> Fetching credentials for cluster: $name ($location)"
      gcloud container clusters get-credentials "$name" \
        --location "$location" \
        --project "$project"
    fi
  done
done

#!/usr/bin/env bash
#
#  Bump the IRIS version across all three repos and the meta.
#
#  Usage: scripts/bump-version.sh <major|minor|patch|pre_l|pre_n>
#
#  Order:
#    1. bump-my-version in each submodule (backend, frontend), push tag
#    2. update meta submodule pointers to the freshly-tagged commits
#    3. bump-my-version in meta (rewrites docker-compose.yml + .env.example
#       + README image tags), commit + tag
#    4. push meta commit + tag
#
#  Prerequisites:
#    - bump-my-version available (pip install bump-my-version)
#    - working tree clean in each submodule and the meta
#    - submodules on their tracking branch

set -euo pipefail

part="${1:?usage: bump-version.sh <major|minor|patch|pre_l|pre_n>}"

cd "$(git rev-parse --show-toplevel)"

for repo in iris-backend iris-frontend; do
    echo "==> Bumping $repo ($part)"
    (
        cd "$repo"
        git diff --quiet
        branch="$(git config -f ../.gitmodules submodule."$repo".branch)"
        git checkout "$branch"
        git pull --ff-only
        bump-my-version bump "$part"
        git push origin HEAD
        git push origin --tags
    )
done

echo "==> Updating meta submodule pointers"
git add iris-backend iris-frontend

echo "==> Bumping meta ($part)"
# --allow-dirty because step above leaves the tree dirty — that IS the
# coupling that makes the meta commit atomic with the sub-repo tags.
bump-my-version bump "$part" --allow-dirty

git push origin HEAD
git push origin --tags

cat <<'EOF'

==> Done.

Reminder: also update iris-plane's supported IRIS versions to include
the new tag:
    - iris-plane/tenant-stack/images.lock.yaml
    - iris-plane/control-plane/api/src/seito_api/routes/tenants.py
      (SUPPORTED_IRIS_VERSIONS)
EOF

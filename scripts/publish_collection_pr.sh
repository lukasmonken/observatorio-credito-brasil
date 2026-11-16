#!/usr/bin/env bash
# Called on main after staging the output of one collector.
set -euo pipefail
case "$1" in
  bacen) scope='data/processed/'; title='Atualizar dados do Banco Central' ;;
  ibge) scope='data/inflation/'; title='Atualizar inflação do IBGE' ;;
  *) exit 2 ;;
esac
git diff --cached --quiet && exit 0
while IFS= read -r -d '' path; do
  [[ "$path" == "$scope"* ]] || { echo "Arquivo fora da coleta" >&2; exit 1; }
done < <(git diff --cached --no-renames --name-only -z)
branch="coletas/$1-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
git switch -c "$branch"
git commit -m "$title"
gh auth setup-git
git push origin "HEAD:refs/heads/$branch"
pr=$(gh pr create --base main --head "$branch" --title "$title" --body "Coleta automática $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID.")
head=$(git rev-parse HEAD)
# Use the PR checks on this candidate, including before branch protection is enabled.
for ((attempt=0; attempt<75; attempt++)); do
  info=$(gh pr view "$pr" --json state,headRefOid,mergeStateStatus)
  [[ $(jq -r .headRefOid <<<"$info") == "$head" ]] || exit 1
  case $(jq -r .state <<<"$info") in MERGED) exit 0 ;; CLOSED) exit 1 ;; esac
  case $(jq -r .mergeStateStatus <<<"$info") in
    DIRTY) echo 'Conflito na coleta' >&2; exit 1 ;;
    BEHIND)
      git fetch origin main
      # If the source code or this collector's output changed, a fresh collection is needed.
      if ! git diff --quiet HEAD...origin/main -- . ':(exclude)data/processed/**' ':(exclude)data/inflation/**' ||
         ! git diff --quiet HEAD...origin/main -- "$scope"; then
        echo 'A base da coleta mudou; execute uma nova coleta.' >&2; exit 1
      fi
      git merge --no-edit origin/main
      git push origin "HEAD:refs/heads/$branch"
      head=$(git rev-parse HEAD)
      continue ;;
  esac
  # gh returns 8 while checks are pending and 1 before checks are registered.
  checks=$(gh pr checks "$pr" --json workflow,name,state || true)
  if [[ -n "$checks" ]]; then
    expected=$(jq '[.[] | select((.workflow=="Verificar aplicação" and .name=="test") or (.workflow=="Publicar dashboard no GitHub Pages" and .name=="build"))]' <<<"$checks")
    if jq -e 'any(.[]; .state=="FAILURE" or .state=="CANCELLED" or .state=="TIMED_OUT")' <<<"$expected" >/dev/null; then
      echo "Verificação reprovada: $pr" >&2; exit 1
    fi
    if jq -e 'length==2 and all(.[]; .state=="SUCCESS")' <<<"$expected" >/dev/null; then
      if gh pr merge "$pr" --squash --match-head-commit "$head"; then
        [[ $(gh pr view "$pr" --json state --jq .state) == MERGED ]] && exit 0
      fi
    fi
  fi
  sleep 20
done
echo "Tempo de espera encerrado: $pr" >&2
exit 1

# Repo settings. The repo already exists, so it is imported, not created:
#   terraform import github_repository.crm_jobs crm-jobs
# Attributes left out here fall back to provider defaults, which can differ
# from the current settings, so the existing values are spelled out.
resource "github_repository" "crm_jobs" {
  name        = "crm-jobs"
  description = "A crm to help with my job hunt"
  visibility  = "public"

  has_issues      = true
  has_projects    = true
  has_wiki        = false
  has_discussions = false

  # Squash merge only; the squashed commit takes the PR title, which CI
  # checks is a Conventional Commit.
  allow_squash_merge          = true
  allow_merge_commit          = false
  allow_rebase_merge          = false
  allow_auto_merge            = true
  squash_merge_commit_title   = "PR_TITLE"
  squash_merge_commit_message = "COMMIT_MESSAGES"

  delete_branch_on_merge = true

  # Offer the "Update branch" button on PRs that are behind main.
  allow_update_branch = true

  # Never let Terraform delete the repo, e.g. after a rename here.
  lifecycle {
    prevent_destroy = true
  }
}

# GitHub Actions' app ID, so only Actions can report the required checks.
locals {
  github_actions_app_id = 15368
}

resource "github_repository_ruleset" "main" {
  name        = "protect-main"
  repository  = github_repository.crm_jobs.name
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
  }

  rules {
    deletion         = true
    non_fast_forward = true

    # Changes reach main only through a PR. No approvals: one person.
    pull_request {
      required_approving_review_count = 0
    }

    # Check names are the job names in .github/workflows/ci.yml, with the
    # matrix value appended. Strict: a PR must be up to date with main, so
    # the checks ran on what will be merged. A required check that never
    # reports blocks every merge, so a workflow must produce each one.
    required_status_checks {
      strict_required_status_checks_policy = true

      required_check {
        context        = "qa (3.14)"
        integration_id = local.github_actions_app_id
      }
      required_check {
        context        = "Conventional Commit title"
        integration_id = local.github_actions_app_id
      }
    }
  }
}

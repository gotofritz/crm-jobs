terraform {
  required_version = ">= 1.6"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

# Authenticates with the token in GITHUB_TOKEN.
provider "github" {
  owner = "gotofritz"
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-west1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-west1-a"
}

variable "machine_type" {
  description = "GCP machine type for all VMs"
  type        = string
  default     = "e2-medium"
}

variable "repo_url" {
  description = "Git repository URL (HTTPS, publicly accessible)"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key for VM access. Format: 'username:ssh-rsa AAAA...'"
  type        = string
  default     = ""
}

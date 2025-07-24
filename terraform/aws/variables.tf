# Variables for AWS Infrastructure

# General Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "agentimigrate"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner of the infrastructure"
  type        = string
  default     = "nagarro-team"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Networking
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# RDS Configuration
variable "rds_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "agentimigrate"
}

variable "database_username" {
  description = "Database username"
  type        = string
  default     = "agentimigrate_user"
}

variable "rds_backup_retention" {
  description = "RDS backup retention period in days"
  type        = number
  default     = 7
}

variable "rds_backup_window" {
  description = "RDS backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "rds_maintenance_window" {
  description = "RDS maintenance window"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# ECS Configuration
variable "ecs_task_cpu" {
  description = "ECS task CPU units"
  type        = number
  default     = 512
}

variable "ecs_task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 1024
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_min_capacity" {
  description = "Minimum ECS capacity for auto scaling"
  type        = number
  default     = 1
}

variable "ecs_max_capacity" {
  description = "Maximum ECS capacity for auto scaling"
  type        = number
  default     = 10
}

# SQS Configuration
variable "sqs_message_retention" {
  description = "SQS message retention period in seconds"
  type        = number
  default     = 1209600  # 14 days
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout in seconds"
  type        = number
  default     = 300  # 5 minutes
}

variable "sqs_max_receive_count" {
  description = "Maximum receive count for SQS dead letter queue"
  type        = number
  default     = 3
}

# API Gateway Configuration
variable "api_domain_name" {
  description = "Custom domain name for API Gateway"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for custom domain"
  type        = string
  default     = ""
}

# LLM API Keys (should be set via environment variables or CI/CD)
variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_api_key" {
  description = "Google/Gemini API key"
  type        = string
  default     = ""
  sensitive   = true
}

# Neo4j AuraDB Configuration
variable "neo4j_aura_uri" {
  description = "Neo4j AuraDB URI"
  type        = string
  default     = ""
}

variable "neo4j_aura_username" {
  description = "Neo4j AuraDB username"
  type        = string
  default     = ""
}

variable "neo4j_aura_password" {
  description = "Neo4j AuraDB password"
  type        = string
  default     = ""
  sensitive   = true
}

# Weaviate Cloud Configuration
variable "weaviate_cloud_url" {
  description = "Weaviate Cloud cluster URL"
  type        = string
  default     = ""
}

variable "weaviate_cloud_api_key" {
  description = "Weaviate Cloud API key"
  type        = string
  default     = ""
  sensitive   = true
}

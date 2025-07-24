# AgentiMigrate Platform - AWS Serverless Infrastructure
# Complete Infrastructure as Code for production deployment

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

# Configure AWS Provider
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "AgentiMigrate"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = var.owner
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local values
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = var.owner
  }
}

# Random password for RDS
resource "random_password" "rds_password" {
  length  = 16
  special = true
}

# VPC and Networking
module "vpc" {
  source = "./modules/vpc"
  
  name_prefix = local.name_prefix
  cidr_block  = var.vpc_cidr
  
  availability_zones = var.availability_zones
  
  tags = local.common_tags
}

# Security Groups
module "security_groups" {
  source = "./modules/security"
  
  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  
  tags = local.common_tags
}

# RDS PostgreSQL Database
module "rds" {
  source = "./modules/rds"
  
  name_prefix = local.name_prefix
  
  # Database configuration
  engine_version    = var.rds_engine_version
  instance_class    = var.rds_instance_class
  allocated_storage = var.rds_allocated_storage
  
  database_name = var.database_name
  username      = var.database_username
  password      = random_password.rds_password.result
  
  # Networking
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.security_groups.rds_security_group_id]
  
  # Backup and maintenance
  backup_retention_period = var.rds_backup_retention
  backup_window          = var.rds_backup_window
  maintenance_window     = var.rds_maintenance_window
  
  # Performance and monitoring
  performance_insights_enabled = true
  monitoring_interval         = 60
  
  tags = local.common_tags
}

# S3 Bucket for Object Storage
module "s3" {
  source = "./modules/s3"
  
  name_prefix = local.name_prefix
  
  # Bucket configuration
  versioning_enabled = true
  lifecycle_enabled  = true
  
  # Security
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  
  tags = local.common_tags
}

# SQS Queues and SNS Topics
module "messaging" {
  source = "./modules/messaging"
  
  name_prefix = local.name_prefix
  
  # Queue configuration
  message_retention_seconds = var.sqs_message_retention
  visibility_timeout_seconds = var.sqs_visibility_timeout
  
  # Dead letter queue
  max_receive_count = var.sqs_max_receive_count
  
  tags = local.common_tags
}

# Secrets Manager
module "secrets" {
  source = "./modules/secrets"
  
  name_prefix = local.name_prefix
  
  # Database secrets
  database_host     = module.rds.endpoint
  database_name     = var.database_name
  database_username = var.database_username
  database_password = random_password.rds_password.result
  
  # LLM API keys (will be set manually or via CI/CD)
  openai_api_key    = var.openai_api_key
  anthropic_api_key = var.anthropic_api_key
  google_api_key    = var.google_api_key
  
  tags = local.common_tags
}

# ECR Repositories for Container Images
module "ecr" {
  source = "./modules/ecr"
  
  name_prefix = local.name_prefix
  
  # Repository names
  repositories = [
    "assessment-service",
    "project-service", 
    "reporting-service"
  ]
  
  # Image lifecycle
  image_tag_mutability = "MUTABLE"
  scan_on_push        = true
  
  tags = local.common_tags
}

# ECS Fargate Cluster
module "ecs" {
  source = "./modules/ecs"
  
  name_prefix = local.name_prefix
  
  # Cluster configuration
  container_insights = true
  
  tags = local.common_tags
}

# ECS Services
module "ecs_services" {
  source = "./modules/ecs-services"
  
  name_prefix = local.name_prefix
  
  # Cluster
  cluster_id   = module.ecs.cluster_id
  cluster_name = module.ecs.cluster_name
  
  # Networking
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids
  
  # Security
  ecs_security_group_id = module.security_groups.ecs_security_group_id
  alb_security_group_id = module.security_groups.alb_security_group_id
  
  # Container images
  assessment_image = "${module.ecr.repository_urls["assessment-service"]}:latest"
  project_image    = "${module.ecr.repository_urls["project-service"]}:latest"
  
  # Environment variables
  environment_variables = {
    CONFIG_ENV                = var.environment
    AWS_REGION               = local.region
    RDS_ENDPOINT             = module.rds.endpoint
    S3_BUCKET_NAME           = module.s3.bucket_name
    SQS_QUEUE_URL            = module.messaging.queue_url
    SNS_TOPIC_ARN            = module.messaging.topic_arn
    SECRETS_MANAGER_PREFIX   = "${local.name_prefix}/secrets"
  }
  
  # Task configuration
  task_cpu    = var.ecs_task_cpu
  task_memory = var.ecs_task_memory
  
  # Service configuration
  desired_count = var.ecs_desired_count
  min_capacity  = var.ecs_min_capacity
  max_capacity  = var.ecs_max_capacity
  
  tags = local.common_tags
}

# Lambda Function for Reporting Service
module "lambda" {
  source = "./modules/lambda"
  
  name_prefix = local.name_prefix
  
  # Function configuration
  function_name = "reporting-service"
  runtime       = "python3.11"
  timeout       = 900
  memory_size   = 1024
  
  # Container image
  image_uri = "${module.ecr.repository_urls["reporting-service"]}:latest"
  
  # Networking
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
  security_group_ids = [module.security_groups.lambda_security_group_id]
  
  # Environment variables
  environment_variables = {
    CONFIG_ENV                = var.environment
    AWS_REGION               = local.region
    S3_BUCKET_NAME           = module.s3.bucket_name
    SECRETS_MANAGER_PREFIX   = "${local.name_prefix}/secrets"
  }
  
  # Permissions
  s3_bucket_arn = module.s3.bucket_arn
  secrets_arns  = module.secrets.secret_arns
  
  tags = local.common_tags
}

# API Gateway
module "api_gateway" {
  source = "./modules/api-gateway"
  
  name_prefix = local.name_prefix
  
  # ALB integration
  alb_dns_name = module.ecs_services.alb_dns_name
  alb_zone_id  = module.ecs_services.alb_zone_id
  
  # Lambda integration
  lambda_function_arn = module.lambda.function_arn
  lambda_function_name = module.lambda.function_name
  
  # Custom domain (optional)
  domain_name = var.api_domain_name
  certificate_arn = var.certificate_arn
  
  tags = local.common_tags
}

# CloudWatch Monitoring
module "monitoring" {
  source = "./modules/monitoring"
  
  name_prefix = local.name_prefix
  
  # Resources to monitor
  ecs_cluster_name = module.ecs.cluster_name
  ecs_service_names = module.ecs_services.service_names
  lambda_function_name = module.lambda.function_name
  rds_instance_id = module.rds.instance_id
  
  # Alerting
  sns_topic_arn = module.messaging.alerts_topic_arn
  
  tags = local.common_tags
}

# IAM Roles and Policies
module "iam" {
  source = "./modules/iam"
  
  name_prefix = local.name_prefix
  
  # Resource ARNs for permissions
  s3_bucket_arn    = module.s3.bucket_arn
  secrets_arns     = module.secrets.secret_arns
  sqs_queue_arn    = module.messaging.queue_arn
  sns_topic_arn    = module.messaging.topic_arn
  
  tags = local.common_tags
}

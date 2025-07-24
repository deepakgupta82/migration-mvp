# Outputs for AWS Infrastructure

# Networking
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnet_ids
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.vpc.public_subnet_ids
}

# Database
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
}

output "rds_port" {
  description = "RDS instance port"
  value       = module.rds.port
}

output "database_name" {
  description = "Database name"
  value       = var.database_name
}

# Object Storage
output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = module.s3.bucket_arn
}

# Messaging
output "sqs_queue_url" {
  description = "SQS queue URL"
  value       = module.messaging.queue_url
}

output "sns_topic_arn" {
  description = "SNS topic ARN"
  value       = module.messaging.topic_arn
}

# Container Registry
output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value       = module.ecr.repository_urls
}

# ECS
output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = module.ecs.cluster_arn
}

# Load Balancer
output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = module.ecs_services.alb_dns_name
}

output "alb_zone_id" {
  description = "Application Load Balancer zone ID"
  value       = module.ecs_services.alb_zone_id
}

# Lambda
output "lambda_function_name" {
  description = "Lambda function name"
  value       = module.lambda.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = module.lambda.function_arn
}

# API Gateway
output "api_gateway_url" {
  description = "API Gateway URL"
  value       = module.api_gateway.api_url
}

output "api_gateway_stage" {
  description = "API Gateway stage"
  value       = module.api_gateway.stage_name
}

# Secrets Manager
output "secrets_manager_prefix" {
  description = "Secrets Manager prefix"
  value       = "${local.name_prefix}/secrets"
}

# Monitoring
output "cloudwatch_log_groups" {
  description = "CloudWatch log group names"
  value       = module.monitoring.log_group_names
}

# IAM
output "ecs_task_role_arn" {
  description = "ECS task role ARN"
  value       = module.iam.ecs_task_role_arn
}

output "ecs_execution_role_arn" {
  description = "ECS execution role ARN"
  value       = module.iam.ecs_execution_role_arn
}

output "lambda_role_arn" {
  description = "Lambda execution role ARN"
  value       = module.iam.lambda_role_arn
}

# Configuration for application
output "application_config" {
  description = "Configuration values for the application"
  value = {
    environment = var.environment
    region      = var.aws_region
    
    # Database
    rds_endpoint = module.rds.endpoint
    database_name = var.database_name
    
    # Storage
    s3_bucket_name = module.s3.bucket_name
    
    # Messaging
    sqs_queue_url = module.messaging.queue_url
    sns_topic_arn = module.messaging.topic_arn
    
    # Secrets
    secrets_prefix = "${local.name_prefix}/secrets"
    
    # API
    api_url = module.api_gateway.api_url
  }
  sensitive = false
}

# Deployment information
output "deployment_info" {
  description = "Information needed for deployment"
  value = {
    ecr_repositories = module.ecr.repository_urls
    ecs_cluster_name = module.ecs.cluster_name
    ecs_service_names = module.ecs_services.service_names
    lambda_function_name = module.lambda.function_name
  }
}

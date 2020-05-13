# Require TF version to be same as or greater than 0.12.24
terraform {
  required_version = ">=0.12.24"
  backend "s3" {
    region  = "us-east-1"
    key     = "wri__gfw-data-api.tfstate"
    encrypt = true
  }
}

# Download any stable version in AWS provider of 2.36.0 or higher in 2.36 train
provider "aws" {
  region  = "us-east-1"
  version = "~> 2.56.0"
}

# some local
locals {
  bucket_suffix         = var.environment == "production" ? "" : "-${var.environment}"
  tf_state_bucket       = "gfw-terraform${local.bucket_suffix}"
  tags                  = data.terraform_remote_state.core.outputs.tags
  name_suffix           = terraform.workspace == "default" ? "" : "-${terraform.workspace}"
  project               = "gfw-data-api"
  aurora_instance_class = data.terraform_remote_state.core.outputs.aurora_cluster_instance_class
  aurora_max_vcpus      = local.aurora_instance_class == "db.t3.medium" ? 2 : local.aurora_instance_class == "db.r4.large" ? 2 : local.aurora_instance_class == "db.r4.xlarge" ? 4 : local.aurora_instance_class == "db.r4.2xlarge" ? 8 : local.aurora_instance_class == "db.r4.4xlarge" ? 16 : local.aurora_instance_class == "db.r4.8xlarge" ? 32 : local.aurora_instance_class == "db.r4.16xlarge" ? 64 : local.aurora_instance_class == "db.r5.large" ? 2 : local.aurora_instance_class == "db.r5.xlarge" ? 4 : local.aurora_instance_class == "db.r5.2xlarge" ? 8 : local.aurora_instance_class == "db.r5.4xlarge" ? 16 : local.aurora_instance_class == "db.r5.8xlarge" ? 32 : local.aurora_instance_class == "db.r5.12xlarge" ? 48 : local.aurora_instance_class == "db.r5.16xlarge" ? 64 : local.aurora_instance_class == "db.r5.24xlarge" ? 96 : ""
}


# Docker image for FastAPI app
module "app_docker_image" {
  source     = "git::https://github.com/wri/gfw-terraform-modules.git//modules/container_registry?ref=v0.1.2"
  image_name = lower("${local.project}${local.name_suffix}")
  root_dir   = "${path.root}/../"
}


# Docker image for Batch jobs
module "batch_docker_image" {
  source     = "git::https://github.com/wri/gfw-terraform-modules.git//modules/container_registry?ref=v0.1.2"
  image_name = lower("${local.project}${local.name_suffix}")
  root_dir   = "${path.root}/../batch/gdal-python.dockerfile"
}

module "fargate_autoscaling" {
  source                       = "git::https://github.com/wri/gfw-terraform-modules.git//modules/fargate_autoscaling?ref=v0.1.2"
  project                      = local.project
  name_suffix                  = local.name_suffix
  tags                         = local.tags
  vpc_id                       = data.terraform_remote_state.core.outputs.vpc_id
  private_subnet_ids           = data.terraform_remote_state.core.outputs.private_subnet_ids
  public_subnet_ids            = data.terraform_remote_state.core.outputs.public_subnet_ids
  container_name               = var.container_name
  container_port               = var.container_port
  listener_port                = var.listener_port
  desired_count                = var.desired_count
  fargate_cpu                  = var.fargate_cpu
  fargate_memory               = var.fargate_memory
  auto_scaling_cooldown        = var.auto_scaling_cooldown
  auto_scaling_max_capacity    = var.auto_scaling_max_capacity
  auto_scaling_max_cpu_util    = var.auto_scaling_max_cpu_util
  auto_scaling_min_capacity    = var.auto_scaling_min_capacity
  security_group_ids           = [data.terraform_remote_state.core.outputs.postgresql_security_group_id]
  task_role_policies           = [data.terraform_remote_state.core.outputs.iam_policy_s3_write_data-lake_arn]
  task_execution_role_policies = [data.terraform_remote_state.core.outputs.iam_policy_s3_write_data-lake_arn, data.terraform_remote_state.core.outputs.secrets_postgresql-reader_policy_arn, data.terraform_remote_state.core.outputs.secrets_postgresql-writer_policy_arn]
  container_definition         = data.template_file.container_definition.rendered

}

# Using instance types with 1 core only
module "batch_aurora_writer" {
  source                   = "git::https://github.com/wri/gfw-terraform-modules.git//modules/compute_environment?ref=master"
  ecs_role_policy_arns     = [data.terraform_remote_state.core.outputs.iam_policy_s3_write_data-lake_arn, data.terraform_remote_state.core.outputs.secrets_postgresql-reader_policy_arn, data.terraform_remote_state.core.outputs.secrets_postgresql-writer_policy_arn]
  instance_types           = ["a1.medium"] # currently not supported but want to have "m6g.medium", "t2.nano", "t2.micro", "t2.small"
  key_pair                 = var.key_pair
  max_vcpus                = local.aurora_max_vcpus
  project                  = local.project
  security_group_ids       = [data.terraform_remote_state.core.outputs.postgresql_security_group_id]
  subnets                  = data.terraform_remote_state.core.outputs.private_subnet_ids
  suffix                   = local.name_suffix
  tags                     = local.tags
  use_ephemeral_storage    = false
  compute_environment_name = "aurora_sql_writer"
}


module "batch_data_lake_writer" {
  source                   = "git::https://github.com/wri/gfw-terraform-modules.git//modules/compute_environment?ref=master"
  ecs_role_policy_arns     = [data.terraform_remote_state.core.outputs.iam_policy_s3_write_data-lake_arn, data.terraform_remote_state.core.outputs.secrets_postgresql-reader_policy_arn, data.terraform_remote_state.core.outputs.secrets_postgresql-writer_policy_arn]
  key_pair                 = var.key_pair
  project                  = local.project
  security_group_ids       = [data.terraform_remote_state.core.outputs.postgresql_security_group_id]
  subnets                  = data.terraform_remote_state.core.outputs.private_subnet_ids
  suffix                   = local.name_suffix
  tags                     = local.tags
  use_ephemeral_storage    = true
  compute_environment_name = "data_lake_writer"
}

module "batch_job_queues" {
  source                             = "./modules/batch"
  aurora_compute_environment_arn     = module.batch_aurora_writer.arn
  data_lake_compute_environment_arn  = module.batch_data_lake_writer.arn
  tile_cache_compute_environment_arn = module.batch_data_lake_writer.arn
  environment                        = var.environment
  name_suffix                        = local.name_suffix
  project                            = local.project
  repository_url                     = "${module.batch_docker_image.repository_url}:latest"
  s3_write_data-lake_arn             = data.terraform_remote_state.core.outputs.iam_policy_s3_write_data-lake_arn
  reader_secret_arn                  = data.terraform_remote_state.core.outputs.secrets_postgresql-reader_arn
  writer_secret_arn                  = data.terraform_remote_state.core.outputs.secrets_postgresql-writer_arn
}

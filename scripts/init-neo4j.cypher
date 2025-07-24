// =====================================================================================
// AgentiMigrate Platform - Neo4j Graph Database Initialization
// Create constraints, indexes, and sample infrastructure graph
// =====================================================================================

// =====================================================================================
// CONSTRAINTS AND INDEXES
// =====================================================================================

// Create constraints for unique identifiers
CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT component_id_unique IF NOT EXISTS FOR (c:Component) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT assessment_id_unique IF NOT EXISTS FOR (a:Assessment) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT dependency_id_unique IF NOT EXISTS FOR (d:Dependency) REQUIRE d.id IS UNIQUE;

// Create indexes for performance
CREATE INDEX component_name_index IF NOT EXISTS FOR (c:Component) ON (c.name);
CREATE INDEX component_type_index IF NOT EXISTS FOR (c:Component) ON (c.type);
CREATE INDEX component_category_index IF NOT EXISTS FOR (c:Component) ON (c.category);
CREATE INDEX project_name_index IF NOT EXISTS FOR (p:Project) ON (p.name);
CREATE INDEX assessment_status_index IF NOT EXISTS FOR (a:Assessment) ON (a.status);

// =====================================================================================
// CLEAR EXISTING DATA (FOR CLEAN INITIALIZATION)
// =====================================================================================

// Remove all existing nodes and relationships
MATCH (n) DETACH DELETE n;

// =====================================================================================
// CREATE SAMPLE PROJECT
// =====================================================================================

CREATE (project:Project {
    id: "550e8400-e29b-41d4-a716-446655440002",
    name: "Legacy ERP Migration to Cloud",
    description: "Comprehensive migration of legacy ERP system to cloud-native architecture",
    client_name: "TechCorp Solutions",
    status: "active",
    target_cloud: "aws",
    migration_strategy: "6Rs",
    created_at: datetime(),
    metadata: {
        priority: "high",
        business_impact: "critical",
        estimated_duration_weeks: 16,
        budget: 500000
    }
});

// =====================================================================================
// CREATE INFRASTRUCTURE COMPONENTS
// =====================================================================================

// Database Tier Components
CREATE (oracle_db:Component:Database {
    id: "550e8400-e29b-41d4-a716-446655440004",
    name: "Primary Database Server",
    type: "database",
    category: "data_tier",
    current_technology: "Oracle 11g",
    target_technology: "Amazon RDS for Oracle",
    migration_complexity: "medium",
    migration_priority: 1,
    migration_strategy: "replatform",
    configuration: {
        cpu_cores: 16,
        memory_gb: 64,
        storage_gb: 2000,
        database_size_gb: 800,
        version: "11.2.0.4",
        charset: "UTF8"
    },
    assessment_notes: "Critical component requiring careful migration planning due to data volume",
    estimated_downtime_hours: 8,
    risk_level: "medium"
});

CREATE (backup_db:Component:Database {
    id: "comp-backup-db-001",
    name: "Backup Database Server",
    type: "database",
    category: "data_tier",
    current_technology: "Oracle 11g Standby",
    target_technology: "Amazon RDS Multi-AZ",
    migration_complexity: "low",
    migration_priority: 3,
    migration_strategy: "replatform",
    configuration: {
        cpu_cores: 8,
        memory_gb: 32,
        storage_gb: 2000,
        role: "standby"
    },
    assessment_notes: "Standby database for disaster recovery",
    risk_level: "low"
});

// Application Tier Components
CREATE (app_server_1:Component:ApplicationServer {
    id: "550e8400-e29b-41d4-a716-446655440005",
    name: "Application Server 1",
    type: "application_server",
    category: "application_tier",
    current_technology: "WebLogic 12c",
    target_technology: "Amazon ECS with Fargate",
    migration_complexity: "high",
    migration_priority: 2,
    migration_strategy: "refactor",
    configuration: {
        cpu_cores: 8,
        memory_gb: 32,
        jvm_heap_gb: 16,
        weblogic_version: "12.2.1.4"
    },
    assessment_notes: "Primary application server requiring containerization",
    containerization_required: true,
    estimated_effort_weeks: 6,
    risk_level: "high"
});

CREATE (app_server_2:Component:ApplicationServer {
    id: "comp-app-server-002",
    name: "Application Server 2",
    type: "application_server",
    category: "application_tier",
    current_technology: "WebLogic 12c",
    target_technology: "Amazon ECS with Fargate",
    migration_complexity: "high",
    migration_priority: 2,
    migration_strategy: "refactor",
    configuration: {
        cpu_cores: 8,
        memory_gb: 32,
        jvm_heap_gb: 16,
        weblogic_version: "12.2.1.4"
    },
    assessment_notes: "Secondary application server in cluster",
    containerization_required: true,
    estimated_effort_weeks: 6,
    risk_level: "high"
});

CREATE (load_balancer:Component:LoadBalancer {
    id: "comp-load-balancer-001",
    name: "F5 Load Balancer",
    type: "load_balancer",
    category: "network_tier",
    current_technology: "F5 BIG-IP",
    target_technology: "AWS Application Load Balancer",
    migration_complexity: "medium",
    migration_priority: 4,
    migration_strategy: "replace",
    configuration: {
        model: "F5-BIG-LTM-VE-1G",
        ssl_termination: true,
        health_checks: true
    },
    assessment_notes: "Load balancer configuration needs to be recreated in AWS ALB",
    risk_level: "medium"
});

// Storage Tier Components
CREATE (file_storage:Component:Storage {
    id: "550e8400-e29b-41d4-a716-446655440006",
    name: "File Storage System",
    type: "storage",
    category: "storage_tier",
    current_technology: "NetApp FAS8200",
    target_technology: "Amazon EFS + S3",
    migration_complexity: "low",
    migration_priority: 4,
    migration_strategy: "rehost",
    configuration: {
        capacity_tb: 50,
        performance_tier: "high",
        protocol: "NFS",
        backup_frequency: "daily"
    },
    assessment_notes: "Straightforward migration to cloud storage services",
    data_transfer_method: "aws_datasync",
    estimated_transfer_days: 3,
    risk_level: "low"
});

CREATE (backup_storage:Component:Storage {
    id: "comp-backup-storage-001",
    name: "Backup Storage System",
    type: "storage",
    category: "storage_tier",
    current_technology: "Dell EMC Data Domain",
    target_technology: "Amazon S3 Glacier",
    migration_complexity: "low",
    migration_priority: 5,
    migration_strategy: "replace",
    configuration: {
        capacity_tb: 100,
        deduplication_ratio: 15,
        retention_years: 7
    },
    assessment_notes: "Long-term backup storage migration to cost-effective cloud solution",
    risk_level: "low"
});

// Network Components
CREATE (firewall:Component:Security {
    id: "comp-firewall-001",
    name: "Perimeter Firewall",
    type: "firewall",
    category: "security_tier",
    current_technology: "Cisco ASA 5525-X",
    target_technology: "AWS Security Groups + NACLs",
    migration_complexity: "medium",
    migration_priority: 3,
    migration_strategy: "replace",
    configuration: {
        model: "ASA5525-K9",
        throughput_mbps: 2000,
        concurrent_connections: 750000
    },
    assessment_notes: "Firewall rules need to be translated to AWS security groups",
    risk_level: "medium"
});

CREATE (network_switch:Component:Network {
    id: "comp-network-switch-001",
    name: "Core Network Switch",
    type: "network_switch",
    category: "network_tier",
    current_technology: "Cisco Catalyst 6500",
    target_technology: "AWS VPC Native",
    migration_complexity: "low",
    migration_priority: 6,
    migration_strategy: "replace",
    configuration: {
        model: "WS-C6506-E",
        port_count: 48,
        speed_gbps: 10
    },
    assessment_notes: "Physical networking replaced by AWS VPC",
    risk_level: "low"
});

// Monitoring and Management
CREATE (monitoring:Component:Monitoring {
    id: "comp-monitoring-001",
    name: "Infrastructure Monitoring",
    type: "monitoring",
    category: "management_tier",
    current_technology: "SolarWinds NPM",
    target_technology: "Amazon CloudWatch + DataDog",
    migration_complexity: "medium",
    migration_priority: 5,
    migration_strategy: "replace",
    configuration: {
        monitored_devices: 150,
        retention_days: 365,
        alert_rules: 200
    },
    assessment_notes: "Monitoring solution needs complete redesign for cloud environment",
    risk_level: "medium"
});

// =====================================================================================
// CREATE RELATIONSHIPS (DEPENDENCIES)
// =====================================================================================

// Find the project node
MATCH (project:Project {id: "550e8400-e29b-41d4-a716-446655440002"})

// Find all components
MATCH (oracle_db:Component {id: "550e8400-e29b-41d4-a716-446655440004"})
MATCH (backup_db:Component {id: "comp-backup-db-001"})
MATCH (app_server_1:Component {id: "550e8400-e29b-41d4-a716-446655440005"})
MATCH (app_server_2:Component {id: "comp-app-server-002"})
MATCH (load_balancer:Component {id: "comp-load-balancer-001"})
MATCH (file_storage:Component {id: "550e8400-e29b-41d4-a716-446655440006"})
MATCH (backup_storage:Component {id: "comp-backup-storage-001"})
MATCH (firewall:Component {id: "comp-firewall-001"})
MATCH (network_switch:Component {id: "comp-network-switch-001"})
MATCH (monitoring:Component {id: "comp-monitoring-001"})

// Create project relationships
CREATE (project)-[:CONTAINS]->(oracle_db)
CREATE (project)-[:CONTAINS]->(backup_db)
CREATE (project)-[:CONTAINS]->(app_server_1)
CREATE (project)-[:CONTAINS]->(app_server_2)
CREATE (project)-[:CONTAINS]->(load_balancer)
CREATE (project)-[:CONTAINS]->(file_storage)
CREATE (project)-[:CONTAINS]->(backup_storage)
CREATE (project)-[:CONTAINS]->(firewall)
CREATE (project)-[:CONTAINS]->(network_switch)
CREATE (project)-[:CONTAINS]->(monitoring)

// Create application dependencies
CREATE (app_server_1)-[:DEPENDS_ON {type: "database_connection", criticality: "high", port: 1521}]->(oracle_db)
CREATE (app_server_2)-[:DEPENDS_ON {type: "database_connection", criticality: "high", port: 1521}]->(oracle_db)
CREATE (load_balancer)-[:ROUTES_TO {type: "http_traffic", port: 8080, health_check: true}]->(app_server_1)
CREATE (load_balancer)-[:ROUTES_TO {type: "http_traffic", port: 8080, health_check: true}]->(app_server_2)

// Create storage dependencies
CREATE (app_server_1)-[:USES {type: "file_storage", mount_point: "/shared/files"}]->(file_storage)
CREATE (app_server_2)-[:USES {type: "file_storage", mount_point: "/shared/files"}]->(file_storage)
CREATE (oracle_db)-[:BACKED_UP_TO {type: "database_backup", frequency: "daily"}]->(backup_storage)
CREATE (backup_db)-[:REPLICATES_FROM {type: "data_guard", lag_seconds: 30}]->(oracle_db)

// Create network dependencies
CREATE (load_balancer)-[:PROTECTED_BY {type: "firewall_rules"}]->(firewall)
CREATE (app_server_1)-[:CONNECTED_VIA {type: "network_connection", vlan: 100}]->(network_switch)
CREATE (app_server_2)-[:CONNECTED_VIA {type: "network_connection", vlan: 100}]->(network_switch)
CREATE (oracle_db)-[:CONNECTED_VIA {type: "network_connection", vlan: 200}]->(network_switch)

// Create monitoring relationships
CREATE (monitoring)-[:MONITORS {type: "performance", metrics: ["cpu", "memory", "disk"]}]->(oracle_db)
CREATE (monitoring)-[:MONITORS {type: "performance", metrics: ["cpu", "memory", "jvm"]}]->(app_server_1)
CREATE (monitoring)-[:MONITORS {type: "performance", metrics: ["cpu", "memory", "jvm"]}]->(app_server_2)
CREATE (monitoring)-[:MONITORS {type: "availability", check_interval: 60}]->(load_balancer)

// =====================================================================================
// CREATE ASSESSMENT NODES
// =====================================================================================

CREATE (assessment:Assessment {
    id: "550e8400-e29b-41d4-a716-446655440003",
    name: "ERP Infrastructure Assessment",
    type: "infrastructure",
    status: "in_progress",
    methodology: "6Rs",
    progress_percentage: 45.0,
    current_phase: "infrastructure_analysis",
    phases_completed: ["document_collection", "initial_discovery"],
    target_cloud: "aws",
    created_at: datetime(),
    estimated_completion: datetime() + duration({weeks: 4})
});

// Link assessment to project
MATCH (project:Project {id: "550e8400-e29b-41d4-a716-446655440002"})
MATCH (assessment:Assessment {id: "550e8400-e29b-41d4-a716-446655440003"})
CREATE (assessment)-[:ASSESSES]->(project);

// =====================================================================================
// CREATE MIGRATION STRATEGY NODES
// =====================================================================================

CREATE (rehost:Strategy {
    name: "Rehost (Lift and Shift)",
    description: "Move applications to cloud with minimal changes",
    complexity: "low",
    time_factor: 1.0,
    cost_factor: 0.8,
    risk_factor: 0.6
});

CREATE (replatform:Strategy {
    name: "Replatform",
    description: "Move to cloud with some optimization",
    complexity: "medium", 
    time_factor: 1.5,
    cost_factor: 1.2,
    risk_factor: 0.8
});

CREATE (refactor:Strategy {
    name: "Refactor/Re-architect",
    description: "Redesign application for cloud-native",
    complexity: "high",
    time_factor: 3.0,
    cost_factor: 2.0,
    risk_factor: 1.2
});

CREATE (replace:Strategy {
    name: "Replace",
    description: "Replace with cloud-native service",
    complexity: "medium",
    time_factor: 2.0,
    cost_factor: 1.5,
    risk_factor: 0.9
});

// Link components to their migration strategies
MATCH (oracle_db:Component {id: "550e8400-e29b-41d4-a716-446655440004"})
MATCH (replatform:Strategy {name: "Replatform"})
CREATE (oracle_db)-[:USES_STRATEGY]->(replatform);

MATCH (app_server_1:Component {id: "550e8400-e29b-41d4-a716-446655440005"})
MATCH (refactor:Strategy {name: "Refactor/Re-architect"})
CREATE (app_server_1)-[:USES_STRATEGY]->(refactor);

MATCH (file_storage:Component {id: "550e8400-e29b-41d4-a716-446655440006"})
MATCH (rehost:Strategy {name: "Rehost (Lift and Shift)"})
CREATE (file_storage)-[:USES_STRATEGY]->(rehost);

// =====================================================================================
// CREATE RISK ASSESSMENT NODES
// =====================================================================================

CREATE (high_risk:Risk {
    level: "high",
    description: "Significant impact on business operations",
    mitigation_required: true,
    approval_level: "executive"
});

CREATE (medium_risk:Risk {
    level: "medium", 
    description: "Moderate impact with manageable consequences",
    mitigation_required: true,
    approval_level: "management"
});

CREATE (low_risk:Risk {
    level: "low",
    description: "Minimal impact with low probability",
    mitigation_required: false,
    approval_level: "technical"
});

// Link components to risk levels
MATCH (app_server_1:Component {id: "550e8400-e29b-41d4-a716-446655440005"})
MATCH (high_risk:Risk {level: "high"})
CREATE (app_server_1)-[:HAS_RISK]->(high_risk);

MATCH (oracle_db:Component {id: "550e8400-e29b-41d4-a716-446655440004"})
MATCH (medium_risk:Risk {level: "medium"})
CREATE (oracle_db)-[:HAS_RISK]->(medium_risk);

MATCH (file_storage:Component {id: "550e8400-e29b-41d4-a716-446655440006"})
MATCH (low_risk:Risk {level: "low"})
CREATE (file_storage)-[:HAS_RISK]->(low_risk);

// =====================================================================================
// CREATE MIGRATION WAVE NODES
// =====================================================================================

CREATE (wave1:Wave {
    number: 1,
    name: "Foundation and Storage",
    description: "Establish cloud foundation and migrate low-risk storage",
    start_week: 1,
    duration_weeks: 4,
    dependencies: [],
    risk_level: "low"
});

CREATE (wave2:Wave {
    number: 2,
    name: "Database Migration",
    description: "Migrate database with minimal downtime",
    start_week: 5,
    duration_weeks: 6,
    dependencies: ["wave1"],
    risk_level: "medium"
});

CREATE (wave3:Wave {
    number: 3,
    name: "Application Modernization",
    description: "Refactor and containerize applications",
    start_week: 11,
    duration_weeks: 8,
    dependencies: ["wave2"],
    risk_level: "high"
});

// Link components to migration waves
MATCH (file_storage:Component {id: "550e8400-e29b-41d4-a716-446655440006"})
MATCH (wave1:Wave {number: 1})
CREATE (wave1)-[:INCLUDES]->(file_storage);

MATCH (oracle_db:Component {id: "550e8400-e29b-41d4-a716-446655440004"})
MATCH (wave2:Wave {number: 2})
CREATE (wave2)-[:INCLUDES]->(oracle_db);

MATCH (app_server_1:Component {id: "550e8400-e29b-41d4-a716-446655440005"})
MATCH (wave3:Wave {number: 3})
CREATE (wave3)-[:INCLUDES]->(app_server_1);

// =====================================================================================
// UTILITY QUERIES FOR VALIDATION
// =====================================================================================

// Return summary of created data
MATCH (p:Project)
OPTIONAL MATCH (p)-[:CONTAINS]->(c:Component)
OPTIONAL MATCH (a:Assessment)-[:ASSESSES]->(p)
RETURN 
    p.name as project_name,
    count(c) as component_count,
    a.name as assessment_name,
    a.status as assessment_status
ORDER BY p.name;

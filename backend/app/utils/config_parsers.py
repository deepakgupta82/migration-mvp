"""
Configuration File Parsers
Extracts detailed configuration information from various config files
"""

import re
import json
import yaml
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigurationParser:
    """Parse various configuration file formats"""
    
    def __init__(self):
        self.parsers = {
            'apache': self._parse_apache_config,
            'nginx': self._parse_nginx_config,
            'tomcat': self._parse_tomcat_config,
            'spring': self._parse_spring_config,
            'docker': self._parse_docker_config,
            'kubernetes': self._parse_kubernetes_config,
            'database': self._parse_database_config
        }
    
    def parse_configuration_files(self, project_id: str, file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Parse configuration files and extract detailed settings"""
        config_data = {
            'ports': [],
            'databases': [],
            'services': [],
            'environment_variables': {},
            'security_settings': {},
            'network_config': {},
            'resource_limits': {},
            'dependencies': []
        }
        
        for filename, content in file_contents.items():
            try:
                file_type = self._detect_config_type(filename, content)
                if file_type and file_type in self.parsers:
                    parsed_config = self.parsers[file_type](content, filename)
                    config_data = self._merge_config_data(config_data, parsed_config)
                    logger.info(f"Parsed {file_type} configuration from {filename}")
            except Exception as e:
                logger.error(f"Error parsing {filename}: {str(e)}")
        
        return config_data
    
    def _detect_config_type(self, filename: str, content: str) -> Optional[str]:
        """Detect configuration file type based on filename and content"""
        filename_lower = filename.lower()
        
        # Apache configurations
        if any(name in filename_lower for name in ['httpd.conf', 'apache.conf', '.htaccess']):
            return 'apache'
        
        # Nginx configurations
        if any(name in filename_lower for name in ['nginx.conf', 'nginx']):
            return 'nginx'
        
        # Tomcat configurations
        if any(name in filename_lower for name in ['server.xml', 'web.xml', 'context.xml']):
            return 'tomcat'
        
        # Spring Boot configurations
        if any(name in filename_lower for name in ['application.properties', 'application.yml', 'application.yaml']):
            return 'spring'
        
        # Docker configurations
        if any(name in filename_lower for name in ['dockerfile', 'docker-compose']):
            return 'docker'
        
        # Kubernetes configurations
        if filename_lower.endswith(('.yaml', '.yml')) and any(keyword in content for keyword in ['apiVersion:', 'kind:']):
            return 'kubernetes'
        
        # Database configurations
        if any(name in filename_lower for name in ['my.cnf', 'postgresql.conf', 'oracle.conf']):
            return 'database'
        
        return None
    
    def _parse_apache_config(self, content: str, filename: str) -> Dict[str, Any]:
        """Parse Apache configuration files"""
        config = {
            'ports': [],
            'virtual_hosts': [],
            'modules': [],
            'security_settings': {},
            'ssl_config': {}
        }
        
        # Extract ports
        port_matches = re.findall(r'Listen\s+(\d+)', content, re.IGNORECASE)
        config['ports'] = [int(port) for port in port_matches]
        
        # Extract virtual hosts
        vhost_pattern = r'<VirtualHost\s+([^>]+)>(.*?)</VirtualHost>'
        vhost_matches = re.findall(vhost_pattern, content, re.DOTALL | re.IGNORECASE)
        for vhost_addr, vhost_content in vhost_matches:
            server_name = re.search(r'ServerName\s+(\S+)', vhost_content, re.IGNORECASE)
            document_root = re.search(r'DocumentRoot\s+(\S+)', vhost_content, re.IGNORECASE)
            config['virtual_hosts'].append({
                'address': vhost_addr.strip(),
                'server_name': server_name.group(1) if server_name else None,
                'document_root': document_root.group(1) if document_root else None
            })
        
        # Extract loaded modules
        module_matches = re.findall(r'LoadModule\s+(\S+)', content, re.IGNORECASE)
        config['modules'] = module_matches
        
        # Extract SSL configuration
        if 'SSLEngine' in content:
            ssl_cert = re.search(r'SSLCertificateFile\s+(\S+)', content, re.IGNORECASE)
            ssl_key = re.search(r'SSLCertificateKeyFile\s+(\S+)', content, re.IGNORECASE)
            config['ssl_config'] = {
                'enabled': True,
                'certificate_file': ssl_cert.group(1) if ssl_cert else None,
                'key_file': ssl_key.group(1) if ssl_key else None
            }
        
        return config
    
    def _parse_nginx_config(self, content: str, filename: str) -> Dict[str, Any]:
        """Parse Nginx configuration files"""
        config = {
            'ports': [],
            'server_blocks': [],
            'upstream_servers': [],
            'ssl_config': {}
        }
        
        # Extract listen ports
        listen_matches = re.findall(r'listen\s+(\d+)', content, re.IGNORECASE)
        config['ports'] = [int(port) for port in listen_matches]
        
        # Extract server blocks
        server_pattern = r'server\s*{([^{}]*(?:{[^{}]*}[^{}]*)*)}'
        server_matches = re.findall(server_pattern, content, re.DOTALL)
        for server_content in server_matches:
            server_name = re.search(r'server_name\s+([^;]+)', server_content, re.IGNORECASE)
            root_dir = re.search(r'root\s+([^;]+)', server_content, re.IGNORECASE)
            config['server_blocks'].append({
                'server_name': server_name.group(1).strip() if server_name else None,
                'root': root_dir.group(1).strip() if root_dir else None
            })
        
        # Extract upstream servers
        upstream_pattern = r'upstream\s+(\S+)\s*{([^}]+)}'
        upstream_matches = re.findall(upstream_pattern, content, re.DOTALL)
        for upstream_name, upstream_content in upstream_matches:
            servers = re.findall(r'server\s+([^;]+)', upstream_content)
            config['upstream_servers'].append({
                'name': upstream_name,
                'servers': [server.strip() for server in servers]
            })
        
        return config
    
    def _parse_tomcat_config(self, content: str, filename: str) -> Dict[str, Any]:
        """Parse Tomcat configuration files"""
        config = {
            'ports': [],
            'connectors': [],
            'contexts': [],
            'datasources': []
        }
        
        try:
            root = ET.fromstring(content)
            
            # Extract connectors and ports
            for connector in root.findall('.//Connector'):
                port = connector.get('port')
                protocol = connector.get('protocol', 'HTTP/1.1')
                if port:
                    config['ports'].append(int(port))
                    config['connectors'].append({
                        'port': int(port),
                        'protocol': protocol,
                        'secure': connector.get('secure', 'false').lower() == 'true'
                    })
            
            # Extract contexts
            for context in root.findall('.//Context'):
                path = context.get('path', '/')
                doc_base = context.get('docBase')
                config['contexts'].append({
                    'path': path,
                    'doc_base': doc_base
                })
            
            # Extract datasources
            for resource in root.findall('.//Resource'):
                if resource.get('type') == 'javax.sql.DataSource':
                    config['datasources'].append({
                        'name': resource.get('name'),
                        'url': resource.get('url'),
                        'driver': resource.get('driverClassName'),
                        'username': resource.get('username')
                    })
        
        except ET.ParseError as e:
            logger.error(f"Error parsing XML in {filename}: {str(e)}")
        
        return config
    
    def _parse_spring_config(self, content: str, filename: str) -> Dict[str, Any]:
        """Parse Spring Boot configuration files"""
        config = {
            'ports': [],
            'databases': [],
            'environment_variables': {},
            'profiles': []
        }
        
        if filename.endswith('.properties'):
            # Parse properties file
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key, value = key.strip(), value.strip()
                    
                    if 'server.port' in key:
                        config['ports'].append(int(value))
                    elif 'spring.datasource' in key:
                        if 'url' in key:
                            config['databases'].append({'url': value})
                    elif 'spring.profiles.active' in key:
                        config['profiles'] = [p.strip() for p in value.split(',')]
                    
                    config['environment_variables'][key] = value
        
        elif filename.endswith(('.yml', '.yaml')):
            # Parse YAML file
            try:
                yaml_data = yaml.safe_load(content)
                if isinstance(yaml_data, dict):
                    # Extract server port
                    if 'server' in yaml_data and 'port' in yaml_data['server']:
                        config['ports'].append(yaml_data['server']['port'])
                    
                    # Extract datasource info
                    if 'spring' in yaml_data and 'datasource' in yaml_data['spring']:
                        ds = yaml_data['spring']['datasource']
                        config['databases'].append(ds)
                    
                    # Extract profiles
                    if 'spring' in yaml_data and 'profiles' in yaml_data['spring']:
                        profiles = yaml_data['spring']['profiles']
                        if 'active' in profiles:
                            config['profiles'] = profiles['active'].split(',') if isinstance(profiles['active'], str) else profiles['active']
                    
                    config['environment_variables'] = self._flatten_yaml(yaml_data)
            
            except yaml.YAMLError as e:
                logger.error(f"Error parsing YAML in {filename}: {str(e)}")
        
        return config
    
    def _parse_docker_config(self, content: str, filename: str) -> Dict[str, Any]:
        """Parse Docker configuration files"""
        config = {
            'ports': [],
            'services': [],
            'environment_variables': {},
            'volumes': [],
            'networks': []
        }
        
        if 'docker-compose' in filename.lower():
            try:
                docker_compose = yaml.safe_load(content)
                if 'services' in docker_compose:
                    for service_name, service_config in docker_compose['services'].items():
                        service_info = {'name': service_name}
                        
                        # Extract ports
                        if 'ports' in service_config:
                            for port_mapping in service_config['ports']:
                                if ':' in str(port_mapping):
                                    host_port = str(port_mapping).split(':')[0]
                                    config['ports'].append(int(host_port))
                        
                        # Extract environment variables
                        if 'environment' in service_config:
                            env_vars = service_config['environment']
                            if isinstance(env_vars, list):
                                for env_var in env_vars:
                                    if '=' in env_var:
                                        key, value = env_var.split('=', 1)
                                        config['environment_variables'][f"{service_name}.{key}"] = value
                            elif isinstance(env_vars, dict):
                                for key, value in env_vars.items():
                                    config['environment_variables'][f"{service_name}.{key}"] = value
                        
                        config['services'].append(service_info)
            
            except yaml.YAMLError as e:
                logger.error(f"Error parsing Docker Compose YAML: {str(e)}")
        
        return config
    
    def _parse_kubernetes_config(self, content: str, filename: str) -> Dict[str, Any]:
        """Parse Kubernetes configuration files"""
        config = {
            'services': [],
            'ports': [],
            'resource_limits': {},
            'environment_variables': {}
        }
        
        try:
            k8s_resources = list(yaml.safe_load_all(content))
            
            for resource in k8s_resources:
                if not resource:
                    continue
                
                kind = resource.get('kind', '')
                metadata = resource.get('metadata', {})
                spec = resource.get('spec', {})
                
                if kind == 'Service':
                    service_info = {
                        'name': metadata.get('name'),
                        'type': spec.get('type', 'ClusterIP')
                    }
                    
                    # Extract ports
                    if 'ports' in spec:
                        for port_spec in spec['ports']:
                            if 'port' in port_spec:
                                config['ports'].append(port_spec['port'])
                    
                    config['services'].append(service_info)
                
                elif kind in ['Deployment', 'StatefulSet', 'DaemonSet']:
                    # Extract resource limits
                    containers = spec.get('template', {}).get('spec', {}).get('containers', [])
                    for container in containers:
                        container_name = container.get('name')
                        resources = container.get('resources', {})
                        if resources:
                            config['resource_limits'][container_name] = resources
                        
                        # Extract environment variables
                        env_vars = container.get('env', [])
                        for env_var in env_vars:
                            key = env_var.get('name')
                            value = env_var.get('value')
                            if key and value:
                                config['environment_variables'][f"{container_name}.{key}"] = value
        
        except yaml.YAMLError as e:
            logger.error(f"Error parsing Kubernetes YAML: {str(e)}")
        
        return config
    
    def _parse_database_config(self, content: str, filename: str) -> Dict[str, Any]:
        """Parse database configuration files"""
        config = {
            'ports': [],
            'databases': [],
            'security_settings': {},
            'performance_settings': {}
        }
        
        # MySQL configuration
        if 'my.cnf' in filename.lower():
            port_match = re.search(r'port\s*=\s*(\d+)', content)
            if port_match:
                config['ports'].append(int(port_match.group(1)))
            
            # Extract key settings
            settings_patterns = {
                'max_connections': r'max_connections\s*=\s*(\d+)',
                'innodb_buffer_pool_size': r'innodb_buffer_pool_size\s*=\s*(\S+)',
                'query_cache_size': r'query_cache_size\s*=\s*(\S+)'
            }
            
            for setting, pattern in settings_patterns.items():
                match = re.search(pattern, content)
                if match:
                    config['performance_settings'][setting] = match.group(1)
        
        # PostgreSQL configuration
        elif 'postgresql.conf' in filename.lower():
            port_match = re.search(r'port\s*=\s*(\d+)', content)
            if port_match:
                config['ports'].append(int(port_match.group(1)))
            
            # Extract key settings
            settings_patterns = {
                'max_connections': r'max_connections\s*=\s*(\d+)',
                'shared_buffers': r'shared_buffers\s*=\s*(\S+)',
                'effective_cache_size': r'effective_cache_size\s*=\s*(\S+)'
            }
            
            for setting, pattern in settings_patterns.items():
                match = re.search(pattern, content)
                if match:
                    config['performance_settings'][setting] = match.group(1)
        
        return config
    
    def _merge_config_data(self, base_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration data from multiple sources"""
        for key, value in new_config.items():
            if key in base_config:
                if isinstance(base_config[key], list) and isinstance(value, list):
                    base_config[key].extend(value)
                elif isinstance(base_config[key], dict) and isinstance(value, dict):
                    base_config[key].update(value)
                else:
                    base_config[key] = value
            else:
                base_config[key] = value
        
        return base_config
    
    def _flatten_yaml(self, data: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten nested YAML structure"""
        items = []
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            if isinstance(value, dict):
                items.extend(self._flatten_yaml(value, new_key, sep=sep).items())
            else:
                items.append((new_key, value))
        return dict(items)

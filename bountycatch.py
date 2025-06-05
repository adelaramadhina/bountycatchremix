import argparse
import redis
import os
import json
import logging
import re
from datetime import datetime
from typing import Optional, Set, Dict, Any
from pathlib import Path

class DataStore:
    def __init__(self, host='localhost', port=6379, db=0, max_connections=10):
        self.pool = redis.ConnectionPool(
            host=host, port=port, db=db, max_connections=max_connections
        )
        self.r = redis.Redis(connection_pool=self.pool)
        self.logger = logging.getLogger(__name__)
        
        try:
            self.r.ping()
            self.logger.info(f"Connected to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise

    def add_domain(self, project: str, domain: str) -> int:
        try:
            return self.r.sadd(project, domain)
        except redis.RedisError as e:
            self.logger.error(f"Failed to add domain {domain} to project {project}: {e}")
            raise

    def get_domains(self, project: str) -> Set[bytes]:
        try:
            return self.r.smembers(project)
        except redis.RedisError as e:
            self.logger.error(f"Failed to get domains for project {project}: {e}")
            raise

    def deduplicate(self, project):
        return True

    def delete_project(self, project: str) -> int:
        try:
            return self.r.delete(project)
        except redis.RedisError as e:
            self.logger.error(f"Failed to delete project {project}: {e}")
            raise
    
    def project_exists(self, project: str) -> bool:
        try:
            return bool(self.r.exists(project))
        except redis.RedisError as e:
            self.logger.error(f"Failed to check if project {project} exists: {e}")
            raise

    def count_domains(self, project: str) -> int:
        try:
            return self.r.scard(project)
        except redis.RedisError as e:
            self.logger.error(f"Failed to count domains for project {project}: {e}")
            raise

class DomainValidator:
    
    
    DOMAIN_PATTERN = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)'
        r'+[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    )
    
    @classmethod
    def is_valid_domain(cls, domain: str) -> bool:
        if not domain or len(domain) > 253:
            return False
        return bool(cls.DOMAIN_PATTERN.match(domain))

class ConfigManager:
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.logger = logging.getLogger(__name__)
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        default_config = {
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'max_connections': 10
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    for section, values in file_config.items():
                        if section in default_config:
                            default_config[section].update(values)
                        else:
                            default_config[section] = values
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to load config file {config_file}: {e}")
        
        redis_host = os.getenv('REDIS_HOST')
        if redis_host:
            default_config['redis']['host'] = redis_host
        
        redis_port = os.getenv('REDIS_PORT')
        if redis_port:
            try:
                default_config['redis']['port'] = int(redis_port)
            except ValueError:
                logging.warning(f"Invalid REDIS_PORT value: {redis_port}")
        
        return default_config
    
    def get_redis_config(self) -> Dict[str, Any]:
        return self.config['redis']
    
    def get_logging_config(self) -> Dict[str, Any]:
        return self.config['logging']

class Project:
    def __init__(self, datastore, name: str):
        self.datastore = datastore
        self.name = name
        self.logger = logging.getLogger(__name__)
    
    def export_domains(self, output_file: str, format_type: str = 'text') -> bool:
        try:
            domains = self.get_domains()
            if not domains:
                self.logger.warning(f"No domains found in project '{self.name}'")
                return False
            
            output_path = Path(output_file)
            
            if format_type.lower() == 'json':
                export_data = {
                    'project': self.name,
                    'domain_count': len(domains),
                    'exported_at': str(datetime.now().isoformat()),
                    'domains': sorted(list(domains))
                }
                
                with open(output_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
                    
            elif format_type.lower() == 'text':
                with open(output_path, 'w') as f:
                    for domain in sorted(domains):
                        f.write(f"{domain}\n")
            else:
                self.logger.error(f"Unsupported export format: {format_type}")
                return False
            
            self.logger.info(f"Exported {len(domains)} domains to {output_file} ({format_type} format)")
            return True
            
        except (IOError, json.JSONEncodeError) as e:
            self.logger.error(f"Failed to export domains: {e}")
            return False

    def add_domains_from_file(self, filename: str, validate: bool = True) -> None:
        file_path = Path(filename)
        if not file_path.exists():
            self.logger.error(f"File {filename} does not exist")
            return
        
        try:
            with open(file_path, 'r') as file:
                total_domains = 0
                new_domains = 0
                invalid_domains = 0
                
                for line_num, line in enumerate(file, 1):
                    domain = line.strip()
                    if not domain:
                        continue
                    
                    if validate and not DomainValidator.is_valid_domain(domain):
                        self.logger.warning(f"Invalid domain '{domain}' on line {line_num}, skipping")
                        invalid_domains += 1
                        continue
                    
                    try:
                        added = self.datastore.add_domain(self.name, domain)
                        new_domains += added
                        total_domains += 1
                    except redis.RedisError as e:
                        self.logger.error(f"Failed to add domain '{domain}': {e}")
                
                duplicate_domains = total_domains - new_domains
                duplicate_percentage = (duplicate_domains / total_domains * 100) if total_domains > 0 else 0
                
                self.logger.info(
                    f"Processed {total_domains} domains: {new_domains} new, "
                    f"{duplicate_domains} duplicates ({duplicate_percentage:.2f}%)"
                )
                if invalid_domains > 0:
                    self.logger.warning(f"Skipped {invalid_domains} invalid domains")
                    
        except IOError as e:
            self.logger.error(f"Failed to read file {filename}: {e}")

    def get_domains(self) -> Set[str]:
        try:
            raw_domains = self.datastore.get_domains(self.name)
            return {domain.decode('utf-8') for domain in raw_domains}
        except redis.RedisError as e:
            self.logger.error(f"Failed to get domains: {e}")
            return set()
    
    def count_domains(self) -> Optional[int]:
        try:
            if not self.datastore.project_exists(self.name):
                self.logger.error(f"Project '{self.name}' does not exist")
                return None
            
            count = self.datastore.count_domains(self.name)
            self.logger.info(f"Project '{self.name}' contains {count} domains")
            return count
        except redis.RedisError as e:
            self.logger.error(f"Failed to count domains: {e}")
            return None

    def deduplicate(self) -> bool:
        return self.datastore.deduplicate(self.name)
    
    def delete(self) -> bool:
        try:
            self.logger.info(f"Attempting to delete project '{self.name}'")
            deleted_count = self.datastore.delete_project(self.name)
            
            if deleted_count == 0:
                self.logger.warning(f"Project '{self.name}' did not exist")
                return False
            else:
                self.logger.info(f"Project '{self.name}' deleted successfully")
                return True
        except redis.RedisError as e:
            self.logger.error(f"Failed to delete project: {e}")
            return False

def setup_logging(config: ConfigManager) -> None:
    logging_config = config.get_logging_config()
    
    logging.basicConfig(
        level=getattr(logging, logging_config['level']),
        format=logging_config['format'],
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bountycatch.log')
        ]
    )

def main():
    parser = argparse.ArgumentParser(
        description="Manage bug bounty targets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s add -p myproject -f domains.txt
  %(prog)s export -p myproject -f output.json --format json
  %(prog)s count -p myproject
  %(prog)s delete -p myproject
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    add_parser = subparsers.add_parser('add', help='Add domains from file')
    add_parser.add_argument('-p', '--project', required=True, help='Project name')
    add_parser.add_argument('-f', '--file', required=True, help='File containing domains')
    add_parser.add_argument('--no-validate', action='store_true', help='Skip domain validation')
    
    export_parser = subparsers.add_parser('export', help='Export domains to file')
    export_parser.add_argument('-p', '--project', required=True, help='Project name')
    export_parser.add_argument('-f', '--file', required=True, help='Output file')
    export_parser.add_argument('--format', choices=['text', 'json'], default='text', help='Export format')
    
    print_parser = subparsers.add_parser('print', help='Print all domains')
    print_parser.add_argument('-p', '--project', required=True, help='Project name')
    
    count_parser = subparsers.add_parser('count', help='Count domains in project')
    count_parser.add_argument('-p', '--project', required=True, help='Project name')
    
    delete_parser = subparsers.add_parser('delete', help='Delete project')
    delete_parser.add_argument('-p', '--project', required=True, help='Project name')
    delete_parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    parser.add_argument('-c', '--config', help='Configuration file path')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    config = ConfigManager(args.config)
    
    if args.verbose:
        config.config['logging']['level'] = 'DEBUG'
    
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    try:
        redis_config = config.get_redis_config()
        datastore = DataStore(**redis_config)
        project = Project(datastore, args.project)
        
    except redis.ConnectionError:
        logger.error("Failed to connect to Redis. Please check your Redis server is running.")
        return 1
    except Exception as e:
        logger.error(f"Initialisation error: {e}")
        return 1

    if args.command == 'add':
        validate = not args.no_validate
        project.add_domains_from_file(args.file, validate=validate)
        project.deduplicate()
        
    elif args.command == 'export':
        if not project.export_domains(args.file, args.format):
            return 1
            
    elif args.command == 'print':
        domains = project.get_domains()
        if not domains:
            logger.warning(f"No domains found in project '{args.project}'")
        else:
            for domain in sorted(domains):
                print(domain)
                
    elif args.command == 'count':
        count = project.count_domains()
        if count is not None:
            print(f"{count}")
        else:
            return 1
            
    elif args.command == 'delete':
        if not args.confirm:
            response = input(f"Are you sure you want to delete project '{args.project}'? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                logger.info("Delete operation cancelled")
                return 0
        
        if project.delete():
            print(f"Project '{args.project}' deleted successfully")
        else:
            return 1
    
    return 0

if __name__ == '__main__':
    try:
        exit_code = main()
        exit(exit_code or 0)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        exit(1)

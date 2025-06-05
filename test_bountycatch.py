#!/usr/bin/env python3
"""
Unit tests for BountyCatch domain management tool
"""

import unittest
import tempfile
import json
import os
import logging
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import our modules
from bountycatch import DataStore, Project, DomainValidator, ConfigManager


class TestDomainValidator(unittest.TestCase):
    """Test domain validation functionality"""
    
    def test_valid_domains(self):
        """Test valid domain names"""
        valid_domains = [
            'example.com',
            'subdomain.example.com',
            'test-domain.co.uk',
            'a.b.c.d.example.org',
            '123domain.com',
            'domain123.net'
        ]
        
        for domain in valid_domains:
            with self.subTest(domain=domain):
                self.assertTrue(DomainValidator.is_valid_domain(domain))
    
    def test_invalid_domains(self):
        """Test invalid domain names"""
        invalid_domains = [
            '',
            'invalid_domain.com',  # underscore not allowed
            'domain-.com',  # trailing hyphen
            '-domain.com',  # leading hyphen
            'domain..com',  # double dot
            'a' * 255,  # too long
            'just-text',  # no TLD
            '.example.com',  # leading dot
            'example.com.',  # trailing dot (simplified for this test)
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.assertFalse(DomainValidator.is_valid_domain(domain))


class TestConfigManager(unittest.TestCase):
    """Test configuration management"""
    
    def test_default_config(self):
        """Test default configuration loading"""
        config = ConfigManager()
        redis_config = config.get_redis_config()
        
        self.assertEqual(redis_config['host'], 'localhost')
        self.assertEqual(redis_config['port'], 6379)
        self.assertEqual(redis_config['db'], 0)
    
    def test_config_file_loading(self):
        """Test loading configuration from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_config = {
                'redis': {
                    'host': 'test-redis',
                    'port': 6380,
                    'db': 1
                }
            }
            json.dump(test_config, f)
            config_file = f.name
        
        try:
            config = ConfigManager(config_file)
            redis_config = config.get_redis_config()
            
            self.assertEqual(redis_config['host'], 'test-redis')
            self.assertEqual(redis_config['port'], 6380)
            self.assertEqual(redis_config['db'], 1)
        finally:
            os.unlink(config_file)
    
    @patch.dict(os.environ, {'REDIS_HOST': 'env-redis', 'REDIS_PORT': '6381'})
    def test_environment_override(self):
        """Test environment variable override"""
        config = ConfigManager()
        redis_config = config.get_redis_config()
        
        self.assertEqual(redis_config['host'], 'env-redis')
        self.assertEqual(redis_config['port'], 6381)


class TestDataStore(unittest.TestCase):
    """Test DataStore functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_redis = Mock()
        
        # Mock the connection pool and Redis client
        with patch('bountycatch.redis.ConnectionPool') as mock_pool:
            with patch('bountycatch.redis.Redis') as mock_redis_class:
                mock_redis_class.return_value = self.mock_redis
                self.mock_redis.ping.return_value = True
                
                self.datastore = DataStore()
    
    def test_add_domain(self):
        """Test adding a domain"""
        self.mock_redis.sadd.return_value = 1
        
        result = self.datastore.add_domain('test-project', 'example.com')
        
        self.assertEqual(result, 1)
        self.mock_redis.sadd.assert_called_once_with('test-project', 'example.com')
    
    def test_get_domains(self):
        """Test getting domains"""
        mock_domains = {b'example.com', b'test.com'}
        self.mock_redis.smembers.return_value = mock_domains
        
        result = self.datastore.get_domains('test-project')
        
        self.assertEqual(result, mock_domains)
        self.mock_redis.smembers.assert_called_once_with('test-project')
    
    def test_project_exists(self):
        """Test checking if project exists"""
        self.mock_redis.exists.return_value = 1
        
        result = self.datastore.project_exists('test-project')
        
        self.assertTrue(result)
        self.mock_redis.exists.assert_called_once_with('test-project')
    
    def test_count_domains(self):
        """Test counting domains"""
        self.mock_redis.scard.return_value = 5
        
        result = self.datastore.count_domains('test-project')
        
        self.assertEqual(result, 5)
        self.mock_redis.scard.assert_called_once_with('test-project')
    
    def test_delete_project(self):
        """Test deleting a project"""
        self.mock_redis.delete.return_value = 1
        
        result = self.datastore.delete_project('test-project')
        
        self.assertEqual(result, 1)
        self.mock_redis.delete.assert_called_once_with('test-project')


class TestProject(unittest.TestCase):
    """Test Project functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_datastore = Mock()
        self.project = Project(self.mock_datastore, 'test-project')
    
    def test_get_domains(self):
        """Test getting domains from project"""
        mock_raw_domains = {b'example.com', b'test.com'}
        self.mock_datastore.get_domains.return_value = mock_raw_domains
        
        result = self.project.get_domains()
        
        expected = {'example.com', 'test.com'}
        self.assertEqual(result, expected)
    
    def test_count_domains_success(self):
        """Test successful domain counting"""
        self.mock_datastore.project_exists.return_value = True
        self.mock_datastore.count_domains.return_value = 10
        
        result = self.project.count_domains()
        
        self.assertEqual(result, 10)
    
    def test_count_domains_nonexistent_project(self):
        """Test counting domains for non-existent project"""
        self.mock_datastore.project_exists.return_value = False
        
        result = self.project.count_domains()
        
        self.assertIsNone(result)
    
    def test_delete_success(self):
        """Test successful project deletion"""
        self.mock_datastore.delete_project.return_value = 1
        
        result = self.project.delete()
        
        self.assertTrue(result)
    
    def test_delete_nonexistent(self):
        """Test deleting non-existent project"""
        self.mock_datastore.delete_project.return_value = 0
        
        result = self.project.delete()
        
        self.assertFalse(result)
    
    def test_add_domains_from_file(self):
        """Test adding domains from file"""
        # Create a temporary file with test domains
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('example.com\n')
            f.write('test.com\n')
            f.write('invalid_domain\n')  # Invalid domain
            f.write('\n')  # Empty line
            temp_file = f.name
        
        try:
            self.mock_datastore.add_domain.return_value = 1
            
            self.project.add_domains_from_file(temp_file, validate=True)
            
            # Should be called twice (for valid domains only)
            self.assertEqual(self.mock_datastore.add_domain.call_count, 2)
        finally:
            os.unlink(temp_file)
    
    def test_export_domains_text(self):
        """Test exporting domains to text file"""
        self.mock_datastore.get_domains.return_value = {b'example.com', b'test.com'}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_file = f.name
        
        try:
            result = self.project.export_domains(temp_file, 'text')
            
            self.assertTrue(result)
            
            # Check file contents
            with open(temp_file, 'r') as f:
                content = f.read()
                self.assertIn('example.com', content)
                self.assertIn('test.com', content)
        finally:
            os.unlink(temp_file)
    
    def test_export_domains_json(self):
        """Test exporting domains to JSON file"""
        self.mock_datastore.get_domains.return_value = {b'example.com', b'test.com'}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_file = f.name
        
        try:
            result = self.project.export_domains(temp_file, 'json')
            
            self.assertTrue(result)
            
            # Check file contents
            with open(temp_file, 'r') as f:
                data = json.load(f)
                self.assertEqual(data['project'], 'test-project')
                self.assertEqual(data['domain_count'], 2)
                self.assertIn('example.com', data['domains'])
                self.assertIn('test.com', data['domains'])
        finally:
            os.unlink(temp_file)


class TestIntegration(unittest.TestCase):
    """Integration tests with mocked Redis"""
    
    @patch('bountycatch.redis.Redis')
    @patch('bountycatch.redis.ConnectionPool')
    def test_full_workflow(self, mock_pool, mock_redis_class):
        """Test a complete workflow"""
        # Mock Redis behaviour
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.ping.return_value = True
        mock_redis.sadd.return_value = 1
        mock_redis.smembers.return_value = {b'example.com', b'test.com'}
        mock_redis.scard.return_value = 2
        mock_redis.exists.return_value = True
        mock_redis.delete.return_value = 1
        
        # Create datastore and project
        datastore = DataStore()
        project = Project(datastore, 'test-project')
        
        # Test adding domains
        result = project.datastore.add_domain('test-project', 'example.com')
        self.assertEqual(result, 1)
        
        # Test getting domains
        domains = project.get_domains()
        self.assertEqual(domains, {'example.com', 'test.com'})
        
        # Test counting
        count = project.count_domains()
        self.assertEqual(count, 2)
        
        # Test deletion
        deleted = project.delete()
        self.assertTrue(deleted)


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)
    
    # Run tests
    unittest.main(verbosity=2)
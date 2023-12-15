import argparse
import redis
import os

class DataStore:
    def __init__(self, host='localhost', port=6379, db=0):
        self.r = redis.Redis(host=host, port=port, db=db)

    def add_domain(self, project, domain):
        return self.r.sadd(project, domain)

    def get_domains(self, project):
        return self.r.smembers(project)

    def deduplicate(self, project):
        pass

    def delete_project(self, project):
        return self.r.delete(project)
    
    def project_exists(self, project):
        return self.r.exists(project)

    def count_domains(self, project):
        return self.r.scard(project)  # SCARD command returns the set count

class Project:
    def __init__(self, datastore, name):
        self.datastore = datastore
        self.name = name

    def add_domains_from_file(self, filename):
        if not os.path.exists(filename):
            print("File {} does not exist.".format(filename))
            return
        with open(filename, 'r') as file:
            total_domains = 0
            new_domains = 0
            for line in file:
                domain = line.strip()
                if domain:  # Check if the domain is not empty
                    added = self.datastore.add_domain(self.name, domain)
                    new_domains += added
                total_domains += 1 if domain else 0  # Only count non-empty lines as total domains
            duplicate_domains = total_domains - new_domains
            if total_domains > 0:
                duplicate_percentage = (duplicate_domains / total_domains) * 100
            else:
                duplicate_percentage = 0
            print("{} out of {} domains were duplicates ({:.2f}%).".format(duplicate_domains, total_domains, duplicate_percentage))

    def get_domains(self):
        return self.datastore.get_domains(self.name)
    
    def count_domains(self):
        if not self.datastore.project_exists(self.name):
            print(f"Error: Project '{self.name}' does not exist.")
            return
        count = self.datastore.count_domains(self.name)
        print(f"There are {count} domains in the project '{self.name}'.")

    def deduplicate(self):
        self.datastore.deduplicate(self.name)
    
    def delete(self):
        print(f"Attempting to delete project '{self.name}'...")
        deleted_count = self.datastore.delete_project(self.name)
        if deleted_count == 0:
            print(f"No such project '{self.name}' to delete.")
        else:
            print(f"Project '{self.name}' deleted successfully.")

def main():
    parser = argparse.ArgumentParser(description="Manage bug bounty targets")
    parser.add_argument('-p', '--project', required=True, help='The project name')
    parser.add_argument('-f', '--file', help='The file containing domains')
    parser.add_argument('-o', '--operation', required=True, choices=['add', 'print', 'delete', 'count'], help='Operation to perform')
    args = parser.parse_args()

    datastore = DataStore()
    project = Project(datastore, args.project)

    def add_operation():
        if args.file is None:
            print("You must provide a file with the 'add' operation.")
            return
        project.add_domains_from_file(args.file)
        project.deduplicate()

    def print_operation():
        domains = project.get_domains()
        for domain in domains:
            print(domain.decode('utf-8'))

    def delete_operation():
        print("Attempting to delete project...")
        print("Checking Redis connection...")
        try:
            datastore.r.ping()
            print("Redis is connected!")
        except redis.ConnectionError:
            print("Failed to connect to Redis.")
            return
        project.delete()

    def count_operation():
        project.count_domains()

    operations = {
        'add': add_operation,
        'print': print_operation,
        'delete': delete_operation,
        'count': count_operation
    }

    operation_function = operations.get(args.operation)
    if operation_function:
        operation_function()
    else:
        print(f"Invalid operation: {args.operation}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")

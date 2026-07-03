from typing import Optional
import requests
from src.tools.helper import Config


class APICaller:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def health_check(self):
        """Check if the server is running"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200, response.json()
        except Exception as e:
            return False, str(e)
    
    def create_docker_container(self, container_name, src_dir, ins_id, image_name="spider_agent-image", working_dir="/workspace", kwargs=None):
        """Create or get Docker environment"""
        if kwargs is None:
            kwargs = {}
        
        data = {
            "container_name": container_name,
            "image_name": image_name,
            "src_dir": src_dir,
            "ins_id": ins_id,
            "working_dir": working_dir,
            "kwargs": kwargs
        }
        
        response = self.session.post(f"{self.base_url}/api/get_docker_env", json=data)
        return response.status_code, response.json()
    
    def get_docker_container(self, container_name):
        data = {
            "container_name": container_name
        }
        response = self.session.post(f"{self.base_url}/api/get_docker_env", json=data)
        return response.status_code, response.json()
    
    def execute_action(self, container_name: str, action: str, other_data: Optional[dict] = None):
        """Execute action in container"""
        data = {
            "container_name": container_name,
            "action": action,
            "other_data": other_data
        }
        
        response = self.session.post(f"{self.base_url}/api/execute_action", json=data)
        return response.status_code, response.json()
    
    def list_containers(self):
        """List all containers"""
        response = self.session.get(f"{self.base_url}/api/containers")
        return response.status_code, response.json()
    
    def delete_container(self, container_name):
        """Delete a container"""
        response = self.session.delete(f"{self.base_url}/api/containers/{container_name}")
        return response.status_code, response.json()
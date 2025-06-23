import json
import time
import logging
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner
import docker
import base64
from datetime import datetime
import csv
import os
import sys
import threading
import logging
import signal
from config import JFROG_URL, USERNAME, PASSWORD, REPO_NAME, IMAGE_NAME, print_config


# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Signal handler for Ctrl+C
def signal_handler(sig, frame):
    logging.debug("Signal received, shutting down")
    if hasattr(sys, 'locust_environment') and sys.locust_environment.runner:
        logging.info("Stopping Locust runner to trigger on_stop for all users")
        sys.locust_environment.runner.quit()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Configuration
#JFROG_URL = "https://trialvq0712.jfrog.io"
#USERNAME = "perftest"  # Replace with your admin username
#PASSWORD = "PerfTest123$"  # Replace with your password
#REPO_NAME = "docker-local"
#IMAGE_NAME = "alpine:3.9"
# CUSTOM_TAG = "test"

# Metrics storage
metrics_data = []

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        logging.info("Master node initialized")
        if not hasattr(sys, "master_reports"):
            sys.master_reports = {}
        environment.runner.register_message("metrics_report", handle_metrics_report)
    elif isinstance(environment.runner, WorkerRunner):
        logging.info("Worker node initialized")
    else:
        logging.info("Local runner initialized")
    sys.locust_environment = environment  # Store environment for signal handler   
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate unified report at test completion"""
    if isinstance(environment.runner, MasterRunner):
        logging.info("Test stopped on master, generating unified report")
        all_metrics = []
        if hasattr(sys, "master_reports"):
            for worker_id, worker_metrics in sys.master_reports.items():
                all_metrics.extend(worker_metrics)
        else:
            logging.warning("No master_reports attribute found on sys module")
            all_metrics = []        
        
        if not all_metrics:
            logging.warning("No metrics data to write to CSV")
            return

        start_time = datetime.now()
        output_file = f"performance_report_{start_time.strftime('%Y%m%d_%H%M%S')}.csv"

        try:
            with open(output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "operation", "response_time", "status"])
                writer.writeheader()
                writer.writerows(all_metrics)
            logging.info(f"Unified report generated: {output_file}")
        except Exception as e:
            logging.error(f"Failed to generate report: {str(e)}")
            
def handle_metrics_report(environment, msg, **kwargs):
    """Master handler for worker metrics reports"""
    worker_id = msg.data["worker_id"]
    worker_metrics = msg.data["metrics"]
    sys.master_reports[worker_id] = worker_metrics
    logging.info(f"Received metrics from worker {worker_id} ({len(worker_metrics)} entries)")

class JFrogXrayUser(HttpUser):
    wait_time = between(1, 5)
    host = JFROG_URL
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_header = {
            "Authorization": f"Basic {base64.b64encode(f'{USERNAME}:{PASSWORD}'.encode()).decode()}"
        }
        self.docker_client = docker.from_env()
        self.start_time = datetime.now()

    def on_start(self):
        """Setup initial configuration"""
        try:
            self.setup_docker()
            self.create_repository()
            self.create_policy()
            self.policy_name = None
            self.watch_name = None
        except Exception as e:
            logging.error(f"Setup failed: {str(e)}")
            self.environment.runner.quit()

    def setup_docker(self):
        """Setup Docker environment"""
        try:
            # Login to JFrog Docker registry
            self.docker_client.login(
                username=USERNAME,
                password=PASSWORD,
                registry=JFROG_URL.replace("https://", "")
            )
        except Exception as e:
            logging.error(f"Docker setup failed: {str(e)}")
            raise

    @task(1)
    def create_repository(self):
        """Create Docker repository"""
        unique_repo_key = f"docker-local-{int(time.time())}-{self.environment.runner.user_count}"
        repo_config = {
            "key": unique_repo_key,
            "projectKey": "",
            "packageType": "docker",
            "rclass": "local",
            "xrayIndex": True
        }
        
        with self.client.put(
            f"/artifactory/api/repositories/{unique_repo_key}",
            json=repo_config,
            headers=self.auth_header,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "create_repository",
                    "response_time": response.request_meta["response_time"],
                    "status": "success"
                })
                self.repo_key = unique_repo_key
            else:
                response.failure(f"Failed to create repository: {response.text}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "create_repository",
                    "response_time": response.request_meta["response_time"],
                    "status": "failed"
                })

    @task(2)
    def push_docker_image(self):
        """Push Docker image to repository"""
        try:
            if not hasattr(self, 'repo_key') or not self.repo_key:
                logging.error("Repository key not set. Ensure create_repository is called successfully first.")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "push_image",
                    "response_time": 0,
                    "status": "failed",
                    "errors": ["No repository key set"]
                })
                return
            logging.debug(f"Pulling image: {IMAGE_NAME}")
            image = self.docker_client.images.pull(IMAGE_NAME)
            tagged_image = f"{JFROG_URL.replace('https://', '')}/{self.repo_key}/{IMAGE_NAME.split(':')[0]}:3.9"
            image.tag(tagged_image)

            # Push the image
            logging.debug(f"Pushing image: {tagged_image}")
            push_log = self.docker_client.images.push(tagged_image, stream=True, decode=True)
            errors = []
            for line in push_log:
                if 'error' in line:
                    errors.append(line['error'])
                    logging.error(f"Docker push error: {line['error']}")

            if not errors:
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "push_image",
                    "status": "success"
                })
            else:
                logging.error(f"Failed to push image: {tagged_image}. Errors: {errors}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "push_image",
                    "status": "failed",
                    "errors": errors
                })
        except docker.errors.APIError as e:
                logging.error(f"Docker API error during push: {str(e)}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "push_image",
                    "response_time": 0,
                    "status": "failed",
                    "errors": [str(e)]
                })
        except Exception as e:
                logging.error(f"Unexpected error during push: {str(e)}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "push_image",
                    "response_time": 0,
                    "status": "failed",
                    "errors": [str(e)]
                })

    @task(3)
    def create_policy(self):
        """Create security policy"""
        policy_name = f"sec_policy_{threading.get_ident()}_{int(time.time() * 1000)}" 
        policy_config = {
            "name": policy_name,
            "description": "Test security policy",
            "type": "security",
            "rules": [{
                "name": "test_rule",
                "criteria": {
                    "malicious_package": False,
                    "fix_version_dependant": False,
                    "min_severity": "high"
                },
                "actions": {
                    "mails": [],
                    "webhooks": [],
                    "fail_build": False,
                    "block_release_bundle_distribution": False,
                    "block_release_bundle_promotion": False,
                    "notify_deployer": False,
                    "notify_watch_recipients": False,
                    "create_ticket_enabled": False,
                    "block_download": {
                        "active": False,
                        "unscanned": False
                    }
                },
                "priority": 1
            }]
        }
        
        with self.client.post(
            "/xray/api/v2/policies",
            json=policy_config,
            headers=self.auth_header,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
                self.policy_name = policy_name
                logging.debug(f"Policy created: {policy_name}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "create_policy",
                    "response_time": response.request_meta["response_time"],
                    "status": "success"
                })
                return policy_name
            else:
                response.failure(f"Failed to create policy: {response.text}")
                logging.error(f"Policy creation failed: {response.text}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "create_policy",
                    "response_time": response.request_meta["response_time"],
                    "status": "failed"
                })

    @task(4)
    def create_watch(self):
        """Create watch for repository"""
        if not hasattr(self, "policy_name") or not self.policy_name:
            logging.error("Policy name not set. Ensure create_policy is called successfully first.")
            metrics_data.append({
                "timestamp": datetime.now().isoformat(),
                "operation": "create_watch",
                "response_time": 0,
                "status": "failed"
            })
            return None
        watch_name = f"watch_{threading.get_ident()}_{int(time.time() * 1000)}"
        watch_config = {
            "general_data": {
                "name": watch_name,
                "description": "Test watch",
                "active": True
            },
            "project_resources": {
                "resources": [{
                    "type": "repository",
                    "bin_mgr_id": "default",
                    "name": self.repo_key,
                    "filters": []
                }]
            },
            "assigned_policies": [
            {
                "name": self.policy_name,
                "type": "security" 
            }
        ]
    }
        
        with self.client.post(
            "/xray/api/v2/watches",
            json=watch_config,
            headers=self.auth_header,
            catch_response=True
        ) as response:
            if response.status_code in (200, 201):
                response.success()
                logging.debug(f"Watch {watch_name} created successfully")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "create_watch",
                    "response_time": response.request_meta["response_time"],
                    "status": "success"
                })
                self.watch_name = watch_name
                return watch_name
            else:
                response.failure(f"Failed to create watch: {response.text}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "create_watch",
                    "response_time": response.request_meta["response_time"],
                    "status": "failed"
                })

    @task(5)
    def check_scan_status(self):
        """Check scan status"""
        with self.client.post(
            "/xray/api/v1/artifact/status",
            json={"repo": self.repo_key, "path": f"/alpine/3.9/manifest.json"},
            headers=self.auth_header,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "check_scan_status",
                    "response_time": response.request_meta["response_time"],
                    "status": "success"
                })
            else:
                response.failure(f"Scan not complete or failed: {response.text}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "check_scan_status",
                    "response_time": response.request_meta["response_time"],
                    "status": "failed"
                })

    @task(6)
    def get_violations(self):
        """Get security violations"""
        violation_config = {
            "filters": {
                "watch_name": self.watch_name,
                "violation_type": "Security",
                "min_severity": "High",
                "resources": {
                    "artifacts": [{
                        "repo": self.repo_key,
                        "path": "alpine/3.9/manifest.json"
                    }]
                },
                "pagination": {
                    "order_by": "created",
                    "direction": "asc",
                    "limit": 100,
                    "offset": 1
                }
            }
        }
        
        with self.client.post(
            "/xray/api/v1/violations",
            json=violation_config,
            headers=self.auth_header,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "get_violations",
                    "response_time": response.request_meta["response_time"],
                    "status": "success"
                })
            else:
                response.failure(f"Failed to get violations: {response.text}")
                metrics_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "operation": "get_violations",
                    "response_time": response.request_meta["response_time"],
                    "status": "failed"
                })

    def on_stop(self):
        """Send metrics to master at user completion"""
        if isinstance(self.environment.runner, WorkerRunner):
            worker_id = self.environment.runner.worker_index
            logging.info(f"Worker {worker_id} sending {len(metrics_data)} metrics to master")
            self.environment.runner.send_message("metrics_report", {
                "worker_id": worker_id,
                "metrics": metrics_data.copy()
            })
        metrics_data.clear()  # Clear local metrics after reporting


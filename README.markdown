# JFrog Artifactory Performance Testing with Locust

This project uses [Locust](https://locust.io/) to perform load testing on JFrog Artifactory and Xray APIs, simulating repository creation, Docker image pushes, security policy creation, and watch configuration. The test generates a performance report (`performance_report_YYYYMMDD_HHMMSS.csv`) with configuration parameters, metrics, and errors, along with visualizations and analysis in `analysis.md`.

## Project Structure
- `locustfile.py`: Defines Locust tasks for testing JFrog APIs.
- `config.py`: Configuration file with JFrog URL, credentials, and test parameters.
- `analyze_report.py`: Analyzes the CSV report and generates visualizations (`response_time.png`, `failure_counts.png`) and a metrics summary (`metrics_summary.txt`).
- `analysis.md`: Documents observations and recommendations based on test results.
- `performance_report_YYYYMMDD_HHMMSS.csv`: Output report with test configuration and performance metrics.
- `requirements.txt`: Lists Python dependencies.

## Prerequisites
- **Python**: 3.8+
- **Docker**: Installed and running, with access to `alpine:3.9`.
- **JFrog Artifactory**: Access to a Pro-X or higher instance (e.g., `https://trialvq0712.jfrog.io`) with valid credentials.
- **Dependencies**:
  ```bash
  pip install -r requirements.txt
  ```
- **Docker Login**:
  ```bash
  docker login trialvq0712.jfrog.io -u <USERNAME> -p <PASSWORD>
  docker pull alpine:3.9
  ```

## Setup
1. **Clone the Repository**:
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Configure `config.py`**:
   Edit `config.py` with your JFrog instance details:
   ```python
   # config.py
   JFROG_URL = "https://trialvq0712.jfrog.io"
   USERNAME = "your_username"
   PASSWORD = "your_password"
   REPO_NAME = "docker-local"
   IMAGE_NAME = "alpine:3.9"
   CUSTOM_TAG = "test"
   ```

3. **Install Dependencies**:
   ```bash
   pip install locust>=2.0.0 docker>=6.0.0 pandas matplotlib seaborn
   ```

4. **Verify Permissions**:
   Ensure write permissions in the project directory:
   ```bash
   chmod u+w .
   ```

## Running the Tests
1. **Start Locust**:
   ```bash
   locust -f locustfile.py
   ```
2. **Configure Test Parameters**:
   - Open `http://localhost:8089` in a browser.
   - Set:
     - **Number of Users**: e.g., 3
     - **Spawn Rate**: e.g., 1 user/second
     - **Host**: `https://trialvq0712.jfrog.io`
   - Start the test and run for ~60 seconds.
   - Stop via the UI or press `Ctrl+C`.

3. **Output**:
   - `performance_report_YYYYMMDD_HHMMSS.csv`: Contains test configuration and metrics (timestamp, operation, response_time, status, errors, user_id, repo_key).
   - Example:
     ```csv
     ### Test Configuration ###
     jfrog_url,https://trialvq0712.jfrog.io
     num_users,3
     ...
     ### Performance Metrics ###
     timestamp,operation,response_time,status,errors,user_id,repo_key
     2025-06-19T17:00:01.123456,create_repository,150.23,success,,uuid1,docker-local-1747918800-abc12345
     ```

## Analyzing the Report
1. **Run Analysis Script**:
   ```bash
   python analyze_report.py performance_report_20250619_170000.csv
   ```
   - Generates:
     - `response_time.png`: Response time trends per operation.
     - `failure_counts.png`: Failure counts by operation.
     - `metrics_summary.txt`: Summary of requests, success/failure rates, and response times.

2. **Update `analysis.md`**:
   - Edit `analysis.md` with metrics from `metrics_summary.txt` and observations from visualizations.
   - Example:
     ```markdown
     ## Observations
     - `push_image` had high latency (~2500ms) due to Docker push.
     - `create_watch` failed with "Got invalid watch" errors.
     ## Recommendations
     - Use a non-empty filter in `create_watch`.
     - Optimize network for faster image pushes.
     ```

## Test Details
The Locust test performs the following tasks:
- **create_repository**: Creates a unique Docker repository (`docker-local-<timestamp>-<uuid>`).
- **push_docker_image**: Pushes `alpine:3.9` to the repository.
- **create_policy**: Creates a security policy in JFrog Xray.
- **create_watch**: Configures a watch to monitor the repository for security issues.

## Troubleshooting
- **CSV Not Generated**:
  - Check logs for `Failed to generate report`.
  - Verify directory permissions: `chmod u+w .`
- **Image Push Failures**:
  - Ensure Docker is logged in: `docker login trialvq0712.jfrog.io`.
  - Check logs for `Docker API error`.
- **Watch Creation Errors**:
  - If `create_watch` fails with `Got invalid watch`, test manually:
    ```bash
    curl -u <USERNAME>:<PASSWORD> -X POST "https://trialvq0712.jfrog.io/xray/api/v2/watches" \
    -H "Content-Type: application/json" \
    -d '{"general_data":{"name":"test-watch","description":"Test watch","active":true},"project_resources":{"resources":[{"type":"repository","name":"docker-local-1747918800-abc12345","filters":[{"type":"regex","value":".*"}]}]},"assigned_policies":[{"name":"sec_policy_1747918800","type":"security"}]}'
    ```

## Future Improvements
- Increase user load to stress-test Artifactory.
- Integrate `analyze_report.py` into a CI/CD pipeline.
- Add server-side monitoring for JFrog Artifactory.

## License
MIT License
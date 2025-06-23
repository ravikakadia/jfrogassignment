# JFrog Artifactory/Xray Performance Test Analysis

**Test Configuration:** 1 Master + 2 Workers  
**Report Generated:** 2025-06-23 06:20:00 UTC
**Performance Report file name:** performance_report_20250623_062000.csv
---

## Performance Summary

| Operation         | Count | Avg. Response (ms) | Success Rate | Failure Rate |
|-------------------|-------|--------------------|--------------|--------------|
| create_repository |   2   |      710.07        |   100%       |     0%       |
| create_policy     |   3   |      315.85        |   100%       |     0%       |
| check_scan_status |   1   |      371.34        |     0%       |   100%       |
| get_violations    |   1   |      333.57        |   100%       |     0%       |
| create_watch      |   1   |     2173.51        |   100%       |     0%       |

---

## Critical Findings

1. **`create_watch` is the bottleneck**
   - Single operation took **2173ms** (much slower than others)
   - Potential causes: Policy assignment complexity, watch initialization overhead

2. **`check_scan_status` failures**
   - 100% failure rate in sampled data
   - Indicates scans not completing before status checks

3. **Repository creation variance**
   - Fastest: 322ms, Slowest: 1098ms (3.4× difference)
   - Inconsistent performance suggests resource contention

---

## Optimization Recommendations

### ⚡ Immediate Fixes

- **Implement exponential backoff for scan checks:**
For example: 
def check_scan_status(self):
for attempt in range(5): # Max 5 retries
with self.client.post(...) as response:
if response.status_code == 200:
data = response.json()
if data["overall"]["status"] == "SCANNED":
break
gevent.sleep(2 ** attempt) # Exponential backoff

-- **Xray Watch Optimization**
- Pre-create watch templates
- Use `"active": false` during creation, then activate in bulk

### 🧪 Test Process Improvements

1. **Baseline Measurement**

Before optimization
locust --headless -u 100 -r 10 -t 5m --csv=baseline

After optimization
locust --headless -u 100 -r 10 -t 5m --csv=optimized

2. **Distributed Monitoring**

@events.request.add_listener
def track_request(request_type, name, response_time, response_length, exception, **kw):
if exception:
logger.error(f"Request failed: {name}, {exception}"

## Key Performance Insights

1. **Watch creation is the critical path** – Requires architectural optimization.
2. **Scan status checks need resilience** – Not performance-related but critical for test validity.
3. **Repository creation consistency** – Indicates possible resource starvation during parallel execution. - May be increasing heap size give better performance.

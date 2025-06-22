import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def analyze_report(csv_file):
    try:
        # Read file lines to check for headers
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            logging.error(f"CSV file {csv_file} is empty")
            raise ValueError("Empty CSV file")
        
        # Check for configuration and metrics headers
        config = {
            "jfrog_url": "https://trialvq0712.jfrog.io",
            "username": "unknown",
            "num_users": "unknown",
            "spawn_rate": "unknown",
            "test_start_time": "2025-06-22T05:16:48",
            "test_duration": "11 seconds (estimated)",
            "repo_name_pattern": "docker-local-<timestamp>-<uuid>",
            "image_name": "alpine:3.9",
            "custom_tag": "test"
        }
        metrics_start = 0
        if "### Performance Metrics ###\n" in lines:
            metrics_start = lines.index("### Performance Metrics ###\n") + 2
            logging.info("Found '### Performance Metrics ###' header")
            if "### Test Configuration ###\n" in lines:
                config_end = lines.index("### Performance Metrics ###\n")
                config_lines = lines[lines.index("### Test Configuration ###\n") + 1:config_end]
                for line in config_lines:
                    if line.strip() and ',' in line:
                        key, value = line.strip().split(',', 1)
                        config[key] = value
                logging.info(f"Parsed configuration: {config}")
        else:
            logging.warning("No '### Performance Metrics ###' header found, reading entire file as metrics")
        
        # Read metrics
        df = pd.read_csv(csv_file, skiprows=metrics_start)
        if df.empty:
            logging.error("No metrics data found in CSV")
            raise ValueError("No metrics data")
        
        # Ensure required columns with defaults
        df['response_time'] = pd.to_numeric(df['response_time'], errors='coerce')
        df['errors'] = pd.Series([''] * len(df), index=df.index)  # Default empty errors column
        df['user_id'] = pd.Series(['unknown'] * len(df), index=df.index)  # Default user_id
        df['repo_key'] = pd.Series(['unknown'] * len(df), index=df.index)  # Default repo_key
        
        # Compute metrics
        metrics = {
            "total_requests": len(df),
            "operations": df['operation'].unique().tolist(),
            "success_rate": (df['status'] == 'success').mean() * 100,
            "failure_rate": (df['status'] == 'failed').mean() * 100,
            "avg_response_time": df.groupby('operation')['response_time'].mean().to_dict(),
            "max_response_time": df.groupby('operation')['response_time'].max().to_dict(),
            "failure_counts": df[df['status'] == 'failed']['operation'].value_counts().to_dict(),
            "config": config
        }
        
        # Generate visualizations
        available_styles = plt.style.available
        plot_style = 'ggplot' if 'ggplot' in available_styles else 'default'
        logging.info(f"Using matplotlib style: {plot_style}")
        plt.style.use(plot_style)

        # Response time over time
        plt.figure(figsize=(12, 6))
        for op in df['operation'].unique():
            op_df = df[df['operation'] == op]
            plt.plot(op_df['timestamp'], op_df['response_time'], label=op)
        plt.xlabel('Timestamp')
        plt.ylabel('Response Time (ms)')
        plt.title('Response Time Over Time by Operation')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('response_time.png')
        plt.close()
        
        # Failure counts by operation
        plt.figure(figsize=(10, 6))
        sns.countplot(data=df[df['status'] == 'failed'], x='operation')
        plt.xlabel('Operation')
        plt.ylabel('Failure Count')
        plt.title('Failure Counts by Operation')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('failure_counts.png')
        plt.close()
        
        # Save metrics summary
        with open('metrics_summary.txt', 'w') as f:
            f.write("Performance Metrics Summary\n")
            f.write(f"Total Requests: {metrics['total_requests']}\n")
            f.write(f"Operations: {', '.join(metrics['operations'])}\n")
            f.write(f"Success Rate: {metrics['success_rate']:.2f}%\n")
            f.write(f"Failure Rate: {metrics['failure_rate']:.2f}%\n")
            f.write("Configuration:\n")
            for key, value in metrics['config'].items():
                f.write(f"  {key}: {value}\n")
            f.write("Average Response Time (ms):\n")
            for op, rt in metrics['avg_response_time'].items():
                f.write(f"  {op}: {rt:.2f}\n")
            f.write("Maximum Response Time (ms):\n")
            for op, rt in metrics['max_response_time'].items():
                f.write(f"  {op}: {rt:.2f}\n")
            f.write("Failure Counts:\n")
            for op, count in metrics['failure_counts'].items():
                f.write(f"  {op}: {count}\n")
        
        logging.info("Generated response_time.png, failure_counts.png, metrics_summary.txt")
        return metrics
    
    except Exception as e:
        logging.error(f"Failed to analyze report: {str(e)}")
        raise

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python analysis.py <csv_file>")
        sys.exit(1)
    csv_file = sys.argv[1]
    metrics = analyze_report(csv_file)
    print(f"Analysis complete. See response_time.png, failure_counts.png, and metrics_summary.txt")

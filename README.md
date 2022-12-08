# metrics_analyzer

`metrics_analyzer` is a command line tools which helps checking metrics between dashboards of grafana, prometheus rules and prometheus metrics and outputs whitelisted metrics or metrics to drop.

## Features

* Connect via API to Grafana and get all metrics which are use in any dashboards
* Connect via API to Prometheus and get all metrics which are use in any rules
* Connect via API to Prometheus and check exist metrics
* Generates regex output to add to service monitor 

## Installation
### Prerequisites
at least Python 3.10
### Stable release

To install metrics_analyzer, run this command directly from repository:


    $ pip install git+https://github.com/oleksii-boiko-ua/metrics_analyzer.git


## Usage

To use this tool locally, you will need to create port-forwards for your grafana and prometheus services.


    $ kubectl port-forward svc/grafana 3000:80
    $ kubectl port-forward svc/prometheus 9090:9090

Also, if you use an API key for Grafana you should set it in you environment.

    $ export GRAFANA_KEY=...

Now you should be able to run the following script:


    $ metrics_analyzer metrics-to-whitelist


Output example:

```yaml
We can whitelist 10 metrics from the job argocd-metrics

process_cpu_seconds_total|ALERTS|go_goroutines|workqueue_depth|process_start_time_seconds|process_resident_memory_bytes|workqueue_adds_total|up|argocd_app_info|workqueue_queue_duration_seconds_bucket


We can whitelist 55 metrics from the job kube-state-metrics

kube_job_status_start_time|kube_deployment_status_replicas|kube_statefulset_status_replicas_ready|kube_pod_container_resource_requests|kube_node_spec_taint|kube_namespace_created|kube_node_status_allocatable|kube_pod_container_resource_limits|kube_deployment_labels|kube_node_info


We can whitelist 10 metrics from the job prometheus-grafana

process_cpu_seconds_total|grafana_http_request_duration_seconds_bucket|go_goroutines|process_start_time_seconds|grafana_build_info|process_resident_memory_bytes|grafana_http_request_duration_seconds_sum|grafana_stat_totals_dashboard|up|grafana_http_request_duration_seconds_count
```

example of metric relabelings for service monitor to whitelist recomended metrics

```yaml
metricRelabelings:
  - action: keep
    regex: 'process_cpu_seconds_total|go_goroutines|prometheus_operator_watch_operations_total'
    sourceLabels: [__name__]
```

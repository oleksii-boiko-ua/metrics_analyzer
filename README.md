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

from io import BytesIO
from tokenize import tokenize, NUMBER, STRING, NAME, ENCODING, ENDMARKER, \
    NEWLINE

import json
import logging
import os
import sys
import argparse
import urllib.request

logger = logging.getLogger('metrics_analyzer')

logging.basicConfig(level='INFO')



GRAFANA_DEFAULT_URL = 'http://localhost:3000'
PROMETHEUS_DEFAULT_URL = 'http://localhost:9090'

GRAFANA_URL = os.environ.get(
    'GRAFANA_URL', GRAFANA_DEFAULT_URL)
GRAFANA_KEY = os.environ.get(
    'GRAFANA_KEY')
PROMETHEUS_URLS = os.environ.get(
    'PROMETHEUS_URLS', PROMETHEUS_DEFAULT_URL)


class Token:

    def __init__(self, no, toknum, tokval):
        self.no = no
        self.toknum = toknum
        self.tokval = tokval

    def __repr__(self):
        return 'Token({no}, {toknum}, "{tokval}")'.format(
            no=self.no, toknum=self.toknum, tokval=self.tokval)

    def is_name(self):
        return self.toknum == NAME

    def is_string(self):
        return self.toknum == STRING

    def is_number(self):
        return self.toknum == NUMBER

    def is_operation(self):
        return self.tokval in [
            "+", "-", "*", "/", "%", "^",
            "==", "!=", ">", "<", ">=", "<="]

    def is_colon(self):
        return self.tokval == ":"

    def is_leftbracket(self):
        return self.tokval == "("

    def is_rightbracket(self):
        return self.tokval == ")"

    def is_leftcurltbracket(self):
        return self.tokval == "{"

    def is_rightcurltbracket(self):
        return self.tokval == "}"

    def is_leftsquarebracket(self):
        return self.tokval == "["

    def is_rightsquarebracket(self):
        return self.tokval == "]"

    def is_unnecessary(self):
        return self.tokval in [
            'by', 'without',
            'group_left', 'group_right',
            'and', 'or', 'unless', 'ignoring', 'on',
            'count_values', 'quantile', 'topk', 'bottomk']

    def get_next(self, heap):
        try:
            return heap[self.no + 1]
        except IndexError:
            return None

    def get_prev(self, heap):
        try:
            return heap[self.no - 1]
        except IndexError:
            return None

class Response:
    def __init__(self, response=None):
        self.response = response
        self.content = self.response.read()

    @property
    def ok(self):
        return 200 <= self.response.getcode() <= 299

    @property
    def text(self):
        return self.content.decode('utf-8')

    def json(self):
        if self.text:
            return json.loads(self.text)
        return {}


def request_get(url=None, token=None):
    request = urllib.request.Request(url)
    data=None
    if token:
        request.add_header(
            "Authorization", "Bearer {token}".format(token=token))
    try:
        conn = urllib.request.urlopen(request, data=data, timeout=10)
    except urllib.error.URLError as e:
        print('{url}: {error}'.format(url=url, error=e.reason))
        exit(1)
    return Response(conn)


def tokenize_string(query):
    result, x = [], 0
    g = tokenize(BytesIO(query.encode('utf-8')).readline)
    for toknum, tokval, _a, _b, _c in g:
        if toknum not in [ENCODING, ENDMARKER, NEWLINE]:
            result.append(Token(x, toknum, tokval))
            x += 1
    return result


def find_metrics(tokenized_query):
    skip, temp, heap, metrics = False, None, [], []
    for token in tokenized_query:
        if skip == '(' and token.is_rightbracket():
            skip = False
            if heap:
                if heap[-1].is_leftbracket():
                    heap.pop()
                    if heap and heap[-1].is_name():
                        heap.pop()
                if temp:
                    metrics.append(temp)
                    temp = None
        elif skip in ['{', '['] and (
                token.is_rightcurltbracket() or token.is_rightsquarebracket()):
            skip = False
            if temp:
                metrics.append(temp)
                temp = None
        elif skip:
            continue
        elif token.is_leftbracket():
            heap.append(token)
        elif token.is_leftcurltbracket() or token.is_leftsquarebracket():
            skip = token.tokval
        elif token.is_colon():
            if temp:
                temp += token.tokval
            else:
                temp = token.tokval
        elif token.is_name():
            if token.is_unnecessary():
                if token.get_next(tokenized_query).is_leftbracket():
                    skip = token.get_next(tokenized_query).tokval
            elif token.get_next(tokenized_query):
                if token.get_next(tokenized_query).is_leftbracket():
                    heap.append(token)
                elif token.get_next(tokenized_query).is_leftcurltbracket() or \
                        token.get_next(
                            tokenized_query).is_leftsquarebracket() or \
                        token.get_next(
                            tokenized_query).is_operation() or \
                        token.get_next(
                            tokenized_query).is_rightbracket():
                    if temp:
                        temp += token.tokval
                        metrics.append(temp)
                        temp = None
                    else:
                        metrics.append(token.tokval)
                elif token.get_next(tokenized_query).is_colon():
                    if not temp:
                        temp = token.tokval
                    else:
                        temp += token.tokval
            elif not token.get_next(tokenized_query):
                if temp:
                    temp += token.tokval
                    metrics.append(temp)
                    temp = None
                else:
                    metrics.append(token.tokval)
    return list(set(metrics))


def get_rules(url=None):
    rules = request_get(
        '{url}/api/v1/rules'.format(url=url))
    if rules.ok:
        data = rules.json()['data']['groups']
        return data
    raise ValueError

def get_metrics_per_job(url=None):
    jobs_metrics = {}
    list_of_jobs = get_list_of_job(url)
    logger.info("Getting metrics per job from prometheus")
    for job in list_of_jobs:
        prom_query = 'group by(__name__) ({__name__!="", job=~"' + f'{job}' + '"})'
        metrics = request_get(f'{url}/api/v1/query?query={prom_query.replace(" ", "%20")}')
        if metrics.ok:
            data = metrics.json()['data']['result']
            jobs_metrics[job] = [metric['metric'].get('__name__') for metric in data]
    return jobs_metrics



def get_list_of_job(url=None):
    logger.info("Getting list of jobs from prometheus")
    prom_query = 'group by(job) ({job!=""})'
    jobs = request_get(f'{url}/api/v1/query?query={prom_query.replace(" ", "%20")}')
    if jobs.ok:
        data = jobs.json()['data']['result']
        jobs = [metric['metric'].get('job') for metric in data]
        return jobs
    raise ValueError

def get_grafana_dashboards_metrics(grafana_url, grafana_key):
    dashboards = get_dashboards(grafana_url, grafana_key)
    grafana_metrics = extract_metrics(data=dashboards, key='expr')
    return grafana_metrics

def get_rules_metrics(url=None):
    rules = get_rules(url)
    rules_metrics = extract_metrics(data=rules, key='query')
    return rules_metrics

def extract_metrics_to_drop(jobs=None, grafana_metrics=None):
    logger.info("Get metrics to drop")
    for job in jobs:
        difference = set(jobs[job]).difference(set(grafana_metrics))
        print(f"\n\nWe can drop {len(list(difference))} metrics from the job {job}\n\n")
        print(to_regex(difference))
        
def extract_metrics_to_whitelist(jobs=None, grafana_metrics=None):
    logger.info("Get metrics to whitelist")
    for job in jobs:
        common_metrics = set(grafana_metrics).intersection(set(jobs[job]))
        print(f"\nWe can whitelist {len(list(common_metrics))} metrics from the job {job}\n")
        print(to_regex(common_metrics))
    

def parse_recursively(search_dict, field):
    """
    Takes a dict with nested lists and dicts, and searches all dicts
    for a key of the field provided.
    """
    fields_found = []

    for key, value in search_dict.items():

        if key == field:
            fields_found.append(value)

        elif isinstance(value, dict):
            results = parse_recursively(value, field)
            for result in results:
                fields_found.append(result)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    more_results = parse_recursively(item, field)
                    for another_result in more_results:
                        fields_found.append(another_result)

    return fields_found


def extract_metrics(data=None, key=None):
    """
    Fetches all metrics from json object based on key (for rules 'query' for dashboards 'expr')
    """
    logger.info("Extracting all metrics from given data")
    expression, metrics = [], []
    for configration in data:
        expression.extend(parse_recursively(configration, key))
    for expr in expression:
        metrics.extend(find_metrics(tokenized_query=tokenize_string(expr)))
    return list(set(metrics))


def get_dashboards(url=None, key=None):
    """
    Fetches all dashboards from grafana and returns it as an object
    """
    logger.info("Fetching all dashboards from grafana")
    dashboards, dashboards_uid = [], []
    search_dashboard = request_get(
        '{url}/api/search'.format(url=url), token=key)
    if search_dashboard.ok:
        dashboards_uid = [dash.get('uid') for dash in search_dashboard.json()]
    for name in dashboards_uid:
        dashboard = request_get('{url}/api/dashboards/uid/{name}'.format(
            url=url, name=name), token=key)
        if dashboard.ok:
            dashboards.append(dashboard.json().get('dashboard', {}))
    return dashboards


def to_regex(metrics=None):
    regex = "|".join(metrics)
    return regex
        
        
def main(args=None):
    """Console script for metrics_analyzer."""
    parser = argparse.ArgumentParser(
        description='Command line tool for check metrics between '
                    'grafana and prometheus instance and output missing, to drop and to whitelist metrics.')
    parser.add_argument(
        choices= ['metrics-to-drop', 'metrics-to-whitelist', 'missing-dashboard-metrics', 'dashboards-metrics', 'rules-metrics', 'metrics-per-job'],
        dest = 'command',
        help='Print metrics-to-drop, metrics-to-whitelist, missing-dashboard-metrics',
        nargs='?')
    parser.add_argument(
        '--grafana-url',
        metavar='grafana_url',
        help='Set grafana url. Default value is {url}'.format(
            url=GRAFANA_DEFAULT_URL),
        nargs='?',
        default=GRAFANA_URL)
    parser.add_argument(
        '--grafana-key',
        metavar='grafana_key',
        help='Set grafana key to have API access.',
        nargs='?',
        default=GRAFANA_KEY)
    parser.add_argument(
        '--prometheus-url',
        metavar='prometheus_url',
        help='Set prometheus url. Default value is {url}'.format(
            url=PROMETHEUS_DEFAULT_URL),
        nargs='?',
        default=PROMETHEUS_URLS)
    args = parser.parse_args(args)
    
    match args.command:
        case 'metrics-to-drop':
            extract_metrics_to_drop(get_metrics_per_job(args.prometheus_url), list(set(get_grafana_dashboards_metrics(args.grafana_url, args.grafana_key) + get_rules_metrics(args.prometheus_url))))
        case 'metrics-to-whitelist':
            extract_metrics_to_whitelist(get_metrics_per_job(args.prometheus_url), list(set(get_grafana_dashboards_metrics(args.grafana_url, args.grafana_key) + get_rules_metrics(args.prometheus_url))))
        case 'dashboards-metrics':
            grafana_dashboards_metrics = get_grafana_dashboards_metrics(args.grafana_url, args.grafana_key)
            print("COUNT:", len(grafana_dashboards_metrics), "\nDASHBOARDS METRICS:\n", grafana_dashboards_metrics)
        case 'rules-metrics':
            rules_metrics = get_rules_metrics(args.prometheus_url)
            print("COUNT:", len(rules_metrics), "\nRULES METRICS:\n", rules_metrics)
        case 'metrics-per-job':
            print("METRICS_PER_JOB:\n", get_metrics_per_job(args.prometheus_url))
        case 'missing-dashboard-metrics':
            print('todo')
    

if __name__ == '__main__':
    sys.exit(main())

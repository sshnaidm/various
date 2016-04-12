import fileinput
import gzip
import os
import re

import datetime
import requests
import sys
from lxml import etree

requests.packages.urllib3.disable_warnings()

timeout_re = re.compile('Killed\s+timeout -s 9 ')
puppet_re = re.compile('"deploy_stderr": ".+?1;31mError: .+?\W(\w+)::')
resolving_re = re.compile(
    'Could not resolve host: (\S+); Name or service not known')

LOGS_DIR = os.path.join(os.environ["HOME"], "tmp", "ci_status")
#MAIN_PAGE = "http://tripleo.org/cistatus-periodic.html"
MAIN_PAGE = "http://tripleo.org/cistatus.html"


PATTERNS = [
    {
        "pattern": "Stack overcloud CREATE_COMPLETE",
        "msg": "Overcloud stack installation: SUCCESS.",
        "tag": ""
    },
    {
        "pattern": "Stack overcloud CREATE_FAILED",
        "msg": "Overcloud stack: FAILED.",
        "tag": "code"
    },
    {
        "pattern": "No valid host was found. There are not enough hosts",
        "msg": "No valid host was found.",
        "tag": "code"
    },
    {
        "pattern": "Failed to connect to trunk.rdoproject.org port 80",
        "msg": "Connection failure to trunk.rdoproject.org.",
        "tag": "infra"
    },
    {
        "pattern": "Overloud pingtest, FAIL",
        "msg": "Overcloud pingtest FAILED.",
        "tag": "code"
    },
    {
        "pattern": "Overcloud pingtest, failed",
        "msg": "Overcloud pingtest FAILED.",
        "tag": "code"
    },
    {
        "pattern": "Error contacting Ironic server: Node ",
        "msg": "Ironic introspection FAIL.",
        "tag": "code"
    },
    {
        "pattern": "Introspection completed with errors:",
        "msg": "Ironic introspection FAIL.",
        "tag": "code"
    },
    {
        "pattern": ": Introspection timeout",
        "msg": "Introspection timeout.",
        "tag": "code"
    },
    {
        "pattern": "is locked by host localhost.localdomain, please retry",
        "msg": "Ironic: Host locking error.",
        "tag": "code"
    },
    {
        "pattern": "Timed out waiting for node ",
        "msg": "Ironic node register FAIL: timeout for node.",
        "tag": "code"
    },
    {
        "pattern": "Killed                  ./testenv-client -b",
        "msg": "Job was killed by testenv-client. Timeout??",
        "tag": "infra"
    },
    {
        "pattern": timeout_re,
        "msg": "Killed by timeout.",
        "tag": "infra"
    },
    {
        "pattern": puppet_re,
        "msg": "Pupppet {} FAIL.",
        "tag": "code"
    },
    {
        "pattern": "Stack not found: overcloud",
        "msg": "Didn't reach overcloud step.",
        "tag": ""
    },
    {
        "pattern": "Error: couldn't connect to server 127.0.0.1:27017",
        "msg": "MongoDB FAIL.",
        "tag": "code"
    },
    {
        "pattern": "Keystone_tenant[service]/ensure: change from absent to present failed",
        "msg": "Keystone FAIL.",
        "tag": "code"
    },
    {
        "pattern": "ERROR:dlrn:cmd failed. See logs at",
        "msg": "Delorean FAIL.",
        "tag": "code"
    },
    {
        "pattern": "500 Internal Server Error: Failed to upload image",
        "msg": "Glance upload FAIL.",
        "tag": "code"
    },
    {
        "pattern": "Slave went offline during the build",
        "msg": "Jenkins slave FAIL.",
        "tag": "infra"
    },
    {
        "pattern": resolving_re,
        "msg": "DNS resolve of {} FAIL.",
        "tag": "infra"
    },
    {
        "pattern": "fatal: The remote end hung up unexpectedly",
        "msg": "Git clone repo FAIL.",
        "tag": "infra"
    },
    {
        "pattern": "Create timed out       | CREATE_FAILED",
        "msg": "Create timed out.",
        "tag": "code"
    },
    {
        "pattern": "FATAL: no longer a configured node for ",
        "msg": "Slave FAIL: no longer a configured node",
        "tag": "infra"
    },
    {
        "pattern": "cd: /opt/stack/new/delorean/data/repos: No such file or directory",
        "msg": "Delorean build FAIL, needs a patch.",
        "tag": "code"
    },

]

def parse(td):
    colors = {'color : #008800': 'green',
              'color : #FF0000': 'red',
              'text-decoration:none': 'none',
              'color : #666666': 'none',
              'color : #000000': 'none'}
    build, log = td.xpath(".//a")
    length = re.search("(\d+) min", build.tail).group(1)
    date = re.search("(\d+-\d+)", build.text).group(1)
    time = re.search("(\d+:\d+)", build.text).group(1)
    stat = re.search("(\d+/\d+)", log.tail).group(1)
    color = colors[build.attrib['style']]
    log_url = log.attrib['href']
    build_url = build.attrib['href']
    job_type = re.search(".*/job/([^/]+)/", build_url).group(1)
    log_hash = re.search(".*/([^/]+)/$", log_url).group(1)
    short_type = job_type.split("-")[-1]
    return {
        'log_url': log_url,
        'log_hash': log_hash,
        'build_url': build_url,
        'length': length,
        'job_type': job_type,
        'color': color,
        'stat': stat,
        'time': time,
        'date': date,
        "short_type": short_type,
        'td': td
    }


def parse_page(main_page):
    page_obj = requests.get(main_page)
    page = page_obj.content
    et = etree.HTML(page)
    tds_gen = (i for i in et.xpath(".//td") if len(i.xpath(".//a")) == 2)
    tds = (i for i in tds_gen if
           "http://logs.openstack.org" in i.xpath(".//a")[1].attrib["href"])
    data = [parse(td) for td in tds]
    return data


def download(g, path):
    console = g['log_url'] + "console.html"
    name = g['log_hash'] + ".html.gz"
    if not os.path.exists(path):
        os.makedirs(path)
    if os.path.exists(os.path.join(path, name)):
        return True
    else:
        req = requests.get(console)
        if req.status_code == 404:
            new_url = console + ".gz"
            req = requests.get(new_url)
            if req.status_code != 200:
                build_console = g['build_url'] + "/consoleText"
                req = requests.get(build_console, verify=False)
                if req.status_code != 200:
                    print "URL " + console + " is not accessible! Skipping..,"
                    return False
        with gzip.open(os.path.join(path, name), "wb") as f:
            f.write(req.content)
        return True

def include(job,
            job_type=None, short=None, dates=None, excluded=None, fail=True):
    if job_type and job["job_type"] != job_type:
        return False
    if short and job["short_type"] != short:
        return False
    if dates and job["date"] not in dates:
        return False
    if excluded and job["short_type"] == excluded:
        return False
    if fail and job['color'] != 'red':
        return False
    return True


def limit(jobs,
          job_type=None,
          number=0,
          short=None,
          days=None,
          excluded=None,
          fail=True):
    jobs = sorted(jobs, key=lambda x: x['date'], reverse=True)
    counter = 0
    if days:
        today = datetime.date.today()
        parse_day = lambda x: datetime.date.strftime(x, "%m-%d")
        dates = []
        for i in xrange(days):
            dates.append(parse_day(today - datetime.timedelta(days=i)))
    else:
        dates = None
    for job in jobs:
        if (counter < number
            and include(job, job_type, short, dates, excluded, fail)
            and download(job, path=LOGS_DIR)):
            yield job
            counter += 1


def analyze(j, logpath):
    def line_match(pat, line):
        if isinstance(pat, re._pattern_type):
            if not pat.search(line):
                return False
            elif pat.search(line).groups():
                return pat.search(line).group(1)
            else:
                return True
        if isinstance(pat, str):
            return pat in line

    jfile = os.path.join(logpath, j['log_hash'] + ".html.gz")
    msg = set()
    delim = "||"
    tags = set()
    for line in fileinput.input(jfile, openhook=fileinput.hook_compressed):
        for p in PATTERNS:
            if line_match(p["pattern"], line) and p["msg"] not in msg:
                msg.add(p["msg"].format(line_match(p["pattern"], line)))
                tags.add(p["tag"])
    if not msg:
        msg = {"Reason was NOT FOUND. Please investigate"}
        delim = "XX"
        tags.add("unknown")
    all_msg = ("{date}:\t"
               "{job_type:38}\t"
               "{delim}\t"
               "{msg:60}\t"
               "{delim}\t"
               "log: {log_url}")
    print all_msg.format(msg=" ".join(sorted(msg)), delim=delim, **j)
    return tags

def print_stats(s):
    tags = [j for i in s for j in i if j]
    for t in set(tags):
        print "Reason - {}: {} fails, {}% of counted {} jobs".format(
            t, tags.count(t), tags.count(t) * 100 / len(s), len(s))




def main():
    # How many jobs to print
    LIMIT_JOBS = 50
    # How many days to include, None for all days, 1 - for today
    DAYS = 1
    # Which kind of jobs to take? ha, nonha, upgrades, None - for all
    INTERESTED_JOB_TYPE = None #  or None for all (ha, nonha, upgrades, etc)
    EXCLUDED_JOB_TYPE = "containers"
    short_name = sys.argv[1] if len(sys.argv) > 1 else INTERESTED_JOB_TYPE

    stats = []
    jobs = parse_page(MAIN_PAGE)
    for job in limit(jobs,
                     short=short_name,
                     number=LIMIT_JOBS,
                     days=DAYS,
                     excluded=EXCLUDED_JOB_TYPE):
        stats.append(analyze(job, LOGS_DIR))
    print "Statistics:"
    print "Analysis of page:", MAIN_PAGE
    print "Job type:", short_name or "all"
    print_stats(stats)


if __name__ == '__main__':
    main()

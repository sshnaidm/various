import fileinput
import gzip
import os
import re
import requests
import sys
from lxml import etree

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
        "msg": "Overcloud stack installation: SUCCESS."
    },
    {
        "pattern": "Stack overcloud CREATE_FAILED",
        "msg": "Overcloud stack: FAILED."
    },
    {
        "pattern": "No valid host was found. There are not enough hosts",
        "msg": "No valid host was found."
    },
    {
        "pattern": "Failed to connect to trunk.rdoproject.org port 80",
        "msg": "Connection failure to trunk.rdoproject.org."
    },
    {
        "pattern": "Overloud pingtest, FAIL",
        "msg": "Overcloud pingtest FAILED."
    },
    {
        "pattern": "Overcloud pingtest, failed",
        "msg": "Overcloud pingtest FAILED."
    },
    {
        "pattern": "Error contacting Ironic server: Node ",
        "msg": "Ironic introspection FAIL."
    },
    {
        "pattern": "Introspection completed with errors:",
        "msg": "Ironic introspection FAIL."
    },
    {
        "pattern": ": Introspection timeout",
        "msg": "Introspection timeout."
    },
    {
        "pattern": "is locked by host localhost.localdomain, please retry",
        "msg": "Ironic: Host locking error."
    },
    {
        "pattern": "Timed out waiting for node ",
        "msg": "Ironic node register FAIL: timeout for node."
    },
    {
        "pattern": "Killed                  ./testenv-client -b",
        "msg": "Job was killed by testenv-client. Timeout??"
    },
    {
        "pattern": timeout_re,
        "msg": "Killed by timeout."
    },
    {
        "pattern": puppet_re,
        "msg": "Pupppet {} FAIL."
    },
    {
        "pattern": "Stack not found: overcloud",
        "msg": "Didn't reach overcloud step."
    },
    {
        "pattern": "Error: couldn't connect to server 127.0.0.1:27017",
        "msg": "MongoDB FAIL."
    },
    {
        "pattern": "Keystone_tenant[service]/ensure: change from absent to present failed",
        "msg": "Keystone FAIL."
    },
    {
        "pattern": "ERROR:dlrn:cmd failed. See logs at",
        "msg": "Delorean FAIL."
    },
    {
        "pattern": "500 Internal Server Error: Failed to upload image",
        "msg": "Glance upload FAIL."
    },
    {
        "pattern": "Slave went offline during the build",
        "msg": "Jenkins slave FAIL."
    },
    {
        "pattern": resolving_re,
        "msg": "DNS resolve of {} FAIL."
    },
    {
        "pattern": "fatal: The remote end hung up unexpectedly",
        "msg": "Git clone repo FAIL."
    },
    {
        "pattern": "Create timed out       | CREATE_FAILED",
        "msg": "Create timed out."
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
                print "URL " + console + " is not accessible! Skipping..,"
                return False
        with gzip.open(os.path.join(path, name), "wb") as f:
            f.write(req.content)
        return True

def include(job, job_type=None, short=None, fail=True):
    if job_type and job["job_type"] != job_type:
        return False
    if short and job["short_type"] != short:
        return False
    if fail and job['color'] != 'red':
        return False
    return True


def limit(jobs, job_type=None, number=0, short=None, fail=True):
    jobs = sorted(jobs, key=lambda x: x['date'], reverse=True)
    counter = 0
    for job in jobs:
        if (counter < number
            and include(job, job_type, short, fail)
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
    for line in fileinput.input(jfile, openhook=fileinput.hook_compressed):
        for p in PATTERNS:
            if line_match(p["pattern"], line) and p["msg"] not in msg:
                msg.add(p["msg"].format(line_match(p["pattern"], line)))
    if not msg:
        msg = {"Reason was NOT FOUND. Please investigate"}
        delim = "XX"
    all_msg = ("{date}:\t"
               "{job_type:38}\t"
               "{delim}\t"
               "{msg:60}\t"
               "{delim}\t"
               "log: {log_url}")
    print all_msg.format(msg=" ".join(sorted(msg)), delim=delim, **j)


def main():
    # How many jobs to print
    LIMIT_JOBS = 50
    # Which kind of jobs to take? ha, nonha, upgrades, None - for all
    INTERESTED_JOB_TYPE = "nonha" #  or None for all (ha, nonha, upgrades, etc)
    short_name = sys.argv[1] if len(sys.argv) > 1 else INTERESTED_JOB_TYPE

    jobs = parse_page(MAIN_PAGE)
    for job in limit(jobs, short=short_name, number=LIMIT_JOBS):
        analyze(job, LOGS_DIR)


if __name__ == '__main__':
    main()

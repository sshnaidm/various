import fileinput
import os
import re
import requests
import sys
from lxml import etree

timeout_re = re.compile('Killed\s+timeout -s 9 ')
LOGS_DIR = os.path.join(os.environ["HOME"], "tmp", "ci_status")
MAIN_PAGE = "http://tripleo.org/cistatus-periodic.html"
# MAIN_PAGE = "http://tripleo.org/cistatus.html"


PATTERNS = [
    {
        "pattern": "Stack overcloud CREATE_COMPLETE",
        "msg": "Overcloud stack installation: SUCCESS. "
    },
    {
        "pattern": "Stack overcloud CREATE_FAILED",
        "msg": "Overcloud stack: FAILED. "
    },
    {
        "pattern": "No valid host was found. There are not enough hosts",
        "msg": "No valid host was found. "
    },
    {
        "pattern": "Failed to connect to trunk.rdoproject.org port 80",
        "msg": "Connection failure to trunk.rdoproject.org. "
    },
    {
        "pattern": "Overloud pingtest, FAIL",
        "msg": "Overcloud pingtest FAILED"
    },
    {
        "pattern": "Error contacting Ironic server: Node ",
        "msg": "Ironic introspection FAIL. "
    },
    {
        "pattern": "Introspection completed with errors:",
        "msg": "Ironic introspection FAIL. "
    },
    {
        "pattern": ": Introspection timeout",
        "msg": "Introspection timeout. "
    },
    {
        "pattern": "is locked by host localhost.localdomain, please retry",
        "msg": "Ironic: Host locking error. "
    },
    {
        "pattern": "Timed out waiting for node ",
        "msg": "Ironic node register FAIL: timeout for node. "
    },
    {
        "pattern": "Killed                  ./testenv-client -b",
        "msg": "Job was killed by testenv-client. Timeout??"
    },
    {
        "pattern": timeout_re,
        "msg": "Killed by timeout. "
    },
]


def parse(td):
    colors = {'color : #008800': 'green',
              'color : #FF0000': 'red',
              'text-decoration:none': 'none'}
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
    name = g['log_hash'] + ".html"
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
        with open(os.path.join(path, name), "w") as f:
            f.write(req.content)
        return True


def limit_jobs(jobs, job_type=None, number=14, short=None, fail=True):
    res = sorted(jobs, key=lambda x: x['date'], reverse=True)
    if job_type:
        res = [i for i in res if i['job_type'] == job_type]
    if short:
        res = [i for i in res if i['short_type'] == short]
    if fail:
        res = [i for i in res if i['color'] == 'red']
    if number:
        res = res[:number]
    return res


def analyze(j, logpath):
    def line_match(pat, line):
        if isinstance(pat, re._pattern_type):
            return pat.search(line)
        if isinstance(pat, str):
            return pat in line

    jfile = os.path.join(logpath, j['log_hash'] + ".html")
    msg = ''
    delim = "||"
    for line in fileinput.input(jfile):
        for p in PATTERNS:
            if line_match(p["pattern"], line) and p["msg"] not in msg:
                msg += p["msg"]
    if not msg:
        msg = "Reason was NOT FOUND. Please investigate"
        delim = "XX"
    all_msg = "{date}:\t{job_type:38}\t{delim}\t{msg:50}\t{delim}\tlog: {log_url}"
    print all_msg.format(msg=msg, delim=delim, **j)


def main():
    LIMIT_JOBS = 7
    INTERESTED_JOB_TYPE = None #  or None for all
    short_name = sys.argv[1] if len(sys.argv) > 1 else INTERESTED_JOB_TYPE

    jobs = parse_page(MAIN_PAGE)
    jobs = [job for job in jobs if download(job, path=LOGS_DIR)]
    for job in limit_jobs(jobs, short=short_name, number=LIMIT_JOBS):
        analyze(job, LOGS_DIR)


if __name__ == '__main__':
    main()

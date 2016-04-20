import fileinput
import gzip
import json
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
exec_re = re.compile('mError: (\S+?) \S+ returned 1 instead of one of')
patchset_re = re.compile('(https://review.openstack.org/\d+)')
date_re = re.compile("Date: \d+-(\d+-\d+) (\d+:\d+)")
len_re = re.compile("- (\d+[mhs])")

VERBOSE = False

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
        "msg": "Puppet {} FAIL.",
        "tag": "code"
    },
    {
        "pattern": exec_re,
        "msg": "Program {} FAIL.",
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
        "pattern": ("cd: /opt/stack/new/delorean/data/repos: "
                    "No such file or directory"),
        "msg": "Delorean repo build FAIL.",
        "tag": "code"
    },
    {
        "pattern": ("[ERROR] - SEVERE ERROR occurs: "
                    "java.lang.InterruptedException"),
        "msg": "Jenkins lave FAIL: InterruptedException",
        "tag": "infra"
    },
    {
        "pattern": ("Killed                  bash -xe "
                    "/opt/stack/new/tripleo-ci/toci_gate_test.sh"),
        "msg": "Main script timeout",
        "tag": "infra"
    },
]


def parse_tr(tr, names):
    colors = {'color : #008800': 'green',
              'color : #FF0000': 'red',
              'text-decoration:none': 'none',
              'color : #666666': 'none',
              'color : #000000': 'none'}
    for index, td in enumerate([i for i in tr.xpath(".//td")]):
        if index == 0:
            if not td.text:
                print td.text
                print td.attrib
                print td.tail
                print td
                print " ".join(tr.xpath(".//text()"))
                return
            date, time = date_re.search(td.text).groups()
        if not td.xpath(".//a"):
            continue
        else:
            patch, log = td.xpath(".//a")
            patch_url = patch.attrib['href']
            log_url = log.attrib['href']
            log_hash = re.search(".*/([^/]+)/$", log_url).group(1)
            color = colors[patch.attrib['style']]
            job_type = names[index -1]
            short_type = job_type.split("-")[-1]
            length = len_re.search(td.xpath(".//a")[0].tail).group(1)
            yield {
                'log_url': log_url,
                'log_hash': log_hash,
                'build_url': None,
                'length': length,
                'job_type': job_type,
                'color': color,
                'stat': None,
                'time': time,
                'date': date,
                "short_type": short_type,
                'td': td
            }


def parse_page(main_page):
    page_obj = requests.get(main_page)
    page = page_obj.content
    et = etree.HTML(page)
    tr_head = [i for i in et.xpath(".//tr")
               if i.attrib['class'] == 'headers'][0]
    job_names = tr_head.xpath(".//td/b/text()")
    trs_gen = (i for i in et.xpath(".//tr")
               if i.attrib['class'] in ('tr1', 'tr0'))
    data = []
    for tr in trs_gen:
        for i in parse_tr(tr, job_names):
            if i:
                data.append(i)
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


def download_buildurl(g, path):
    url = g['build_url'] + "/api/json"
    name = g['log_hash'] + ".json.gz"
    if not os.path.exists(path):
        os.makedirs(path)
    if os.path.exists(os.path.join(path, name)):
        return True
    req = requests.get(url)
    if req.status_code != 200:
        return False
    try:
        text = json.load(req.content)
    except:
        return False
    with gzip.open(os.path.join(path, name), "wb") as f:
        f.write(text)
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
          fail=True,
          down_path=None):
    def parse_day(x):
        return datetime.date.strftime(x, "%m-%d")

    jobs = sorted(jobs, key=lambda x: x['date'], reverse=True)
    counter = 0
    if days:
        today = datetime.date.today()

        dates = []
        for i in xrange(days):
            dates.append(parse_day(today - datetime.timedelta(days=i)))
    else:
        dates = None
    for job in jobs:
        if (counter < number
            and include(job, job_type, short, dates, excluded, fail)
            and download(job, path=down_path)):
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
    tags = set()
    found_reason = True
    patch_url = ""
    try:
        for line in fileinput.input(jfile, openhook=fileinput.hook_compressed):
            for p in PATTERNS:
                if line_match(p["pattern"], line) and p["msg"] not in msg:
                    msg.add(p["msg"].format(line_match(p["pattern"], line)))
                    tags.add(p["tag"])
            if "Triggered by:" in line and patchset_re.search(line):
                patch_url = patchset_re.search(line).group(1)
        if not msg:
            msg = {"Reason was NOT FOUND. Please investigate"}
            found_reason = False
            tags.add("unknown")
    except Exception as e:
        print "Exception when parsing {}: {}".format(jfile, str(e))
        msg = {"Error when parsing logs. Please investigate"}
        found_reason = False
        tags.add("unknown")
    templ = ("{date}:\t"
             "{job_type:38}\t"
             "{delim}\t"
             "{msg:60}\t"
             "{delim}\t"
             "log: {log_url}")
    text = templ.format(msg=" ".join(sorted(msg)),
                        delim="||" if found_reason else "XX",
                        **j)
    message = {
        "text": text,
        "tags": tags,
        "msg": msg,
        "reason": found_reason,
        "job": j,
        "periodic": "periodic" in j["job_type"],
        "patch_url": patch_url
    }
    return message


def run(amount=10,
        days=1,
        job_type=None,
        excluded="containers",
        down_path=os.path.join(os.environ["HOME"], "tmp", "ci_status"),
        page="http://tripleo.org/cistatus.html"):
    jobs = parse_page(page)
    for job in limit(jobs,
                     short=job_type,
                     number=amount,
                     days=days,
                     excluded=excluded,
                     down_path=down_path):
        yield analyze(job, down_path)


def print_stats(s):
    stats_tags = [i['tags'] for i in s]
    tags = [j for i in stats_tags for j in i if j]
    for t in set(tags):
        print "Reason - {}: {} fails, {}% of counted {} jobs".format(
            t, tags.count(t), tags.count(t) * 100 / len(s), len(s))


def print_analysis(messages):
    list_messages = []
    for msg in messages:
        list_messages.append(msg)
        print (msg['text'] + (" Patch: " + msg["patch_url"] if VERBOSE else "")
               + (" Build: " + msg["job"]["build_url"] if VERBOSE else ""))
    return list_messages


def main():
    LOGS_DIR = os.path.join(os.environ["HOME"], "tmp", "ci_status")
    #MAIN_PAGE = "http://tripleo.org/cistatus-periodic.html"
    MAIN_PAGE = "http://tripleo.org/cistatus.html"
    # How many jobs to print
    LIMIT_JOBS = 1000
    # How many days to include, None for all days, 1 - for today
    DAYS = 7
    # Which kind of jobs to take? ha, nonha, upgrades, None - for all
    INTERESTED_JOB_TYPE = None  # or None for all (ha, nonha, upgrades, etc)
    EXCLUDED_JOB_TYPE = "containers"
    short_name = sys.argv[1] if len(sys.argv) > 1 else INTERESTED_JOB_TYPE

    stats = run(amount=LIMIT_JOBS,
                days=DAYS,
                job_type=short_name,
                excluded=EXCLUDED_JOB_TYPE,
                down_path=LOGS_DIR,
                page=MAIN_PAGE)
    stats_list = print_analysis(stats)
    print "Statistics:"
    print "Analysis of page:", MAIN_PAGE
    print "Job type:", short_name or "all"
    print_stats(stats_list)


if __name__ == '__main__':
    main()

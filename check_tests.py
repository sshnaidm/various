#!/usr/bin/python
import datetime
import re
import requests
import smtplib
import sys
from email.mime.text import MIMEText
from six.moves.urllib.parse import urljoin
from six.moves.html_parser import HTMLParser


DEBUG = False
JOBS = [
    "periodic-tripleo-ci-centos-7-ovb-ha-tempest",
]
LOG_URL = "http://logs.openstack.org/periodic/"

HREF = re.compile('href="([^"]+)"')
JOBRE = re.compile('[a-z0-9]{7}/')
TESTRE = re.compile('(tempest\.[^ \(\)]+)')
TIMEST = re.compile('(\d{4}-\d{2}-\d{2} \d{2}:\d{2}):\d{2}\.\d+ \|')
TITLE = re.compile('<title>(.*?)</title>')

FAILED = "... FAILED"
OK = "... ok"
ERROR = "... ERROR"
SKIPPED = "... SKIPPED"
RECPTO = ["sshnaidm@redhat.com", "whayutin@redhat.com"]
MAIL_FROM = "sshnaidm@redhat.com"
RH_SMTP = "int-mx.corp.redhat.com"

TESTS = {
    'tempest.scenario.test_volume_boot_pattern.*':
        'http://bugzilla.redhat.com/1272289',
    'tempest.api.identity.*v3.*':
        'https://bugzilla.redhat.com/1266947',
    '.*test_external_network_visibility':
        'https://bugs.launchpad.net/tripleo/+bug/1577769',
}


def die(msg):
    print(msg)
    sys.exit(1)


def get_html(url):
    try:
        resp = requests.get(url)
        if resp is None:
            raise Exception("Get None as result")
    except Exception as e:
        print("Exception %s" % str(e))
        return
    return resp


def get_index(job):
    ''' Get index page of periodic job and returns all links to jobs'''
    url = urljoin(LOG_URL, job)
    res = get_html(url)
    if res is None or not res.ok:
        die("Failed to get job URL %s" % url)
    body = res.content.decode() if res.content else ''
    if not body:
        die("No content in periodic index %s" % url)
    with open("/tmp/mytest", "w") as f:
        f.write(body)
    hrefs = [HREF.search(l).group(1)
             for l in body.splitlines() if HREF.search(l)]
    links = ["/".join((url, link)) for link in hrefs if JOBRE.match(link)]
    if links:
        return links
    else:
        die("No periodic job link were found in %s" % url)


def get_console(job_url):
    ''' Get console page of job'''
    def _good_result(res):
        if res is None or int(res.status_code) not in (200, 404):
            return False
        else:
            return True

    def _get_date(c):
        text = c.splitlines()
        # find last line with timestamp
        for l in text[::-1]:
            if TIMEST.match(l):
                return datetime.datetime.strptime(TIMEST.search(l).group(1),
                                                  "%Y-%m-%d %H:%M")
        return None

    url = urljoin(job_url, "console.html.gz")
    res = get_html(url)
    if not _good_result(res):
        print("Error getting console %s" % url)
        # Try again
        res = get_html(url)
        if not _good_result(res):
            return (None, None, None)
    elif int(res.status_code) == 404:
        url = urljoin(job_url, "console.html")
        res = get_html(url)
        if not _good_result(res):
            # Try again
            res = get_html(url)
            if not _good_result(res):
                print("Error getting console %s" % url)
                return (None, None, None)
    console = res.content.decode('utf-8')
    # with open("/tmp/console", "wt") as f:
    #    f.write(console)
    date = _get_date(console)
    return console, date, url


def get_tests_results(console):
    ''' Get results of tests from console'''
    failed = [TESTRE.search(l).group(1)
              for l in console.splitlines() if FAILED in l]
    ok = [TESTRE.search(l).group(1)
          for l in console.splitlines() if OK in l]
    errors = [TESTRE.search(l).group(1)
              for l in console.splitlines() if ERROR in l]
    all_skipped = [TESTRE.search(l).group(1)
              for l in console.splitlines() if SKIPPED in l]
    return failed, ok, errors


def compare_tests(failures):
    ''' Detect fails covered by bugs and new'''
    covered, new = [], []
    for fail in failures:
        for test in TESTS:
            if re.search(test, fail):
                covered.append(fail)
    new = [fail for fail in failures if fail not in covered]
    return covered, new


def check_bug(b):
    ''' Generic check bug status and name'''
    if 'bugzilla.redhat.com' in b:
        return check_bz_bug(b)
    elif 'bugs.launchpad.net' in b:
        return check_lp_bug(b)


def check_bz_bug(b):
    ''' Return status of a bug in BZ'''
    html = get_html(b)
    if html:
        text = html.content.decode('utf-8')
        name = TITLE.search(text).group(1) if TITLE.search(text) else ''
        h = HTMLParser()
        name = h.unescape(name)
    else:
        name = ''
    return name, None


def check_lp_bug(b):
    ''' Return status of a bug in Launchpad'''
    html = get_html(b)
    if html:
        text = html.content.decode('utf-8')
        name = TITLE.search(text).group(1) if TITLE.search(text) else ''
    else:
        name = ''
    return name, None


def nice_print_bugs(bugs):
    text = ""
    for i in bugs:
        name, status = check_bug(i)
        text += "%s (%s)\n" % (name, i)
    return text


def refresh_bugs():
    ''' Refresh status of bugs'''
    pass


def stats(d):
    ''' Get statistics about test failures'''
    return d


def dummy(subj, body, addresses=RECPTO):
    print("from %s to %s" % (MAIL_FROM, ",".join(addresses)))
    print("[Tempest report] " + subj)
    print(body)


def mail(subj, body, addresses=RECPTO):
    ''' Send mail'''
    if DEBUG:
        return dummy(subj, body, addresses=RECPTO)
    msg = MIMEText(body)
    msg['Subject'] = "[Tempest report] " + subj
    msg['From'] = MAIL_FROM
    msg['To'] = ",".join(addresses)
    s = smtplib.SMTP(RH_SMTP)
    s.sendmail(MAIL_FROM, addresses, msg.as_string())
    s.quit()


def send_unexpected_failure(last):
    ''' Send mail with unexpected failure'''
    mail(
        subj="unexpected failure",
        body="""
Hi, dear mail recipients,
the script is still under development and error just happened.
The debug info is:
link: %s
data: %s

We'll solve it ASAP, thanks for you patience.
            """ % (last['link'], str(last))
    )


def send_report_with_failures(last):
    ''' Send mail with failures today'''
    if not last['run']:
        mail(
            subj="No tests run in last tempest job",
            body="""
Hi, dear mail recipients,
unfortunately in last run of tempest job no tests ran,
it may be problem with TripleO installation,
please check: %s
            """ % last['link']
        )
    else:
        mail(
            subj="Not covered tests failed",
            body="""
Hi, dear mail recipients,
in last tests run we have a few tests that failed, and which are
not covered by bugs, it could be unstable test or new bug,
please check: %s
Not covered tests:

%s

Bugs that are opened:
%s

            """ % (last['link'],
                   "\n".join(last['new']),
                   nice_print_bugs(TESTS.values()))
        )


def send_successful_report(last, nofail=False):
    ''' Send mail with success, no failures'''
    if nofail:
        mail(
            subj="All passed, no tests failed",
            body="""
Hi, dear mail recipients,
in the last run nothing failed, all tests passed.
please check: %s
                """ % last['link']
        )
    else:
        mail(
            subj="No new tests failed",
            body="""
Hi, dear mail recipients,
in the last run only covered by bugs tests failed,
please check: %s
Bugs that are opened:
%s
                """ % (last['link'], nice_print_bugs(TESTS.values()))
        )


def main(upstream=True, downstream=False):
    data = []
    # bugs_status = refresh_bugs()
    if upstream:
        for periodic_job in JOBS:
            index = get_index(periodic_job)
            for run in index:
                console, date, link = get_console(run)
                if not console or not date:
                    continue
                fails, ok, errors = get_tests_results(console)
                d = {
                    'run': True,
                    'date': date,
                    'link': link
                }
                if fails:
                    covered, new = compare_tests(fails)
                    d.update({
                        'failed': fails,
                        'covered': covered,
                        'new': new,
                        'errors': errors,
                    })
                elif not fails and not ok and not errors:
                    d['run'] = False
                data.append(d)

    data = sorted(data, key=lambda x: x['date'])
    last = data[-1]
    if last.get('new') or not last.get('run'):
        # some_stats = stats(d)
        send_report_with_failures(last)
    elif last.get('failed') and not last.get('new'):
        send_successful_report(last=last)
    elif last.get('ok') and not last.get('failed') and not last.get('errors'):
        send_successful_report(last=last, nofail=True)
    else:
        send_unexpected_failure(last)


if __name__ == '__main__':
    main()

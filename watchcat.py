import paramiko
import datetime
import json
import os
import re
import logging
import gzip
import requests
import contextlib
import lzma
import tarfile
import fileinput
from requests import ConnectionError

requests.packages.urllib3.disable_warnings()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('watchcat')
log.setLevel(logging.DEBUG)

DIR = os.path.dirname(os.path.realpath(__file__))
DOWNLOAD_PATH = os.path.join(os.environ["HOME"], "ci-files")
SSH_TIMEOUT = 120
GERRIT_REQ_TIMEOUT = 2
GERRIT_HOST = "review.openstack.org"
GERRIT_PORT = 29418
GERRIT_USER = "robo"
GERRIT_BRANCHES = ("master", "stable/liberty", "stable/mitaka")
TRACKED_JOBS = ("gate-tripleo-ci-f22-upgrades",
                "gate-tripleo-ci-f22-nonha",
                "gate-tripleo-ci-f22-ha",
                "gate-tripleo-ci-f22-containers")
# Regexps
JOB_RE = re.compile("(\S+) (http://logs.openstack.org/\S+) "
                    ": (FAILURE|SUCCESS) in ([hms \d]+)")
PATCH_RE = re.compile("Patch Set (\d+):")
TIME_RE = re.compile("((?P<hour>\d+)h)? *((?P<min>\d+)m)? *((?P<sec>\d+)s)?")

# Patterns regexps
timeout_re = re.compile('Killed\s+timeout -s 9 ')
puppet_re = re.compile('"deploy_stderr": ".+?1;31mError: .+?\W(\w+)::')
resolving_re = re.compile(
    'Could not resolve host: (\S+); Name or service not known')
exec_re = re.compile('mError: (\S+?) \S+ returned 1 instead of one of')
failed_deps_re = re.compile('Failed to build (.*)')
# https://github.com/openstack-infra/project-config/blob/master/
# gerritbot/channels.yaml
PROJECTS = (
    'openstack/tripleo-heat-templates',
    'openstack/dib-utils',
    'openstack/diskimage-builder',
    'openstack/instack',
    'openstack/instack-undercloud',
    'openstack/os-apply-config',
    'openstack/os-cloud-config',
    'openstack/os-collect-config',
    'openstack/os-net-config',
    'openstack/os-refresh-config',
    'openstack/python-tripleoclient',
    'openstack-infra/tripleo-ci',
    'openstack/tripleo-common',
    'openstack/tripleo-image-elements',
    'openstack/tripleo-incubator',
    'openstack/tripleo-puppet-elements',
    'openstack/puppet-pacemaker',
    'openstack/puppet-tripleo',
    'openstack/tripleo-docs',
    'openstack/tripleo-quickstart',
    'openstack/tripleo-specs',
    'openstack/tripleo-ui',
)

PATTERNS = {

    "/console.html": [

        {
            "pattern": "Stack overcloud CREATE_COMPLETE",
            "msg": "Overcloud stack installation: SUCCESS.",
            "tag": "",
        },
        {
            "pattern": "Stack overcloud CREATE_FAILED",
            "msg": "Overcloud stack: FAILED.",
            "tag": "code",
        },
        {
            "pattern": "No valid host was found. There are not enough hosts",
            "msg": "No valid host was found.",
            "tag": "code",
        },
        {
            "pattern": "Failed to connect to trunk.rdoproject.org port 80",
            "msg": "Connection failure to trunk.rdoproject.org.",
            "tag": "infra",
        },
        {
            "pattern": "Overloud pingtest, FAIL",
            "msg": "Overcloud pingtest FAILED.",
            "tag": "code",
        },
        {
            "pattern": "Overcloud pingtest, failed",
            "msg": "Overcloud pingtest FAILED.",
            "tag": "code",
        },
        {
            "pattern": "Error contacting Ironic server: Node ",
            "msg": "Ironic introspection FAIL.",
            "tag": "code",
        },
        {
            "pattern": "Introspection completed with errors:",
            "msg": "Ironic introspection FAIL.",
            "tag": "code",
        },
        {
            "pattern": ": Introspection timeout",
            "msg": "Introspection timeout.",
            "tag": "code",
        },
        {
            "pattern": "is locked by host localhost.localdomain, please retry",
            "msg": "Ironic: Host locking error.",
            "tag": "code",
        },
        {
            "pattern": "Timed out waiting for node ",
            "msg": "Ironic node register FAIL: timeout for node.",
            "tag": "code",
        },
        {
            "pattern": "Killed                  ./testenv-client -b",
            "msg": "Job was killed by testenv-client. Timeout??",
            "tag": "infra",
        },
        {
            "pattern": timeout_re,
            "msg": "Killed by timeout.",
            "tag": "infra",
        },
        {
            "pattern": puppet_re,
            "msg": "Puppet {} FAIL.",
            "tag": "code",
        },
        {
            "pattern": exec_re,
            "msg": "Program {} FAIL.",
            "tag": "code",
        },
        {
            "pattern": "ERROR:dlrn:cmd failed. See logs at",
            "msg": "Delorean FAIL.",
            "tag": "code",
        },
        {
            "pattern": "500 Internal Server Error: Failed to upload image",
            "msg": "Glance upload FAIL.",
            "tag": "code",
        },
        {
            "pattern": "Slave went offline during the build",
            "msg": "Jenkins slave FAIL.",
            "tag": "infra",
        },
        {
            "pattern": resolving_re,
            "msg": "DNS resolve of {} FAIL.",
            "tag": "infra",
        },
        {
            "pattern": "fatal: The remote end hung up unexpectedly",
            "msg": "Git clone repo FAIL.",
            "tag": "infra",
        },
        {
            "pattern": "Create timed out       | CREATE_FAILED",
            "msg": "Create timed out.",
            "tag": "code",
        },
        {
            "pattern": "[overcloud]: CREATE_FAILED Create timed out",
            "msg": "Create timed out.",
            "tag": "code",
        },
        {
            "pattern": "FATAL: no longer a configured node for ",
            "msg": "Slave FAIL: no longer a configured node",
            "tag": "infra",
        },
        {
            "pattern": ("cd: /opt/stack/new/delorean/data/repos: "
                        "No such file or directory"),
            "msg": "Delorean repo build FAIL.",
            "tag": "code",
        },
        {
            "pattern": ("[ERROR] - SEVERE ERROR occurs: "
                        "java.lang.InterruptedException"),
            "msg": "Jenkins lave FAIL: InterruptedException",
            "tag": "infra",
        },
        {
            "pattern": ("Killed                  bash -xe "
                        "/opt/stack/new/tripleo-ci/toci_gate_test.sh"),
            "msg": "Main script timeout",
            "tag": "infra",
        },
        {
            "pattern": ("Command 'instack-install-undercloud' "
                        "returned non-zero exit status"),
            "msg": "Undercloud install FAIL.",
            "tag": "code",
        },
        {
            "pattern": failed_deps_re,
            "msg": "Failed to build dep {}.",
            "tag": "infra",
        },
    ],

    '/logs/postci.txt.gz': [
        {
            "pattern": puppet_re,
            "msg": "Puppet {} FAIL.",
            "tag": "code",
        },
    ],
    '/logs/overcloud-controller-0.tar.xz//var/log/neutron/server.log': [
        {
            "pattern": 'Extension router-service-type not supported',
            "msg": "Testing pattern, please ignore.",
            "tag": "code",
        },
    ]
}


class SSH(object):
    def __init__(self,
                 host, port, user, timeout=None, key=None, key_path=None):
        self.ssh_cl = paramiko.SSHClient()
        self.ssh_cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        log.debug("Executing ssh {user}@{host}:{port}".format(
            user=user, host=host, port=port))
        self.ssh_cl.connect(hostname=host,
                            port=port,
                            username=user,
                            timeout=timeout,
                            pkey=key,
                            key_filename=key_path)

    def exe(self, cmd):
        log.debug("Executing cmd by ssh: {cmd}".format(cmd=cmd))
        stdin, stdout, stderr = self.ssh_cl.exec_command(cmd)
        return stdin, stdout.read(), stderr.read()

    def close(self):
        self.ssh_cl.close()


class Gerrit(object):
    def __init__(self, *cmds):
        self.key_path = os.path.join(DIR, "robi_id_rsa")

    def get_project_patches(self, projects):
        def filtered(x):
            return [json.loads(i) for i in x.splitlines() if 'project' in i]

        data = []
        self.ssh = SSH(host=GERRIT_HOST,
                       port=GERRIT_PORT,
                       user=GERRIT_USER,
                       timeout=GERRIT_REQ_TIMEOUT,
                       key_path=self.key_path)
        cmd_template = ('gerrit query "status: open project: '
                        '{project} '
                        'branch: {branch}" '
                        '--comments '
                        '--format JSON '
                        'limit: {limit} '
                        '--patch-sets '
                        '--current-patch-set')
        for proj in projects:
            for branch in GERRIT_BRANCHES:
                command = cmd_template.format(
                    project=proj, branch=branch, limit=200)
                out, err = self.ssh.exe(command)[1:]
                data += filtered(out)
        self.ssh.close()
        return data


class Patch(object):
    def __init__(self, data):
        self.data = data
        self.branch = data['branch']
        self.project = data['project']
        self.status = data['status']
        self.topic = data.get('topic', '')
        self.url = data['url']
        self.commitmsg = data['commitMessage']
        self.created = datetime.datetime.fromtimestamp(data['createdOn'])
        self.lastup = datetime.datetime.fromtimestamp(data['lastUpdated'])
        self.patch_umber = data['number']
        self.gid = data['id']
        self.owner = data['owner']
        self.sets = [Patchset(i, data) for i in data['patchSets']]
        self.current = Patchset(data['currentPatchSet'], data)
        self.comments = data['comments']
        self.jobs = self.get_jobs()
        self.subject = data['subject']

    def _extract_job_from_comment(self, comment):
        def parse_time(x):
            timest = TIME_RE.search(x.strip())
            hour, minute, sec = map(int, (
                timest.groupdict()['hour'] or 0,
                timest.groupdict()['min'] or 0,
                timest.groupdict()['sec'] or 0))
            # Resolution in minutes
            return 60 * hour + minute

        jobs = []
        text = comment['message']
        timestamp = datetime.datetime.fromtimestamp(comment['timestamp'])
        data = JOB_RE.findall(text)
        if data:
            patch_num = PATCH_RE.search(text).group(1)
            patchset = [s for s in self.sets if s.number == int(patch_num)][0]
            for j in data:
                job = Job(
                    name=j[0],
                    log_url=j[1],
                    status=j[2],
                    length=parse_time(j[3]),
                    patch=self,
                    patchset=patchset,
                    timestamp=timestamp
                )
                jobs.append(job)
        return jobs

    def get_jobs(self):
        res = []
        for comment in self.comments:
            res += self._extract_job_from_comment(comment)
        return res


class Patchset(object):
    def __init__(self, data, patch):
        self.number = int(data['number'])
        self.patchset_ctime = datetime.datetime.fromtimestamp(
            data['createdOn'])
        self.ref = data['ref']
        self.patchset_url = ('https://review.openstack.org/#/c/' +
                             patch['number'] + "/" + data['number'])


class Job(object):
    def __init__(self,
                 name, log_url, status, length, patch, patchset, timestamp):
        self.name = name
        self.log_url = log_url
        self.fail = status == 'FAILURE'
        self.status = status
        self.length = length
        self.patch = patch
        self.patchset = patchset
        self.ts = timestamp
        self.log_hash = self.hashed(self.log_url)

    def hashed(self, url):
        return url.strip("/").split("/")[-1]

    def __repr__(self):
        return str({'name': self.name,
                    'log_url': self.log_url,
                    'status': self.status,
                    'project': self.patch.project,
                    'branch': self.patch.branch,
                    'length': str(self.length),
                    'patchset': str(self.patchset.number),
                    'patchset_url': str(self.patchset.patchset_url),
                    'date': datetime.datetime.strftime(self.ts, "%m-%d %H:%M")
                    })


class Filter:
    def __init__(self,
                 data,
                 days=None,
                 dates=None,
                 limit=None,
                 short=None,
                 fail=True,
                 exclude=None,
                 job_type=None):
        self.data = sorted(data, key=lambda i: i.ts, reverse=True)
        self.default = [self.f_only_tracked]
        self.limit = limit
        self.filters = [
            (self.f_days, days),
            (self.f_short, short),
            (self.f_fail, fail),
            (self.f_exclude, exclude),
            (self.f_dates, dates),
            (self.f_jobtype, job_type),
        ]

    def run(self):
        for fil in self.default:
            self.data = [job for job in self.data if fil(job)]
        for filt in self.filters:
            self.data = [job for job in self.data if filt[0](job, filt[1])]
        if self.limit:
            return list(self.data)[:self.limit]
        else:
            return list(self.data)

    def f_only_tracked(self, job):
        return job.name in TRACKED_JOBS

    def _day_format(self, x):
        return datetime.date.strftime(x, "%m-%d")

    def _job_day_format(self, x):
        return  datetime.date.strftime(x, "%m-%d")

    def f_days(self, job, days):
        if not days:
            return True
        today = datetime.date.today()
        dates = []
        for i in xrange(days):
            dates.append(self._day_format(today - datetime.timedelta(days=i)))
        job_date = self._job_day_format(job.ts)
        return job_date in dates

    def f_dates(self, job, dates):
        if not dates:
            return True
        job_date = self._job_day_format(job.ts)
        return job_date in dates


    def f_short(self, job, short):
        def shorten(x):
            return {'gate-tripleo-ci-f22-upgrades': 'upgrades',
                    'gate-tripleo-ci-f22-nonha': 'nonha',
                    'gate-tripleo-ci-f22-ha': 'ha',
                    'gate-tripleo-ci-f22-containers': 'containers'
                    }.get(x, x)

        if not short:
            return True
        return shorten(job.name) == short

    def f_fail(self, job, fail):
        return True if not fail else job.fail

    def f_exclude(self, job, exclude):
        return True if not exclude else job.name != exclude

    def f_jobtype(self, job, job_type):
        return True if not job_type else job.name == job_type



class Web:
    def __init__(self, url):
        self.url = url

    def get(self, ignore404=False):
        log.debug("GET {url} with ignore404={i}".format(
            url=self.url, i=str(ignore404)))
        req = requests.get(self.url)
        if req.status_code != 200:
            if not (ignore404 and req.status_code == 404):
                log.error("Page {url} got status {code}".format(
                    url=self.url, code=req.status_code))
        return req


class JobFile:
    def __init__(self, job, path=DOWNLOAD_PATH, file_link=None, build=None):
        self.job_dir = os.path.join(path, job.log_hash)
        if not os.path.exists(self.job_dir):
            os.makedirs(self.job_dir)
        # /logs/undercloud.tar.gz//var/log/nova/nova-compute.log
        self.file_link = file_link or "/console.html"
        self.file_url = job.log_url + self.file_link.split("//")[0]
        self.file_path = None
        self.build = build

    def get_file(self):
        if self.build:
            return self.get_build_page()
        if "//" in self.file_link:
            return self.get_tarred_file()
        else:
            return self.get_regular_file()

    def get_build_page(self):
        web = Web(url=self.build)
        try:
            req = web.get()
        except ConnectionError:
            log.error("Jenkins page {} is unavailable".format(self.build))
            return None
        if req.status_code != 200:
            return None
        else:
            self.file_path = os.path.join(self.job_dir, "build_page.gz")
            with gzip.open(self.file_path, "wb") as f:
                f.write(req.content)
            return self.file_path

    def get_regular_file(self):
        log.debug("Get regular file {}".format(self.file_link))
        self.file_name = os.path.basename(self.file_link).rstrip(".gz") + ".gz"
        self.file_path = os.path.join(self.job_dir, self.file_name)
        if os.path.exists(self.file_path):
            log.debug("File {} is already downloaded".format(self.file_path))
            return self.file_path
        else:
            web = Web(url=self.file_url)
            ignore404 = self.file_link == "/console.html"
            req = web.get(ignore404=ignore404)
            if req.status_code != 200 and self.file_link == "/console.html":
                self.file_url += ".gz"
                web = Web(url=self.file_url)
                log.debug("Trying to download gzipped console")
                req = web.get()
            if req.status_code != 200:
                log.error("Failed to retrieve URL: {}".format(self.file_url))
                return None
            else:
                with gzip.open(self.file_path, "wb") as f:
                    f.write(req.content)
            return self.file_path

    def _extract(self, tar, root_dir, file_path):
        log.debug("Extracting file {} from {} in {}".format(
                file_path, tar, root_dir))
        try:
            with contextlib.closing(lzma.LZMAFile(tar)) as xz:
                with tarfile.open(fileobj=xz) as f:
                    f.extract(file_path, path=root_dir)
            return True
        except Exception as e:
            log.error("Error when untarring file {} from {} in {}:{}".format(
                file_path, tar, root_dir, e))
            return False

    def get_tarred_file(self):
        tar_file_link, intern_path = self.file_link.split("//")
        log.debug("Get file {} from tar.gz archive {}".format(intern_path, tar_file_link))
        tar_base_name = os.path.basename(tar_file_link)
        tar_prefix = tar_base_name.split(".")[0]
        tar_root_dir = os.path.join(self.job_dir, tar_prefix)
        self.file_path = os.path.join(tar_root_dir, intern_path)

        if os.path.exists(self.file_path + ".gz"):
            log.debug("File {} is already downloaded".format(
                self.file_path + ".gz"))
            return self.file_path + ".gz"
        if not os.path.exists(tar_root_dir):
            os.makedirs(tar_root_dir)
        tar_file_path = os.path.join(self.job_dir, tar_base_name)
        if not os.path.exists(tar_file_path):
            web = Web(url=self.file_url )
            req = web.get()
            if req.status_code != 200:
                return None
            else:
                with open(tar_file_path, "wb") as f:
                    f.write(req.content)
        if self._extract(tar_file_path, tar_root_dir, intern_path):
            with open(self.file_path, 'rb') as f:
                with gzip.open(self.file_path + ".gz", 'wb') as zipped_file:
                    zipped_file.writelines(f)
            os.remove(self.file_path)
            self.file_path += ".gz"
            return self.file_path
        else:
            return None


def analysis(job, down_path):
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

    message = {
        "text": '',
        "tags": [],
        "msg": '',
        "reason": False,
        "job": job,
        "periodic": False,
    }

    msg = set()
    tags = set()
    found_reason = True
    console = JobFile(job, path=down_path).get_file()
    if not console:
        message['text'] = message['msg'] = 'No console file'
        message['tags'] = ['infra']
        message['reason'] = True
        return message
    files = PATTERNS.keys()
    for file in files:
        jfile = JobFile(job, path=down_path, file_link=file).get_file()
        if not jfile:
            log.error("File {} is not downloaded, "
                      "skipping its patterns".format(file))
            break
        else:
            try:
                log.debug("Opening file for scan: {}".format(jfile))
                for line in fileinput.input(
                        jfile, openhook=fileinput.hook_compressed):
                    for p in PATTERNS[file]:
                        if (line_match(p["pattern"], line) and
                                p["msg"] not in msg):
                            msg.add(p["msg"].format(
                                line_match(p["pattern"], line)))
                            tags.add(p["tag"])
                if not msg:
                    log.debug("No patterns in file {}".format(jfile))
                    msg = {"Reason was NOT FOUND. Please investigate"}
                    found_reason = False
                    tags.add("unknown")
            except Exception as e:
                log.error("Exception when parsing {}: {}".format(jfile, str(e)))
                msg = {"Error when parsing logs. Please investigate"}
                found_reason = False
                tags.add("unknown")
    templ = ("{date}\t"
             "{job_type:38}\t"
             "{delim}\t"
             "{msg:60}\t"
             "{delim}\t"
             "log: {log_url}")
    text = templ.format(
        msg=" ".join(sorted(msg)),
        delim="||" if found_reason else "XX",
        date=job.ts.strftime("%m-%d %H:%M"),
        job_type=job.name,
        log_url=job.log_url
    )
    message = {
        "text": text,
        "tags": tags,
        "msg": msg,
        "reason": found_reason,
        "job": job,
        "periodic": "periodic" in job.name,
    }
    return message


def meow(days=None,
         dates=None,
         limit=None,
         short=None,
         fail=True,
         exclude=None,
         job_type=None,
         down_path=DOWNLOAD_PATH,
         ):
    g = Gerrit()
    gerrit = g.get_project_patches(['openstack/tripleo-common'])
    with open("/tmp/gerrit", "w") as f:
        #gerrit = json.loads(f.read())
        s = json.dumps(gerrit)
        f.write(s)
    jobs = (job for patch in gerrit for job in Patch(patch).jobs)
    f = Filter(
        jobs,
        days=days,
        dates=dates,
        limit=limit,
        short=short,
        fail=fail,
        exclude=exclude,
        job_type=job_type
        # dates=["04-19", "04-29", "04-28"],
        # limit=None,
        # exclude='gate-tripleo-ci-f22-containers'
    )
    filtered = f.run()
    ready = []
    for job in filtered:
        ready.append(analysis(job, down_path=down_path))
    return ready


def main():
    for m in  meow(limit=2, dates=["04-19"]):
        print m["text"]



if __name__ == "__main__":
    main()

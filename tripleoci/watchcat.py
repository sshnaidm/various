import json
import config
from config import log
from utils import Gerrit
from analysis import analyze
from periodic import Periodic
from patches import Patch
from filters import Filter


# # Regexps
# JOB_RE = re.compile(r"(\S+) (http://logs.openstack.org/\S+) "
#                     r": (FAILURE|SUCCESS) in ([hms \d]+)")
# PATCH_RE = re.compile(r"Patch Set (\d+):")
# TIME_RE = re.compile(r"((?P<hour>\d+)h)? *((?P<min>\d+)m)? *((?P<sec>\d+)s)?")
#
# # Jobs regexps
# branch_re = re.compile(r"\+ export ZUUL_BRANCH=(\S+)")
# ts_re = re.compile(r"(201\d-[01]\d-[0123]\d [012]\d:\d\d):\d\d\.\d\d\d")



#
# class Periodic(object):
#     def __init__(self, url, down_path=config.DOWNLOAD_PATH, limit=None):
#         self.per_url = url
#         self.down_path = down_path
#         self.limit = limit
#         self.jobs = self.get_jobs()
#
#     def _get_index(self):
#         w = Web(self.per_url)
#         req = w.get()
#         if req.status_code != 200:
#             log.error("Can not retrieve periodic page {}".format(self.per_url))
#             return None
#         return req.content
#
#     def _get_console(self, job):
#         path = os.path.join(
#             self.down_path, job["log_hash"], "console.html.gz")
#         if os.path.exists(path):
#             log.debug("Console is already here: {}".format(path))
#             return path
#         web = Web(job["log_url"] + "/console.html")
#         req = web.get(ignore404=True)
#         if req.status_code == 404:
#             url = job["log_url"] + "/console.html.gz"
#             web = Web(url=url)
#             log.debug("Trying to download gzipped console")
#             req = web.get()
#         if req.status_code != 200:
#             log.error("Failed to retrieve console: {}".format(job["log_url"]))
#             return None
#         else:
#             if not os.path.exists(os.path.dirname(path)):
#                 os.makedirs(os.path.dirname(path))
#             with gzip.open(path, "wb") as f:
#                 f.write(req.content)
#         return path
#
#     def parse_index(self, text):
#         jobs = []
#         et = etree.HTML(text)
#         trs = [i for i in et.xpath("//tr") if not i.xpath("th")][1:]
#         for tr in trs:
#             job = {}
#             td1, td2 = tr.xpath("td")[1:3]
#             lhash = td1.xpath("a")[0].attrib['href'].rstrip("/")
#             job["log_hash"] = lhash
#             job["log_url"] = self.per_url.rstrip("/") + "/" + lhash
#             job["ts"] = datetime.datetime.strptime(td2.text.strip(),
#                                                    "%d-%b-%Y %H:%M")
#             job["name"] = self.per_url.rstrip("/").split("/")[-1]
#             jobs.append(job)
#         return sorted(jobs, key=lambda x: x['ts'], reverse=True)
#
#     def _parse_ts(self, ts):
#         return datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M")
#
#     def _get_more_data(self, j):
#         def delta(e, s):
#             return (self._parse_ts(e) - self._parse_ts(s)).seconds / 60
#
#         start = end = None
#         j.update({
#             'status': 'FAILURE',
#             'fail': True,
#             'branch': ''
#         })
#         console = self._get_console(j)
#         if not console:
#             log.error("Failed to get console for periodic {}".format(repr(j)))
#         else:
#             for line in fileinput.input(console,
#                                         openhook=fileinput.hook_compressed):
#                 if "Finished: SUCCESS" in line:
#                     j['fail'] = False
#                     j['status'] = 'SUCCESS'
#                 elif "Finished: FAILURE" in line:
#                     j['fail'] = True
#                     j['status'] = 'FAILURE'
#                 elif "Finished: ABORTED" in line:
#                     j['fail'] = True
#                     j['status'] = 'ABORTED'
#                 if branch_re.search(line):
#                     j['branch'] = branch_re.search(line).group(1)
#                 if 'Started by user' in line:
#                     start = ts_re.search(line).group(1)
#                 if "Finished: " in line:
#                     end = ts_re.search(line).group(1)
#             j['length'] = delta(end, start) if start and end else 0
#         return j
#
#     def get_jobs(self):
#         index = self._get_index()
#         jobs = self.parse_index(index)[:self.limit]
#         for j in jobs:
#             raw = self._get_more_data(j)
#             yield PeriodicJob(**raw)
#
#
# class Patch(object):
#     def __init__(self, data):
#         self.data = data
#         self.branch = data['branch']
#         self.project = data['project']
#         self.status = data['status']
#         self.topic = data.get('topic', '')
#         self.url = data['url']
#         self.commitmsg = data['commitMessage']
#         self.created = datetime.datetime.fromtimestamp(data['createdOn'])
#         self.lastup = datetime.datetime.fromtimestamp(data['lastUpdated'])
#         self.patch_number = data['number']
#         self.gid = data['id']
#         self.owner = data['owner']
#         self.sets = [Patchset(i, data) for i in data['patchSets']]
#         self.current = Patchset(data['currentPatchSet'], data)
#         self.comments = data['comments']
#         self.jobs = self.get_jobs()
#         self.subject = data['subject']
#
#     def _extract_job_from_comment(self, comment):
#         def parse_time(x):
#             timest = TIME_RE.search(x.strip())
#             hour, minute, sec = map(int, (
#                 timest.groupdict()['hour'] or 0,
#                 timest.groupdict()['min'] or 0,
#                 timest.groupdict()['sec'] or 0))
#             # Resolution in minutes
#             return 60 * hour + minute
#
#         jobs = []
#         text = comment['message']
#         timestamp = datetime.datetime.fromtimestamp(comment['timestamp'])
#         data = JOB_RE.findall(text)
#         if data:
#             patch_num = PATCH_RE.search(text).group(1)
#             patchset = [s for s in self.sets if s.number == int(patch_num)][0]
#             for j in data:
#                 job = Job(
#                     name=j[0],
#                     log_url=j[1],
#                     status=j[2],
#                     length=parse_time(j[3]),
#                     patch=self,
#                     patchset=patchset,
#                     timestamp=timestamp
#                 )
#                 jobs.append(job)
#         return jobs
#
#     def get_jobs(self):
#         res = []
#         for comment in self.comments:
#             res += self._extract_job_from_comment(comment)
#         return res
#
#
# class Patchset(object):
#     def __init__(self, data, patch):
#         self.number = int(data['number'])
#         self.patchset_ctime = datetime.datetime.fromtimestamp(
#             data['createdOn'])
#         self.ref = data['ref']
#         self.patchset_url = ('https://review.openstack.org/#/c/' +
#                              patch['number'] + "/" + data['number'])
#
#
# class Job(object):
#     def __init__(self,
#                  name, log_url, status, length, patch, patchset, timestamp):
#         self.name = name
#         self.log_url = log_url
#         self.fail = status == 'FAILURE'
#         self.status = status
#         self.length = length
#         self.patch = patch
#         self.patchset = patchset
#         self.ts = timestamp
#         self.branch = self.patch.branch if self.patch else ""
#         self.datetime = self.ts.strftime("%m-%d %H:%M")
#         self.log_hash = self.hashed(self.log_url)
#         self.periodic = False
#
#     def hashed(self, url):
#         return url.strip("/").split("/")[-1]
#
#     def __repr__(self):
#         return str({'name': self.name,
#                     'log_url': self.log_url,
#                     'status': self.status,
#                     'project': self.patch.project if self.patch else "",
#                     'branch': self.branch,
#                     'length': str(self.length),
#                     'patchset': str(
#                         self.patchset.number) if self.patchset else "",
#                     'patchset_url': str(
#                         self.patchset.patchset_url) if self.patchset else "",
#                     'date': datetime.datetime.strftime(self.ts, "%m-%d %H:%M")
#                     })
#

# class PeriodicJob(Job):
#     def __init__(self, **kwargs):
#         super(PeriodicJob, self).__init__(
#             name=kwargs["name"],
#             log_url=kwargs["log_url"],
#             status=kwargs["status"],
#             length=kwargs["length"],
#             timestamp=kwargs["ts"],
#             patch=None,
#             patchset=None
#         )
#         self.periodic = True


#
# class Web:
#     def __init__(self, url):
#         self.url = url
#
#     def get(self, ignore404=False):
#         log.debug("GET {url} with ignore404={i}".format(
#             url=self.url, i=str(ignore404)))
#         req = requests.get(self.url)
#         if req.status_code != 200:
#             if not (ignore404 and req.status_code == 404):
#                 log.error("Page {url} got status {code}".format(
#                     url=self.url, code=req.status_code))
#         return req


# class JobFile:
#     def __init__(self, job, path=config.DOWNLOAD_PATH, file_link=None,
#                  build=None):
#         self.job_dir = os.path.join(path, job.log_hash)
#         if not os.path.exists(self.job_dir):
#             os.makedirs(self.job_dir)
#         # /logs/undercloud.tar.gz//var/log/nova/nova-compute.log
#         self.file_link = file_link or "/console.html"
#         self.file_url = job.log_url + self.file_link.split("//")[0]
#         self.file_path = None
#         self.build = build
#
#     def get_file(self):
#         if self.build:
#             return self.get_build_page()
#         if "//" in self.file_link:
#             return self.get_tarred_file()
#         else:
#             return self.get_regular_file()
#
#     def get_build_page(self):
#         web = Web(url=self.build)
#         try:
#             req = web.get()
#         except ConnectionError:
#             log.error("Jenkins page {} is unavailable".format(self.build))
#             return None
#         if req.status_code != 200:
#             return None
#         else:
#             self.file_path = os.path.join(self.job_dir, "build_page.gz")
#             with gzip.open(self.file_path, "wb") as f:
#                 f.write(req.content)
#             return self.file_path
#
#     def get_regular_file(self):
#         log.debug("Get regular file {}".format(self.file_link))
#         self.file_name = os.path.basename(self.file_link).rstrip(".gz") + ".gz"
#         self.file_path = os.path.join(self.job_dir, self.file_name)
#         if os.path.exists(self.file_path):
#             log.debug("File {} is already downloaded".format(self.file_path))
#             return self.file_path
#         else:
#             web = Web(url=self.file_url)
#             ignore404 = self.file_link == "/console.html"
#             req = web.get(ignore404=ignore404)
#             if req.status_code != 200 and self.file_link == "/console.html":
#                 self.file_url += ".gz"
#                 web = Web(url=self.file_url)
#                 log.debug("Trying to download gzipped console")
#                 req = web.get()
#             if req.status_code != 200:
#                 log.error("Failed to retrieve URL: {}".format(self.file_url))
#                 return None
#             else:
#                 with gzip.open(self.file_path, "wb") as f:
#                     f.write(req.content)
#             return self.file_path
#
#     def _extract(self, tar, root_dir, file_path):
#         log.debug("Extracting file {} from {} in {}".format(
#             file_path, tar, root_dir))
#         try:
#             with contextlib.closing(lzma.LZMAFile(tar)) as xz:
#                 with tarfile.open(fileobj=xz) as f:
#                     f.extract(file_path, path=root_dir)
#             return True
#         except Exception as e:
#             log.error("Error when untarring file {} from {} in {}:{}".format(
#                 file_path, tar, root_dir, e))
#             return False
#
#     def get_tarred_file(self):
#         tar_file_link, intern_path = self.file_link.split("//")
#         log.debug("Get file {} from tar.gz archive {}".format(intern_path,
#                                                               tar_file_link))
#         tar_base_name = os.path.basename(tar_file_link)
#         tar_prefix = tar_base_name.split(".")[0]
#         tar_root_dir = os.path.join(self.job_dir, tar_prefix)
#         self.file_path = os.path.join(tar_root_dir, intern_path)
#
#         if os.path.exists(self.file_path + ".gz"):
#             log.debug("File {} is already downloaded".format(
#                 self.file_path + ".gz"))
#             return self.file_path + ".gz"
#         if not os.path.exists(tar_root_dir):
#             os.makedirs(tar_root_dir)
#         tar_file_path = os.path.join(self.job_dir, tar_base_name)
#         if not os.path.exists(tar_file_path):
#             web = Web(url=self.file_url)
#             req = web.get()
#             if req.status_code != 200:
#                 return None
#             else:
#                 with open(tar_file_path, "wb") as f:
#                     f.write(req.content)
#         if self._extract(tar_file_path, tar_root_dir, intern_path):
#             with open(self.file_path, 'rb') as f:
#                 with gzip.open(self.file_path + ".gz", 'wb') as zipped_file:
#                     zipped_file.writelines(f)
#             os.remove(self.file_path)
#             self.file_path += ".gz"
#             return self.file_path
#         else:
#             return None
#
#
# def analysis(job, down_path):
#     def line_match(pat, line):
#         if isinstance(pat, re._pattern_type):
#             if not pat.search(line):
#                 return False
#             elif pat.search(line).groups():
#                 return pat.search(line).group(1)
#             else:
#                 return True
#         if isinstance(pat, str):
#             return pat in line
#
#     message = {
#         "text": '',
#         "tags": [],
#         "msg": '',
#         "reason": False,
#         "job": job,
#         "periodic": False,
#     }
#
#     msg = set()
#     tags = set()
#     found_reason = True
#     console = JobFile(job, path=down_path).get_file()
#     if not console:
#         message['text'] = message['msg'] = 'No console file'
#         message['tags'] = ['infra']
#         message['reason'] = True
#         return message
#     files = PATTERNS.keys()
#     for file in files:
#         jfile = JobFile(job, path=down_path, file_link=file).get_file()
#         if not jfile:
#             log.error("File {} is not downloaded, "
#                       "skipping its patterns".format(file))
#             continue
#         else:
#             try:
#                 log.debug("Opening file for scan: {}".format(jfile))
#                 for line in fileinput.input(
#                         jfile, openhook=fileinput.hook_compressed):
#                     for p in PATTERNS[file]:
#                         if (line_match(p["pattern"], line) and
#                                 p["msg"] not in msg):
#                             msg.add(p["msg"].format(
#                                 line_match(p["pattern"], line)))
#                             tags.add(p["tag"])
#
#             except Exception as e:
#                 log.error("Exception when parsing {}: {}".format(
#                     jfile, str(e)))
#                 msg = {"Error when parsing logs. Please investigate"}
#                 found_reason = False
#                 tags.add("unknown")
#     if not msg:
#         log.debug("No patterns in job files {}".format(job))
#         msg = {"Reason was NOT FOUND. Please investigate"}
#         found_reason = False
#         tags.add("unknown")
#     templ = ("{date}\t"
#              "{job_type:38}\t"
#              "{delim}\t"
#              "{msg:60}\t"
#              "{delim}\t"
#              "log: {log_url}")
#     text = templ.format(
#         msg=" ".join(sorted(msg)),
#         delim="||" if found_reason else "XX",
#         date=job.datetime,
#         job_type=job.name,
#         log_url=job.log_url
#     )
#     message = {
#         "text": text,
#         "tags": tags,
#         "msg": msg,
#         "reason": found_reason,
#         "job": job,
#         "periodic": "periodic" in job.name,
#     }
#     return message


def meow(days=None,
         dates=None,
         limit=None,
         short=None,
         fail=True,
         exclude=None,
         job_type=None,
         down_path=config.DOWNLOAD_PATH,
         periodic=True,
         ):
    if not periodic:
        g = Gerrit()
        # gerrit = g.get_project_patches(config.PROJECTS)
        # with open("/tmp/gerrit", "w") as f:
        #     s = json.dumps(gerrit)
        #     f.write(s)
        # If debug mode
        with open("/tmp/gerrit", "r") as f:
            gerrit = json.loads(f.read())
        jobs = (job for patch in gerrit for job in Patch(patch).jobs)
    else:
        jobs = (job
                for url in config.PERIODIC_URLS
                for job in Periodic(
                    url, down_path=down_path, limit=limit).jobs)
    f = Filter(
        jobs,
        days=days,
        dates=dates,
        limit=limit,
        short=short,
        fail=fail,
        exclude=exclude,
        job_type=job_type,
        periodic=periodic
    )
    filtered = f.run()
    ready = []
    for job in filtered:
        ready.append(analyze(job, down_path=down_path))
    return ready


def main():
    for m in meow(limit=2, dates=["05-01"], periodic=True):
        print m["text"]


if __name__ == "__main__":
    main()

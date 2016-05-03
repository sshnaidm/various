import fileinput
import re

from config import log
from patterns import PATTERNS
from utils import JobFile


def analyze(job, down_path):
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
            continue
        else:
            try:
                log.debug("Opening file for scan: {}".format(jfile))
                for line in fileinput.input(
                        jfile, openhook=fileinput.hook_compressed):
                    for p in PATTERNS[file]:
                        if (line_match(p["pattern"], line) and
                                p["msg"] not in msg):
                            log.debug("Found pattern {} in file {}:{}".format(
                                repr(p), file, jfile))
                            msg.add(p["msg"].format(
                                line_match(p["pattern"], line)))
                            tags.add(p["tag"])

            except Exception as e:
                log.error("Exception when parsing {}: {}".format(
                    jfile, str(e)))
                msg = {"Error when parsing logs. Please investigate"}
                found_reason = False
                tags.add("unknown")
    if not msg:
        log.debug("No patterns in job files {}".format(job))
        msg = {"Reason was NOT FOUND. Please investigate"}
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
        date=job.datetime,
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

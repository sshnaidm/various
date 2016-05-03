import contextlib
import gzip
import json
import lzma
import os
import paramiko
import requests
import tarfile
import time
from requests import ConnectionError

import config
from config import log

requests.packages.urllib3.disable_warnings()

DIR = os.path.dirname(os.path.realpath(__file__))


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
        try:
            stdin, stdout, stderr = self.ssh_cl.exec_command(cmd)
        except paramiko.ssh_exception.SSHException as e:
            log.error("SSH command failed: {}\n{}".format(cmd, e))
            return None, None, None
        return stdin, stdout.read(), stderr.read()

    def close(self):
        log.debug("Closing SSH connection")
        self.ssh_cl.close()


class Gerrit(object):
    def __init__(self):
        self.key_path = os.path.join(DIR, "robi_id_rsa")
        self.ssh = None

    def get_project_patches(self, projects):
        def filtered(x):
            return [json.loads(i) for i in x.splitlines() if 'project' in i]

        data = []

        cmd_template = ('gerrit query "status: open project: '
                        '{project} '
                        'branch: {branch}" '
                        '--comments '
                        '--format JSON '
                        'limit: {limit} '
                        '--patch-sets '
                        '--current-patch-set')
        for proj in projects:
            # Start SSH for every project from scratch because SSH timeout
            self.ssh = SSH(host=config.GERRIT_HOST,
                           port=config.GERRIT_PORT,
                           user=config.GERRIT_USER,
                           timeout=config.GERRIT_REQ_TIMEOUT,
                           key_path=self.key_path)
            for branch in config.GERRIT_BRANCHES:
                command = cmd_template.format(
                    project=proj,
                    branch=branch,
                    limit=config.GERRIT_PATCH_LIMIT)
                out, err = self.ssh.exe(command)[1:]
                if err:
                    log.error("Error with ssh:{}".format(err))
                data += filtered(out)
            self.ssh.close()
            # Let's not ddos Gerrit
            time.sleep(1)
        return data


class Web(object):
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


class JobFile(object):
    def __init__(self, job, path=config.DOWNLOAD_PATH, file_link=None,
                 build=None):
        self.job_dir = os.path.join(path, job.log_hash)
        if not os.path.exists(self.job_dir):
            os.makedirs(self.job_dir)
        # /logs/undercloud.tar.gz//var/log/nova/nova-compute.log
        self.file_link = file_link or "/console.html"
        self.file_url = job.log_url + self.file_link.split("//")[0]
        self.file_path = None
        self.build = build
        self.file_name = None

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
        log.debug("Get file {} from tar.gz archive {}".format(intern_path,
                                                              tar_file_link))
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
            web = Web(url=self.file_url)
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

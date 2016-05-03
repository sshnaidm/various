import json
import config
from config import log
from utils import Gerrit
from analysis import analyze
from periodic import Periodic
from patches import Patch
from filters import Filter


def meow(days=None,
         dates=None,
         limit=None,
         short=None,
         fail=True,
         exclude=None,
         job_type=None,
         down_path=config.DOWNLOAD_PATH,
         periodic=False,
         ):
    if not periodic:
        g = Gerrit()
        #gerrit = g.get_project_patches(config.PROJECTS)
        # Dump gerrit data for investigation
        #with open("/tmp/gerrit", "w") as f:
        #    f.write(json.dumps(gerrit))
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
    for m in meow(limit=12, periodic=True, short="ha"):
        print m["text"]


if __name__ == "__main__":
    main()

import os
import jinja2
from ciparse import run


def main():

    def by_job_type(l):
        job_types = {i["job"]["job_type"] for i in l if i["job"]["job_type"]}
        d = {}
        for job_type in job_types:
            d[job_type] = [i for i in l if i["job"]["job_type"] == job_type]
        return d

    work_dir = os.path.dirname(__file__)
    ci_data = run(amount=1000,
                  days=0,
                  job_type=None,
                  excluded="containers",
                  down_path=os.path.join(os.environ["HOME"], "tmp",
                                         "ci_status"),
                  page="http://tripleo.org/cistatus.html")
    periodic_data = run(amount=1000,
                         days=7,
                         job_type=None,
                         excluded="containers",
                         down_path=os.path.join(os.environ["HOME"], "tmp",
                                                "ci_status"),
                         page="http://tripleo.org/cistatus-periodic.html")

    JINJA_ENVIRONMENT = jinja2.Environment(
        loader=jinja2.FileSystemLoader(work_dir),
        extensions=['jinja2.ext.autoescape'],
        autoescape=True)
    template = JINJA_ENVIRONMENT.get_template('template.html')
    html = template.render({
        "ci": by_job_type(list(ci_data)),
        "periodic": by_job_type(list(periodic_data)),
    })
    with open(os.path.join(work_dir, "index.html"), "w") as f:
        f.write(html)


if __name__ == '__main__':
    main()

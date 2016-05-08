import jinja2
import os
import pickle

from watchcat import meow
from utils import top, statistics


def main():
    """
        This function runs job analysis by calling meow() and creates HTML page
        with all data it received.
        HTML is created by Jinja templating template.html file.
    :return: writes index.html file in current directory
    """

    def by_job_type(l):
        job_types = {i["job"].name for i in l if i["job"].name}
        d = {}
        for job_type in job_types:
            d[job_type] = [i for i in l if i["job"].name == job_type]
        return d

    work_dir = os.path.dirname(__file__)
    ci_data = meow(limit=None,
                       days=8,
                       job_type=None,
                       exclude="gate-tripleo-ci-f22-containers",
                       down_path=os.path.join(os.environ["HOME"], "ci_status"))

    periodic_data = meow(limit=None,
                         days=7,
                         job_type=None,
                         exclude=None,
                         down_path=os.path.join(os.environ["HOME"],
                                                "ci_status"),
                         periodic=True)

    with open("/tmp/ci_data_dump", "w") as g:
        pickle.dump(ci_data, g)
    with open("/tmp/periodic_data_dump", "w") as g:
         pickle.dump(periodic_data, g)
    # For debug mode
    # with open("/tmp/ci_data_dump", "rb") as g:
    #     ci_data = pickle.load(g)
    # with open("/tmp/periodic_data_dump", "rb") as g:
    #    periodic_data = pickle.load(g)

    errors_top = top(ci_data)
    stats, per_stats = statistics(ci_data), statistics(
        periodic_data, periodic=True)

    JINJA_ENVIRONMENT = jinja2.Environment(
        loader=jinja2.FileSystemLoader(work_dir),
        extensions=['jinja2.ext.autoescape'],
        autoescape=True)
    template = JINJA_ENVIRONMENT.get_template('template.html')
    html = template.render({
        "ci": by_job_type(list(ci_data)),
        "periodic": by_job_type(list(periodic_data)),
        'ci_stats': stats,
        'periodic_stats': per_stats,
        "errors_top": errors_top,
    })
    with open(os.path.join(work_dir, "index.html"), "w") as f:
        #f.write(html.encode('utf-8'))
        f.write(html.encode('ascii', 'ignore').decode('ascii'))


if __name__ == '__main__':
    main()

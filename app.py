import os
import jinja2
from watchcat import meow


def main():

    def by_job_type(l):
        job_types = {i["job"].name for i in l if i["job"].name}
        d = {}
        for job_type in job_types:
            d[job_type] = [i for i in l if i["job"].name == job_type]
        return d

    work_dir = os.path.dirname(__file__)

    local = False

    if not local:
        ci_data = meow(limit=10,
                      days=None,
                      job_type=None,
                      exclude="containers",
                      down_path=os.path.join(os.environ["HOME"],"ci_status"))

    # periodic_data = meow(amount=10,
    #                     days=0,
    #                     job_type=None,
    #                     excluded="containers",
    #                     down_path=os.path.join(os.environ["HOME"], "tmp",
    #                                            "ci_status"),
    #                     page="http://tripleo.org/cistatus-periodic.html")
    import pickle
    if not local:
        with open("/tmp/ttt", "w") as g:
            pickle.dump(ci_data, g)
    else:
        with open("/tmp/ttt", "rb") as g:
            ci_data = pickle.load(g)

    JINJA_ENVIRONMENT = jinja2.Environment(
        loader=jinja2.FileSystemLoader(work_dir),
        extensions=['jinja2.ext.autoescape'],
        autoescape=True)
    template = JINJA_ENVIRONMENT.get_template('template.html')
    html = template.render({
        "ci": by_job_type(list(ci_data)),
#        "periodic": by_job_type(list(periodic_data)),
    })
    with open(os.path.join(work_dir, "index.html"), "w") as f:
        f.write(html)


if __name__ == '__main__':
    main()

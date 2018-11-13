import os
import requests


class DownstreamKicker(object):
    def __init__(self):
        self.gitlab_url_base = "https://gitlab.polyswarm.io"
        # everything that relies on polyswarm-client, both public and private
        self.dependent_projects = os.getenv("CI_PROP_ENGINES", "").split() + os.getenv("CI_POLYSWARM_CLIENT_DOWNSTREAM", "").split()

    def kick_dependent_project(self, proj):
        r =  requests.post("{0}/api/v4/projects/{1}/trigger/pipeline/".format(self.gitlab_url_base,
                                                                                "externalci/{}".format(proj)),
                             data={"token": os.getenv("CI_JOB_TOKEN"), "ref": os.getenv("CI_COMMIT_REF_NAME")})
        r.raise_for_status()
        return r

    def kick_projects(self):
        for p in self.dependent_projects:
            self.kick_dependent_project(p)

def main():
    d = DownstreamKicker()
    d.kick_projects()


if __name__ == "__main__":
    main()
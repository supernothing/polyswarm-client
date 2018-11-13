import os
import requests


class DownstreamKicker(object):
    def __init__(self):
        self.gitlab_url_base = "https://gitlab.polyswarm.io"
        # everything that relies on polyswarm-client, both public and private
        self.dependent_projects = os.getenv("CI_PROP_ENGINES", "").split() + os.getenv("CI_POLYSWARM_CLIENT_DOWNSTREAM",
                                                                                       "").split()
        self.head = {'Private-Token': os.getenv("CI_CUSTOM_CI_PAT")}

    def resolve_project_id(self, proj):
        r = requests.get("{0}/api/v4/projects/".format(self.gitlab_url_base), headers=self.head)
        proj_name = "externalci/{}".format(proj)
        j = r.json()
        for p in j:
            if p['path_with_namespace'] == proj_name:
                return p['id']
        raise Exception("project {0} not found".format(proj_name))

    def get_or_update_project_token(self, project_id):
        url = "{0}/api/v4/projects/{1}/triggers".format(self.gitlab_url_base, project_id)

        r = requests.get(url, headers=self.head)

        r.raise_for_status()
        for t in r.json():
            if t['description'] == "kicker":
                return t['token']

        r = requests.post(url, data={'description': "kicker"}, headers=self.head)
        return r.json()['token']

    def kick_dependent_project(self, proj):

        project_id = self.resolve_project_id(proj)

        trigger_token = self.get_or_update_project_token(project_id)

        r = requests.post("{0}/api/v4/projects/{1}/trigger/pipeline".format(self.gitlab_url_base,
                                                                            project_id),

                          data={'ref': os.getenv("CI_COMMIT_REF_NAME"), 'token': trigger_token},
                          )
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

import os
import requests
from requests import HTTPError


class DownstreamKicker(object):
    def __init__(self):
        self.gitlab_url_base = "https://gitlab.polyswarm.io"
        # everything that relies on polyswarm-client, both public and private
        self.dependent_projects = os.getenv("CI_POLYSWARM_CLIENT_DOWNSTREAM", "").split()

        self.head = {'Private-Token': os.getenv("CI_CUSTOM_CI_PAT")}

    def resolve_project_id(self, proj):
        j = self._get_all_projects()
        proj_name = "externalci/{}".format(proj)

        for p in j:
            if p['path_with_namespace'] == proj_name:
                return p['id']
        raise Exception("project {0} not found".format(proj_name))

    def _get_all_projects(self):
        r = requests.get("{0}/api/v4/projects/".format(self.gitlab_url_base), headers=self.head)
        r.raise_for_status()
        return r.json()

    def get_or_update_project_token(self, project_id):
        url = "{0}/api/v4/projects/{1}/triggers".format(self.gitlab_url_base, project_id)

        r = requests.get(url, headers=self.head)

        r.raise_for_status()
        for t in r.json():
            if t['description'] == "kicker":
                return t['token']

        r = requests.post(url, data={'description': "kicker"}, headers=self.head)
        j = r.json()
        return j['token']

    def kick_dependent_project(self, proj):

        project_id = self.resolve_project_id(proj)

        trigger_token = self.get_or_update_project_token(project_id)
        ref_name = os.getenv("CI_COMMIT_REF_NAME")

        r = None
        try:
            r = requests.post("{0}/api/v4/projects/{1}/trigger/pipeline".format(self.gitlab_url_base, project_id),
                              data={'ref': ref_name, 'token': trigger_token},

                              )
            r.raise_for_status()
        except HTTPError as e:
            if os.getenv("CI_COMMIT_REF_NAME") != "master":
                print("Matching branch {0} not found, skipping for project {1}".format(ref_name, proj))
                return r
            raise e
        return r

    def get_engine_projects(self):
        """
        Get all projects that are engines, rebuild.
        :return: ['engine-ikarus']
        """
        ps = []
        for p in self._get_all_projects():
            if p['path_with_namespace'].startswith("externalci/engine-"):
                ps.append(p['path'])
        return ps

    def kick_projects(self):
        for p in self.dependent_projects:
            self.kick_dependent_project(p)

    def kick_engine_projects(self):
        # todo command line for this
        engines = os.getenv("CI_PROP_ENGINES", "").split()
        if not engines:
            engines = self.get_engine_projects()
        for p in engines:
            self.kick_dependent_project(p)


def main():
    d = DownstreamKicker()
    d.kick_projects()
    d.kick_engine_projects()


if __name__ == "__main__":
    main()

import os
import tempfile
import urllib.request
import logging
from subprocess import check_call
from arbiter.verbatimdb.__main__ import generate_db

MALICIOUS_BOOTSTRAP_URL = os.getenv('MALICIOUS_BOOTSTRAP_URL')
ARCHIVE_PW = os.getenv('ARCHIVE_PASSWORD')


class DownloadToFileSystemCorpus(object):
    def __init__(self, base_dir=None):
        self.url = MALICIOUS_BOOTSTRAP_URL
        self.base_dir = base_dir if base_dir else tempfile.mkdtemp(suffix="malware-corpus")
        self.truth_fname = "truth.db"
        self.truth_db_pth = os.path.join(self.base_dir, self.truth_fname)

    @property
    def mal_path(self):
        return os.path.join(self.base_dir, "malicious")

    @property
    def benign_pth(self):
        return os.path.join(self.base_dir, "malicious")

    def download_and_unpack(self):
        logging.info("Downloading to {0}".format(self.base_dir))
        for is_mal, package_name in [(True, "malicious.tgz.gpg"), (False, "benign.tgz.gpg")]:

            mal_dir = self.mal_path if is_mal else self.benign_pth
            archive_pth = os.path.join(mal_dir, package_name)
            archive_dst = mal_dir
            if not os.path.isdir(archive_dst):
                os.mkdir(archive_dst)
            archive_tgz = archive_pth.rstrip(".gpg")
            r = urllib.request.urlretrieve("{0}/{1}".format(self.url, package_name), archive_pth)
            check_call(["gpg", "--batch", "--passphrase", ARCHIVE_PW, "--decrypt",
                        "--no-use-agent", "--cipher-algo", "AES256",
                         "--yes", "-o", archive_tgz, archive_pth])
            # can do with python tar file, but being lazy
            check_call(["tar", "xf", archive_tgz, "-C", archive_dst])
            os.unlink(archive_tgz)
            os.unlink(archive_pth)

    def _get_pth_listing(self, p):
        artifacts = []
        for root, dirs, files in os.walk(p):
            for f in files:
                artifacts.append(os.path.join(root, f))
        return artifacts

    def get_malicious_file_list(self):
        return self._get_pth_listing(self.mal_path)

    def get_benign_file_list(self):
        return self._get_pth_listing(self.benign_pth)

    def download_truth(self):
        u = "{0}/{1}".format(self.url, self.truth_fname)
        logging.info("Fetching truth database {0}".format(u))
        r = urllib.request.urlretrieve(u, self.truth_db_pth)

    def generate_truth(self):
        d = generate_db(self.truth_db_pth, self.mal_path, self.benign_pth)

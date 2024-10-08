import docker
import subprocess
import logging


client = docker.from_env()

IMAGE_CACHE = {}

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


class Container(object):

    def __init__(self, attrs):
        self.name = attrs["Name"].lstrip("/")
        self.image_sha256 = attrs["Image"]
        self.image = attrs["Config"]["Image"]
        self.labels = attrs["Config"]["Labels"]

        self.auto_update_enabled = self.labels.get("patcher/auto-update", "false").lower() == "true"
        self.systemd_name = self.labels.get("patcher/systemd-name", self.name)

        repo_image = client.images.get(self.image_sha256)
        self.repo_image_sha256 = repo_image.attrs["RepoDigests"][0].split("@")[1]

    def should_update(self):
        if not self.auto_update_enabled:
            return False
        if self.image not in IMAGE_CACHE:
            d = client.images.get_registry_data(self.image)
            d.pull()
            d.reload()
            IMAGE_CACHE[self.image] = d.attrs["Descriptor"]["digest"]
        return IMAGE_CACHE[self.image] != self.repo_image_sha256

    def restart(self):
        p = subprocess.Popen(['systemctl', 'restart', self.systemd_name], stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE, shell=False)
        output = p.communicate()
        if p.returncode != 0:
            LOGGER.error("Failed to restart {0}, output from systemd: {1}".format(self.systemd_name, output[1]))

    def __repr__(self):
        return "<Container (name={0}, image_sha256={1}, image={2}, repo_image_sha256={3}, auto_update_enabled={4}, systemd_name={5})>".\
            format(self.name, self.image_sha256, self.image, self.repo_image_sha256, self.auto_update_enabled, self.systemd_name)


def get_containers():
    rv = client.containers.list(all=False)
    return [Container(x.attrs) for x in rv]


if __name__ == '__main__':
    for container in get_containers():
        try:
            LOGGER.info("Acting on {0}".format(container))
            if container.should_update():
                LOGGER.info("Restarting {0}".format(container))
                container.restart()
        except Exception as e:
            LOGGER.exception("Error occurred for {0}".format(container))

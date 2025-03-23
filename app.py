import docker
from docker.models.containers import Container
import concurrent.futures
import logging
import os


client = docker.from_env()

IMAGE_CACHE = {}

logging.basicConfig(level=logging.INFO, format="%(levelno)s:%(name)s:%(threadName)s:%(message)s")
LOGGER = logging.getLogger(__name__)

THREAD_POOL_SIZE = int(os.getenv("THREAD_POOL_SIZE", "3"))


class ContainerUpdate(object):

    def __init__(self, container: Container):
        self.container = container
        self.name = container.attrs["Name"].lstrip("/")
        self.image = container.attrs["Config"]["Image"]
        self.labels = container.attrs["Config"]["Labels"]
        self.auto_update_enabled = self.labels.get("patcher/auto-update", "false").lower() == "true"
        self.container_stop_timeout = int(self.labels.get("patcher/stop-timeout", "30"))
        self.repo_image_sha256 = container.image.attrs["RepoDigests"][0].split("@")[1]

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
        self.container.stop(timeout=self.container_stop_timeout)

    def __repr__(self):
        return (f"<ContainerUpdate (name={self.name}, image={self.image}, repo_image_sha256={self.repo_image_sha256}, "
                f"auto_update_enabled={self.auto_update_enabled})>")


def get_containers():
    rv = client.containers.list(all=False)
    return [ContainerUpdate(x) for x in rv]


def handle_container_update(cu: ContainerUpdate):
    try:
        LOGGER.info(f"Evaluating {cu}")
        if cu.should_update():
            LOGGER.info(f"Restarting {cu}")
            cu.restart()
    except Exception as e:
        LOGGER.exception(f"Error occurred for {cu}")


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
        cus = get_containers()
        future_to_handle = {executor.submit(handle_container_update, cu): cu for cu in cus}
        for future in concurrent.futures.as_completed(future_to_handle):
            try:
                future.result()
            except Exception as exc:
                LOGGER.exception("Error occurred")

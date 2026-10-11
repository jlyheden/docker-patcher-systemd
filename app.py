import docker
import docker.errors
from docker.models.containers import Container
import concurrent.futures
import logging
import os
import subprocess
from contextvars import ContextVar
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

client = docker.from_env()

state = ContextVar("state", default=0)

IMAGE_CACHE = {}

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(threadName)s:%(message)s")
LOGGER = logging.getLogger(__name__)

THREAD_POOL_SIZE = int(os.getenv("THREAD_POOL_SIZE", "3"))


class DockerRetryException(Exception):
    pass


class ContainerUpdate(object):

    def __init__(self, container: Container):
        self.container = container
        self.name = container.attrs["Name"].lstrip("/")
        self.image = container.attrs["Config"]["Image"]
        if ":" in self.image:
            self.repository, self.tag = self.image.split(":")
        else:
            self.repository = self.image
            self.tag = None
        self.labels = container.attrs["Config"]["Labels"]
        self.auto_update_enabled = self.labels.get("patcher/auto-update", "false").lower() == "true"
        self.should_pull = self.labels.get("patcher/auto-pull", "false").lower() == "true"
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

    def pull(self):
        client.images.pull(self.repository, tag=self.tag)

    def restart(self):
        self.container.stop(timeout=self.container_stop_timeout)

    def __repr__(self):
        return (f"<ContainerUpdate (name={self.name}, image={self.image}, repo_image_sha256={self.repo_image_sha256}, "
                f"auto_update_enabled={self.auto_update_enabled})>")


def get_containers():
    rv = client.containers.list(all=False)
    return [ContainerUpdate(x) for x in rv]


@retry(retry=retry_if_exception_type(DockerRetryException),
       wait=wait_exponential(multiplier=1, min=10, max=600),
       stop=stop_after_attempt(50))
def handle_container_update(cu: ContainerUpdate):
    attempt_state = state.get()
    try:
        LOGGER.info(f"Evaluating {cu}")
        if cu.should_update():
            if cu.should_pull:
                LOGGER.info(f"Pulling image {cu}")
                cu.pull()
            LOGGER.info(f"Restarting {cu}")
            cu.restart()
        else:
            LOGGER.info(f"Ignoring update of {cu}")
    except docker.errors.APIError as e:
        if e.response.status_code == 429:
            LOGGER.info(f"Got rate limited for {cu}")
            raise DockerRetryException(e)
        elif e.response.status_code == 500:
            LOGGER.info(f"Got http 500 for {cu}")
            raise DockerRetryException(e)
        elif e.response.status_code == 404:
            if not attempt_state == "shellpulled":
                # https://github.com/docker/docker-py/issues/2101
                LOGGER.info(f"Got 404 but it might be due to buggy py-docker, retrying with shell docker pull for {cu}")
                subprocess.call(["docker", "pull", f"{cu.repository}:{cu.tag}"])
                state.set("shellpulled")
                raise DockerRetryException(e)
            else:
                raise
        else:
            LOGGER.exception(f"Docker API error occurred that was not due to rate limit: {e}, Response: {e.response}, Response reason: {e.response.reason}, Response headers: {e.response.headers}")
    except Exception as e:
        LOGGER.exception(f"Error occurred for {cu}")


def run_task(cu: ContainerUpdate):
    token = state.set(0)  # Initialize state for this task
    try:
        return handle_container_update(cu)
    finally:
        state.reset(token)  # Restore previous context


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
        cus = get_containers()
        future_to_handle = {executor.submit(run_task, cu): cu for cu in cus}
        for future in concurrent.futures.as_completed(future_to_handle):
            try:
                future.result()
            except Exception as exc:
                LOGGER.exception("Error occurred")

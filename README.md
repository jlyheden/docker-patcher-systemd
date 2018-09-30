# docker-systemd-patcher

![Docker Automated build](https://img.shields.io/docker/automated/jlyheden/docker-patcher-systemd.svg)

A Python thing that will query the docker daemon for running container images and given that auto-update is supported will query remote repo for image updates. Updates are assumed to be handled by systemd via ExecStartPre pulls.

Run like this in cron or systemd timer:

```
docker run \
    --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /var/run/dbus:/var/run/dbus \
    -v /run/systemd:/run/systemd \
    -v /usr/bin/systemctl:/usr/bin/systemctl \
    -v /etc/systemd/system:/etc/systemd/system \
    jlyheden/docker-patcher-systemd
```

For containers that you want to be patched add a label **patcher/auto-update=true**. Default behavior is to ignore the container.

The application will assume that the container name matches the systemd service name but that can be overridden by setting the label **patcher/systemd-name=some-name**

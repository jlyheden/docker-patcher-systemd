# docker-systemd-patcher

[![Docker Automated build](https://img.shields.io/docker/automated/jlyheden/docker-patcher-systemd.svg)](https://hub.docker.com/r/jlyheden/docker-patcher-systemd/builds/)

A Python script that connects to the docker daemon to see if there's any running containers where the image tag has been
updated and if so stops the container, relying on systemd to start it up again. Works fine for non-critical setups like
keeping your home server or hobby projects up to date but if you need something more advanced you should probably check
out [watchtower](https://github.com/containrrr/watchtower)

The script assumes that the container lifecycle is handled by systemd, for example running a nginx container like this:

```ini
# /etc/systemd/system/docker.nginx.service
[Unit]
Description=Nginx reverse proxy container

[Service]
TimeoutStartSec=0
Restart=always
ExecStop=-/usr/bin/docker stop %n
ExecStart=/usr/bin/docker run \
  --rm \
  --name %n \
  -p 80:80 \
  -p 443:443 \
  --label "patcher/auto-update=true" \
  --label "patcher/auto-pull=true" \
  --label "patcher/stop-timeout=30" \
  nginx:mainline-alpine

[Install]
WantedBy=multi-user.target
```

And then, to run the patcher script on a cron schedule (below works on Debian 12). Max parallel updates configured
via `THREAD_POOL_SIZE` env var.

```ini
# /etc/systemd/system/docker.patcher.service
[Unit]
Description=Patches selected systemd docker containers
Requires=docker.patcher.service

[Service]
Type=oneshot
ExecStartPre=/usr/bin/docker pull jlyheden/docker-patcher-systemd:latest
ExecStart=/usr/bin/docker run \
  --rm \
  --name %n \
  -e THREAD_POOL_SIZE=3 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jlyheden/docker-patcher-systemd:latest

# /etc/systemd/system/docker.patcher.timer
[Unit]
Description=Timer for docker.patcher.service

[Timer]
OnCalendar=Mon *-*-* 5:00:00

[Install]
WantedBy=timers.target
```

For all the containers that you want to be auto updated you must add a label `patcher/auto-update=true` or the patcher
will ignore the container. You can tweak by container how many seconds the graceful shutdown will wait
via `patcher/stop-timeout=N`. Default is `30` seconds.

## Configuration toggles

| Type                 | Scope     | Name                 | Description                                                                 | Default |
|----------------------|-----------|----------------------|-----------------------------------------------------------------------------|---------|
| Environment variable | Global    | THREAD_POOL_SIZE     | Number of parallel containers to update                                     | 3       |
| Container label      | Container | patcher/auto-update  | Toggle if container should be updated                                       | false   |
| Container label      | Container | patcher/auto-pull    | Toggle if container image should be pulled                                  | false   |
| Container label      | Container | patcher/stop-timeout | Wait time in seconds for container to stop gracefully before applying force | 30      |
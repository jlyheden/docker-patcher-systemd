# docker-systemd-patcher

[![Docker Automated build](https://img.shields.io/docker/automated/jlyheden/docker-patcher-systemd.svg)](https://hub.docker.com/r/jlyheden/docker-patcher-systemd/builds/)

A Python script that connects to the docker daemon to see if there's any running containers where the image tag has been updated and if so triggers a systemd restart of the relevant containers. Works fine for non-critical setups like keeping your home server or hobby projects up to date but if you need something more advanced you should probably check out [watchtower](https://github.com/containrrr/watchtower)

It assumes that containers are handled by systemd, for example running an nginx container like this:

```
$ cat /etc/systemd/system/docker.nginx.service
[Unit]
Description=Nginx reverse proxy container

[Service]
TimeoutStartSec=0
Restart=always
ExecStop=-/usr/bin/docker stop %n
ExecStartPre=/usr/bin/docker pull nginx:mainline-alpine
ExecStart=/usr/bin/docker run \
  --rm \
  --name %n \
  -p 80:80 \
  -p 443:443 \
  --label "patcher/auto-update=true" \
  nginx:mainline-alpine

[Install]
WantedBy=multi-user.target
```

Then run like this in a systemd timer:

```
$ cat /etc/systemd/system/docker.patcher.service
[Unit]
Description=Patches selected systemd docker containers
Requires=docker.patcher.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker run \
  --rm \
  --name %n \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/run/dbus:/var/run/dbus \
  -v /run/systemd:/run/systemd \
  -v /usr/bin/systemctl:/usr/bin/systemctl \
  -v /etc/systemd/system:/etc/systemd/system \
  jlyheden/docker-patcher-systemd

$ cat /etc/systemd/system/docker.patcher.timer
[Unit]
Description=Timer for docker.patcher.service

[Timer]
OnCalendar=Mon *-*-* 5:00:00

[Install]
WantedBy=timers.target
```

For the containers that you want to be auto updated you must add a label `patcher/auto-update=true`. Default behavior is to ignore the container.

The script will assume that the container name matches the systemd service name but this can be overridden by setting the label `patcher/systemd-name=some-name`

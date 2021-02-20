# docker-systemd-patcher

[![Docker Automated build](https://img.shields.io/docker/automated/jlyheden/docker-patcher-systemd.svg)](https://hub.docker.com/r/jlyheden/docker-patcher-systemd/builds/)

A Python script that connects to the docker daemon to see if there's any running containers where the image tag has been updated and if so triggers a systemd restart of the relevant containers. Works fine for non-critical setups like keeping your home server or hobby projects up to date but if you need something more advanced you should probably check out [watchtower](https://github.com/containrrr/watchtower)

The script assumes that the container lifecycle is handled by systemd, for example running an nginx container like this:

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

And then, to run the patcher script on a cron schedule (below works on Debian 10):

```
$ cat /etc/systemd/system/docker.patcher.service
[Unit]
Description=Patches selected systemd docker containers
Requires=docker.patcher.service

[Service]
Type=oneshot
ExecStartPre=/usr/bin/docker pull jlyheden/docker-patcher-systemd:latest
ExecStart=/usr/bin/docker run \
  --rm \
  --name %n \
  -v /bin/systemctl:/bin/systemctl \
  -v /run/systemd/system:/run/systemd/system \
  -v /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket \
  -v /sys/fs/cgroup:/sys/fs/cgroup \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jlyheden/docker-patcher-systemd:latest

$ cat /etc/systemd/system/docker.patcher.timer
[Unit]
Description=Timer for docker.patcher.service

[Timer]
OnCalendar=Mon *-*-* 5:00:00

[Install]
WantedBy=timers.target
```

For all the containers that you want to be auto updated you must add a label `patcher/auto-update=true`. Default behavior is to ignore the container if the label is not set.

The script will assume that the container name matches the systemd service name but this can be overridden by setting the label `patcher/systemd-name=some-name`

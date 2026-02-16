---
title: "Docker Swarm"
weight: 2
---

Prerequisites:
- Docker with Swarm mode enabled

Initialize swarm and deploy:

```bash
docker swarm init
docker stack deploy -c docs/deployment/docker-compose.yml intentkit
```

Check services:

```bash
docker service ls
```

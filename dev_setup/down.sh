#!/bin/bash


docker-compose -f $(pwd)/dev_setup/database/docker-compose.yml down  --remove-orphans --volumes

docker-compose -f $(pwd)/dev_setup/broker/docker-compose.yml down  --remove-orphans --volumes

docker-compose -f $(pwd)/dev_setup/cache/docker-compose.yml down  --remove-orphans --volumes

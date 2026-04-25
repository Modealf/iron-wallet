
#!/bin/bash


docker-compose -f $(pwd)/dev_setup/database/docker-compose.yml up  -d

docker-compose -f $(pwd)/dev_setup/cache/docker-compose.yml up -d

docker-compose -f $(pwd)/dev_setup/broker/docker-compose.yml up -d


sleep 4

docker exec database sh -c "/cockroach/cockroach sql -u root --insecure  --host=database < /docker-entrypoint-initdb.d/init.sql"

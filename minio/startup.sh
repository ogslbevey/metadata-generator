#!/bin/sh

# start the service 
echo 'starting minio...'
minio server /data --console-address ":9001" &

# ensure that the service has started
echo 'waiting for minio to start...'
for i in {1..5}; do
	if timeout 5s bash -c ':> /dev/tcp/127.0.0.1/9000'; then
		break
	elif [ $i -eq 5 ]; then
	  echo 'minio is not starting properly... cannot create bucket'
		exit 1
	fi
	sleep 1
done

# login
mc alias set minio http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD &&

# setup the bucket if it doesn't exist
if ! mc ls minio/bucket; then
	echo 'bucket does not exist! creating...'
  mc mb minio/bucket
else
  echo 'bucket already exists! starting...'
fi

# sleep until interrupted...
sleep inf
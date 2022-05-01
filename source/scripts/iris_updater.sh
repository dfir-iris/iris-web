echo "=== IRIS UPDATES ==="
echo "Will unpack $1"
echo "Target IRIS directory is $2"

pkill gunicorn

sleep 2

pkill gunicorn

TMP_DIR=/tmp/iris_updates

if [ -d $TMP_DIR ]
then
  echo "Cleaning previous updates temporary files"
  rm -rf $TMP_DIR
fi

mkdir -p /tmp/iris_updates

echo "Started unpacking update archive"
unzip -q $1 -d /tmp/iris_updates
echo "Done"

echo "Applying updates"
rsync -av --checksum $TMP_DIR/$3/source/ $2
echo "Done"

# If need reboot
if [[ $6 ]]
then

  # cd to update directory
  cd $2

  # if in docker, call the entrypoint
  if [[ $5 -eq 1 ]]
  then

    echo "Restarting IRIS"
    exec celery -A app.celery control shutdown
    nohup ./iris-entrypoint.sh $4

  else

    # Otherwise, not in docker, directly call the methods
    if [[ $4 -eq "worker" ]]
    then
      echo "Restarting IRIS worker"
      exec celery -A app.celery control shutdown
      sleep 2
      exec celery -A app.celery worker -E -l INFO

    else:
      echo "Restarting IRIS web app"
      exec gunicorn app:app --worker-class eventlet --bind 0.0.0.0:8000 --timeout 180 --worker-connections 1000 --log-level=info

    fi # worker condition

  fi # docker condition

fi # restart condition

echo "Updates applied"


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
rsync -av --checksum $TMP_DIR/source/ $2

echo "Upgrading packages"
cd $2
pip3 install -r requirements.txt

echo "Done"

# If need reboot
if [[ $6 -eq 1 ]]
then

  # cd to update directory
  cd $2

  if [ $4 == "worker" ]
  then
    echo "Restarting IRIS worker"
    celery -A app.celery control shutdown
    sleep 2
    exec celery -A app.celery worker -E -B -l INFO

  else
    echo "Restarting IRIS Web app"
    exec gunicorn app:app --worker-class eventlet --bind 0.0.0.0:8000 --timeout 180 --worker-connections 1000 --log-level=info

  fi # Worker condition

fi # restart condition

echo "Updates applied"


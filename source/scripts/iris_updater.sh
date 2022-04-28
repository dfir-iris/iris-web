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

if [[ $6 ]]
then
  echo "Restarting IRIS web app"
  cd $2
  if [[ $5 -eq 1 ]]
  then
    nohup ./iris-entrypoint.sh $4
  else
    exec gunicorn app:app --worker-class eventlet --bind 0.0.0.0:8000 --timeout 180 --worker-connections 1000 --log-level=info
  fi
fi

echo "Update applied"


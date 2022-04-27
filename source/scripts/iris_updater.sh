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

echo "Restarting IRIS web app"
cd $2
#chmox +x iris-entrypoint.sh
nohup ./iris-entrypoint.sh $4
echo "Done - Update applied"


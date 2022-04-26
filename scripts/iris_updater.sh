echo "=== IRIS UPDATES ==="
echo "Will unpack $1"
echo "Target IRIS directory is $2"

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
rsync -av --checksum $TMP_DIR/$3/ $2
echo "Done"

echo "Restarting IRIS web app"
nohup cd source && ../docker/webApp/iris-entrypoint.sh $3
echo "Done - Update applied"


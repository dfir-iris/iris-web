#
# before we build the image & create the devcontainer, we will...
#

echo $PWD

# copy `.env.model` to `.env` if it doesn't exist already
if [ ! -f .env ]; then
    echo ".env not found, cloning .env.model"
    cp .env.model .env
fi
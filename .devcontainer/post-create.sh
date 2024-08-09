#
# after our initial creation of the devcontainer, we will...
#

# mark workspace dir as safe dir for git (b/c container user != host user)
git config --global --add safe.directory /workspaces/iris-web

# change working dir to source 
cd source

# install python dependencies
pip install -r requirements.txt
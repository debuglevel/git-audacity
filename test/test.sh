set -u
set -o pipefail
set -e 

TEMPORARY_PROJECT_FILE="test.aup3"
DESTINATION_DIRECTORY="$TEMPORARY_PROJECT_FILE.sql.dir"
VERSION_1_PROJECT_FILE="test_1.aup3"
VERSION_2_PROJECT_FILE="test_2.aup3"

echo "Removing former state..."
rm -rf "$TEMPORARY_PROJECT_FILE"
rm -rf "$DESTINATION_DIRECTORY"

echo "Removing .git"
rm -rf .git

echo "Initialize git..."
git init --initial-branch=main .
git config user.email "you@example.com"
git config user.name "Your Name"


echo "Copying project file version 1..."
cp "$VERSION_1_PROJECT_FILE" "$TEMPORARY_PROJECT_FILE"

echo "Exploding project file version 1..."
python3 aup3git.py explode "$TEMPORARY_PROJECT_FILE"

echo
echo "git add split-directory version 1..."
git add "$DESTINATION_DIRECTORY"

echo "git commit split-directory  version 1 (--quiet; i.e. no ouput)..."
git commit -m 'version 1' --quiet

echo "====> .git size:"
du -hs .git

echo
echo "================="
echo

echo "Copying project file version 2..."
cp "$VERSION_2_PROJECT_FILE" "$TEMPORARY_PROJECT_FILE"

echo "Exploding project file version 2..."
python3 aup3git.py explode "$TEMPORARY_PROJECT_FILE"

echo
echo "git add split-directory version 2..."
git add "$DESTINATION_DIRECTORY"

echo "git commit split-directory version 2..."
git commit -m 'version 2'

echo "====> .git size:"
du -hs .git

echo
echo "================="
echo

echo "Removing project file..."
rm "$TEMPORARY_PROJECT_FILE"

echo "Imploding..."
python3 aup3git.py implode "$TEMPORARY_PROJECT_FILE"

LATESTTAG=$(git describe --tags --abbrev=0)

rm -rf build dist

python -m build

read -p "Upload to PyPi? (enter to confirm, ctrl-c to quit)"

python -m twine upload dist/*

rm -rf build dist

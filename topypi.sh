
rm -rf build dist

python -m build

read -p "Upload to PyPi? (enter to confirm, ctrl-c to quit)"

python -m twine upload --verbose dist/*

rm -rf build dist

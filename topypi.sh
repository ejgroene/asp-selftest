LATESTTAG=$(git describe --tags --abbrev=0)

#rm -rf build dist

python -m build
#python -m twine upload dist/*

#rm -rf build dist

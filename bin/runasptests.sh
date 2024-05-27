#
# Find all logic (asp) files and run their tests.
# Implicitly run the Python tests of asp-tests.
#
for fname in `find . -name "*.lp"`; do
    pushd `dirname ${fname}` > /dev/null
    asp-tests `basename ${fname}`
    if [ $? -ne 0 ]; then
        echo "An error occurred. Quiting."
        popd > /dev/null
        exit
    fi
    popd > /dev/null
done


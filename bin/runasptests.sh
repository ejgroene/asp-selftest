#
# Find all logic (asp) files and run their tests.
# Implicitly run the Python tests of asp-tests.
#
for fname in `find . -name "*.lp"`; do
    asp-tests ${fname} --silent
    error=$?
    if [ $error -ne 0 ]; then
        echo '\[$(tput bold)\]An error occurred during asp-test\[$(tput sgr0)\]. Quiting.'
        exit $error
    fi
done



import clingo


NA = clingo.String("N/A")


def Noop(next, *args, **kwargs):
    return next(*args, **kwargs)


def write_file(file, text):
    file.write_text(text)
    return file.as_posix()